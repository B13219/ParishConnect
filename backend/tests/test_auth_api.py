from collections.abc import Generator

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import password_hash, require_roles
from app.core.settings import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, Role, User, UserRole


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with TestingSessionLocal() as db:
        branch = Branch(name="Test Parish", location="Test City")
        admin_role = Role(name="Administrator", description="Full access")
        usher_role = Role(name="Usher", description="Attendance check-in")
        db.add_all([branch, admin_role, usher_role])
        db.flush()
        admin = User(
            branch_id=branch.id,
            name="Ada Admin",
            email="admin@test.local",
            password_hash=password_hash("parishconnect"),
            status="active",
        )
        usher = User(
            branch_id=branch.id,
            name="Uma Usher",
            email="usher@test.local",
            password_hash=password_hash("parishconnect"),
            status="active",
        )
        db.add_all([admin, usher])
        db.flush()
        db.add_all(
            [
                UserRole(user_id=admin.id, role_id=admin_role.id),
                UserRole(user_id=usher.id, role_id=usher_role.id),
            ]
        )
        db.commit()

    app = create_app()

    @app.get("/test-admin-only")
    def admin_only(user: User = Depends(require_roles("pastor_leader"))) -> dict[str, str]:
        return {"email": user.email}

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_login_returns_token_and_role_profile() -> None:
    client = build_client()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "parishconnect"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["roles"] == ["administrator"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "admin@test.local"


def test_login_rejects_bad_password() -> None:
    client = build_client()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "wrong"},
    )

    assert response.status_code == 401


def test_logout_requires_current_user() -> None:
    client = build_client()
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "parishconnect"},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "logged_out"


def test_password_reset_round_trip_updates_password(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "local")
    client = build_client()

    request = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "admin@test.local"},
    )
    token = request.json()["demo_reset_token"]
    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "new-secure-password"},
    )
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "parishconnect"},
    )
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "new-secure-password"},
    )

    assert confirm.status_code == 200
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_role_dependency_allows_admin_and_denies_usher() -> None:
    client = build_client()
    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "parishconnect"},
    ).json()["access_token"]
    usher_token = client.post(
        "/api/v1/auth/login",
        json={"email": "usher@test.local", "password": "parishconnect"},
    ).json()["access_token"]

    admin_response = client.get(
        "/test-admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    usher_response = client.get(
        "/test-admin-only",
        headers={"Authorization": f"Bearer {usher_token}"},
    )

    assert admin_response.status_code == 200
    assert usher_response.status_code == 403


def test_password_reset_does_not_expose_token_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    client = build_client()

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "admin@test.local"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert "demo_reset_token" not in response.json()

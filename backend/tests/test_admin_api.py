from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import AuditLog, Branch, User
from tests.auth_helpers import add_test_user, auth_headers


def build_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with TestingSessionLocal() as db:
        branch = Branch(name="Test Parish", location="Test City")
        db.add(branch)
        db.flush()
        add_test_user(db, branch, "Administrator")
        add_test_user(db, branch, "Receptionist")
        add_test_user(db, branch, "Accountant")
        add_test_user(db, branch, "Usher")
        add_test_user(db, branch, "Pastor / Leader")
        db.commit()

    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def test_admin_can_create_user_assign_role_and_view_audit_log() -> None:
    client, SessionLocal = build_client()
    headers = auth_headers(client, "Administrator")

    response = client.post(
        "/api/v1/admin/users",
        json={
            "name": "New Usher",
            "email": "new.usher@test.local",
            "phone": "+255 700 000 000",
            "password": "parishconnect",
            "role": "usher",
        },
        headers=headers,
    )

    assert response.status_code == 201
    created = response.json()
    assert created["email"] == "new.usher@test.local"
    assert created["roles"] == ["usher"]

    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.status_code == 200
    assert any(user["email"] == "new.usher@test.local" for user in users.json()["users"])

    logs = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert logs.status_code == 200
    assert logs.json()["audit_logs"][0]["action"] == "admin.user_created"

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "new.usher@test.local"))
        assert user is not None
        assert db.scalar(select(AuditLog).where(AuditLog.entity_id == user.id)) is not None


def test_admin_can_update_user_role_status_and_password() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Administrator")

    users = client.get("/api/v1/admin/users", headers=headers).json()["users"]
    receptionist = next(user for user in users if user["primary_role"] == "receptionist")

    response = client.patch(
        f"/api/v1/admin/users/{receptionist['id']}",
        json={"role": "accountant", "status": "inactive", "password": "new-password"},
        headers=headers,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["roles"] == ["accountant"]
    assert updated["status"] == "inactive"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "receptionist@test.local", "password": "new-password"},
    )
    assert login.status_code == 401


def test_non_admin_cannot_manage_users() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    response = client.get("/api/v1/admin/users", headers=headers)

    assert response.status_code == 403


def test_admin_can_update_branch_settings_and_audit_change() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Administrator")

    response = client.patch(
        "/api/v1/admin/branch",
        json={
            "name": "Grace Parish Main",
            "location": "Dar es Salaam",
            "contact_phone": "+255 700 111 000",
        },
        headers=headers,
    )

    assert response.status_code == 200
    branch = response.json()["branch"]
    assert branch["name"] == "Grace Parish Main"
    assert branch["contact_phone"] == "+255 700 111 000"

    logs = client.get("/api/v1/admin/audit-logs", headers=headers).json()["audit_logs"]
    assert logs[0]["action"] == "admin.branch_updated"


def test_admin_can_create_backup_manifest_and_audit_export() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Administrator")

    response = client.post("/api/v1/admin/backup-manifest", headers=headers)

    assert response.status_code == 200
    manifest = response.json()
    assert manifest["kind"] == "backup_manifest"
    assert manifest["branch"]["name"] == "Test Parish"
    assert manifest["table_counts"]["users"] >= 4
    assert manifest["table_counts"]["branches"] == 1

    logs = client.get("/api/v1/admin/audit-logs", headers=headers).json()["audit_logs"]
    assert logs[0]["action"] == "admin.backup_manifest_exported"


def test_non_admin_cannot_create_backup_manifest() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    response = client.post("/api/v1/admin/backup-manifest", headers=headers)

    assert response.status_code == 403

def test_administrator_can_update_geofence_settings() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Administrator")

    response = client.put(
        "/api/v1/admin/branch/geofence",
        json={
            "setup_method": "manual",
            "latitude": -6.7924,
            "longitude": 39.2083,
            "attendance_radius_meters": 120,
            "geofence_enabled": True,
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()["geofence"]
    assert data["setup_method"] == "manual"
    assert data["latitude"] == -6.7924
    assert data["longitude"] == 39.2083
    assert data["attendance_radius_meters"] == 120
    assert data["geofence_enabled"] is True


def test_pastor_leader_can_update_geofence_settings() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.put(
        "/api/v1/admin/branch/geofence",
        json={
            "setup_method": "map",
            "latitude": -6.7924,
            "longitude": 39.2083,
            "attendance_radius_meters": 100,
            "geofence_enabled": True,
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["geofence"]["setup_method"] == "map"


def test_geofence_requires_coordinates_when_enabled() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Administrator")

    response = client.put(
        "/api/v1/admin/branch/geofence",
        json={
            "setup_method": "manual",
            "latitude": None,
            "longitude": None,
            "attendance_radius_meters": 100,
            "geofence_enabled": True,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_geofence_can_be_disabled_without_coordinates() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Pastor / Leader")

    response = client.put(
        "/api/v1/admin/branch/geofence",
        json={
            "setup_method": "manual",
            "latitude": None,
            "longitude": None,
            "attendance_radius_meters": 100,
            "geofence_enabled": False,
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["geofence"]["geofence_enabled"] is False
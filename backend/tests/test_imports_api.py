from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import AuditLog, Branch, ImportBatch, Member
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
        add_test_user(db, branch, "Usher")
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


def test_receptionist_can_preview_and_commit_member_import() -> None:
    client, SessionLocal = build_client()
    headers = auth_headers(client, "Receptionist")
    csv_text = (
        "first_name,last_name,phone,email,status\n"
        "Neema,Kileo,+255 1,neema@test.local,active\n"
        "Missing,,,+255bad,active\n"
    )

    preview = client.post(
        "/api/v1/imports/preview",
        json={"import_type": "members", "csv_text": csv_text, "file_name": "members.csv"},
        headers=headers,
    )

    assert preview.status_code == 200
    assert preview.json()["total_rows"] == 2
    assert preview.json()["valid_rows"] == 1
    assert preview.json()["failed_rows"] == 1

    commit = client.post(
        "/api/v1/imports/commit",
        json={"import_type": "members", "csv_text": csv_text, "file_name": "members.csv"},
        headers=headers,
    )

    assert commit.status_code == 201
    assert commit.json()["import"]["successful_rows"] == 1
    with SessionLocal() as db:
        assert db.scalar(select(Member).where(Member.email == "neema@test.local")) is not None
        batch = db.scalar(select(ImportBatch))
        assert batch is not None
        assert batch.failed_rows == 1
        assert db.scalar(select(AuditLog).where(AuditLog.entity_id == batch.id)) is not None


def test_import_rejects_missing_required_columns() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    response = client.post(
        "/api/v1/imports/preview",
        json={"import_type": "members", "csv_text": "first_name,email\nOnly,only@test.local\n"},
        headers=headers,
    )

    assert response.status_code == 422
    assert "last_name" in response.json()["detail"]


def test_usher_cannot_import_people() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Usher")

    response = client.post(
        "/api/v1/imports/preview",
        json={
            "import_type": "members",
            "csv_text": "first_name,last_name\nAsha,Mwinyi\n",
        },
        headers=headers,
    )

    assert response.status_code == 403

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Branch
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


def test_create_and_update_member() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    create_response = client.post(
        "/api/v1/members/",
        json={
            "first_name": "Test",
            "last_name": "Member",
            "phone": "+255 700 000 111",
            "email": "test.member@example.test",
        },
        headers=headers,
    )

    assert create_response.status_code == 201
    member = create_response.json()
    assert member["name"] == "Test Member"
    assert member["status"] == "active"

    update_response = client.patch(
        f"/api/v1/members/{member['id']}",
        json={"membership_status": "inactive"},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["status"] == "inactive"


def test_member_lifecycle_status_updates() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    create_response = client.post(
        "/api/v1/members/",
        json={"first_name": "Lifecycle", "last_name": "Member"},
        headers=headers,
    )
    member_id = create_response.json()["id"]

    for lifecycle_status in ["transferred", "deceased", "discontinued"]:
        update_response = client.patch(
            f"/api/v1/members/{member_id}",
            json={"membership_status": lifecycle_status},
            headers=headers,
        )

        assert update_response.status_code == 200
        assert update_response.json()["status"] == lifecycle_status


def test_create_update_and_convert_visitor() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    create_response = client.post(
        "/api/v1/members/visitors",
        json={
            "first_name": "Test",
            "last_name": "Visitor",
            "phone": "+255 700 000 222",
            "email": "test.visitor@example.test",
        },
        headers=headers,
    )

    assert create_response.status_code == 201
    visitor = create_response.json()
    assert visitor["follow_up_status"] == "new"

    update_response = client.patch(
        f"/api/v1/members/visitors/{visitor['id']}",
        json={"follow_up_status": "contacted"},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["follow_up_status"] == "contacted"

    convert_response = client.post(
        f"/api/v1/members/visitors/{visitor['id']}/convert",
        headers=headers,
    )

    assert convert_response.status_code == 201
    body = convert_response.json()
    assert body["member"]["name"] == "Test Visitor"
    assert body["visitor"]["follow_up_status"] == "converted"
    assert body["visitor"]["converted_member_id"] == body["member"]["id"]


def test_create_household_and_add_child() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")
    member = client.post(
        "/api/v1/members/",
        json={"first_name": "Parent", "last_name": "Guardian", "phone": "+255 700 000 333"},
        headers=headers,
    ).json()

    household_response = client.post(
        "/api/v1/members/households",
        json={
            "name": "Guardian Household",
            "primary_member_id": member["id"],
            "primary_phone": "+255 700 000 333",
        },
        headers=headers,
    )

    assert household_response.status_code == 201
    household = household_response.json()
    assert household["name"] == "Guardian Household"
    assert household["people"][0]["relationship"] == "primary"

    child_response = client.post(
        f"/api/v1/members/households/{household['id']}/people",
        json={
            "person_type": "child",
            "relationship": "child",
            "first_name": "Little",
            "last_name": "Guardian",
            "can_self_check_in": False,
        },
        headers=headers,
    )

    assert child_response.status_code == 201
    child = child_response.json()
    assert child["name"] == "Little Guardian"
    assert child["can_self_check_in"] is False

    list_response = client.get("/api/v1/members/households", headers=headers)

    assert list_response.status_code == 200
    assert len(list_response.json()["households"][0]["people"]) == 2

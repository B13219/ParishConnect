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
            "address": "123 Parish Road",
            "area": "Kinondoni",
            "gender": "male",
            "date_of_birth": "1995-06-15",
            "marital_status": "married",
            "occupation": "Teacher",
            "preferred_language": "sw",
            "notes": "Choir member",
        },
        headers=headers,
    )

    assert create_response.status_code == 201
    member = create_response.json()
    data = create_response.json()
    assert member["name"] == "Test Member"
    assert member["status"] == "active"
    assert data["address"] == "123 Parish Road"
    assert data["area"] == "Kinondoni"
    assert data["gender"] == "male"
    assert data["date_of_birth"] == "1995-06-15"
    assert data["marital_status"] == "married"
    assert data["occupation"] == "Teacher"
    assert data["preferred_language"] == "sw"
    assert data["notes"] == "Choir member"


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
            "address": "45 Community Street",
            "area": "Ubungo",
            "gender": "female",
            "preferred_language": "sw",
            "notes": "First-time visitor",
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

def test_convert_visitor_blocks_possible_duplicate_member() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    member_response = client.post(
        "/api/v1/members/",
        json={
            "first_name": "Existing",
            "last_name": "Person",
            "phone": "+255700111222",
            "email": "existing.person@example.test",
        },
        headers=headers,
    )

    assert member_response.status_code == 201

    visitor_response = client.post(
        "/api/v1/members/visitors",
        json={
            "first_name": "Existing",
            "last_name": "Person",
            "phone": "+255700111222",
            "email": "existing.person@example.test",
        },
        headers=headers,
    )

    assert visitor_response.status_code == 201

    visitor = visitor_response.json()

    convert_response = client.post(
        f"/api/v1/members/visitors/{visitor['id']}/convert",
        headers=headers,
    )

    assert convert_response.status_code == 409
    assert (
        "possible existing member"
        in convert_response.json()["detail"].lower()
    )

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
def test_member_response_includes_household_summary() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")

    member_response = client.post(
        "/api/v1/members/",
        json={
            "first_name": "Ada",
            "last_name": "Member",
            "phone": "+255700000001",
        },
        headers=headers,
    )

    assert member_response.status_code == 201

    member_id = member_response.json()["id"]

    household_response = client.post(
        "/api/v1/members/households",
        json={
            "name": "Member Household",
            "primary_member_id": member_id,
            "primary_phone": "+255700123456",
        },
        headers=headers,
    )

    assert household_response.status_code == 201

    people = client.get(
        "/api/v1/members/",
        headers=headers,
    ).json()

    member = next(
        item
        for item in people["members"]
        if item["id"] == member_id
    )

    assert member["household"] is not None
    assert member["household"]["name"] == "Member Household"
    assert member["household"]["relationship"] == "primary"
    assert member["household"]["is_primary_member"] is True
    assert member["household"]["primary_phone"] == "+255700123456"
def test_people_csv_export() -> None:
    client, _ = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")

    member_response = client.post(
        "/api/v1/members/",
        json={
            "first_name": "Ada",
            "last_name": "Member",
            "phone": "+255700000001",
            "email": "ada@example.com",
            "address": "123 Parish Road",
            "area": "Kinondoni",
            "gender": "female",
            "date_of_birth": "1995-06-15",
            "marital_status": "married",
            "occupation": "Teacher",
            "preferred_language": "sw",
            "notes": "Choir member",
        },
        headers=receptionist_headers,
    )

    assert member_response.status_code == 201

    visitor_response = client.post(
        "/api/v1/members/visitors",
        json={
            "first_name": "Ben",
            "last_name": "Visitor",
            "address": "45 Community Street",
            "area": "Ubungo",
            "gender": "male",
            "preferred_language": "en",
            "notes": "First-time visitor",
        },
        headers=receptionist_headers,
    )

    assert visitor_response.status_code == 201

    response = client.get(
        "/api/v1/members/export.csv",
        headers=receptionist_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    csv_text = response.text

    assert "record_type" in csv_text
    assert "first_name" in csv_text
    assert "address" in csv_text
    assert "area" in csv_text
    assert "preferred_language" in csv_text

    assert "Ada" in csv_text
    assert "123 Parish Road" in csv_text
    assert "Kinondoni" in csv_text

    assert "Ben" in csv_text
    assert "45 Community Street" in csv_text
    assert "Ubungo" in csv_text
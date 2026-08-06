from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, Member, Visitor
from tests.auth_helpers import add_test_user, auth_headers


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with TestingSessionLocal() as db:
        branch = Branch( name="Test Parish", location="Test City", latitude=-6.7924, longitude=39.2083, attendance_radius_meters=100,
            geofence_enabled=True)
        db.add(branch)
        db.flush()
        add_test_user(db, branch, "Administrator")
        add_test_user(db, branch, "Receptionist")
        add_test_user(db, branch, "Usher")
        add_test_user(db, branch, "Pastor / Leader")
        db.add_all(
            [
                Member(branch_id=branch.id, first_name="Ada", last_name="Member"),
                Visitor(branch_id=branch.id, first_name="Ben", last_name="Visitor"),
            ]
        )
        db.commit()

    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_create_event_and_check_in_member() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")
    people = client.get("/api/v1/members/", headers=receptionist_headers).json()
    member_id = people["members"][0]["id"]

    event_response = client.post(
        "/api/v1/attendance/events",
        json={"name": "Sunday Service", "event_type": "service", "location": "Main Hall"},
        headers=usher_headers,
    )

    assert event_response.status_code == 201
    event = event_response.json()
    assert event["name"] == "Sunday Service"

    check_in_response = client.post(
        "/api/v1/attendance/check-ins",
        json={"event_id": event["id"], "person_type": "member", "person_id": member_id},
        headers=usher_headers,
    )

    assert check_in_response.status_code == 201
    assert check_in_response.json()["person_name"] == "Ada Member"

    duplicate_response = client.post(
        "/api/v1/attendance/check-ins",
        json={"event_id": event["id"], "person_type": "member", "person_id": member_id},
        headers=usher_headers,
    )

    assert duplicate_response.status_code == 409


def test_create_visitor_check_in() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")
    people = client.get("/api/v1/members/", headers=receptionist_headers).json()
    visitor_id = people["visitors"][0]["id"]
    event_id = client.post(
        "/api/v1/attendance/events",
        json={"name": "Youth Meeting"},
        headers=usher_headers,
    ).json()["id"]

    check_in_response = client.post(
        "/api/v1/attendance/check-ins",
        json={"event_id": event_id, "person_type": "visitor", "person_id": visitor_id},
        headers=usher_headers,
    )

    assert check_in_response.status_code == 201
    assert check_in_response.json()["person_name"] == "Ben Visitor"


def test_qr_check_in_member() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")
    people = client.get("/api/v1/members/", headers=receptionist_headers).json()
    member_id = people["members"][0]["id"]
    event = client.post(
        "/api/v1/attendance/events",
        json={"name": "QR Service"},
        headers=usher_headers,
    ).json()

    token_response = client.get(
        f"/api/v1/attendance/events/{event['id']}/qr-token",
        headers=usher_headers,
    )

    assert token_response.status_code == 200
    token = token_response.json()["token"]
    assert token is not None

    check_in_response = client.post(
        "/api/v1/attendance/qr-check-ins",
        json={
            "event_id": event["id"],
            "qr_token": token,
            "person_type": "member",
            "person_id": member_id,
        },
    )

    assert check_in_response.status_code == 201
    assert check_in_response.json()["check_in_method"] == "qr"


def test_qr_code_svg_endpoint() -> None:
    client = build_client()
    usher_headers = auth_headers(client, "Usher")
    event = client.post(
        "/api/v1/attendance/events",
        json={"name": "QR Display"},
        headers=usher_headers,
    ).json()
    response = client.get(
        f"/api/v1/attendance/events/{event['id']}/qr-code.svg",
        params={"data": "http://127.0.0.1:5173/scan.html?event_id=demo&token=demo"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in response.text
    assert "<rect" in response.text


def test_qr_check_in_household_dependent() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")
    people = client.get("/api/v1/members/", headers=receptionist_headers).json()
    member_id = people["members"][0]["id"]
    household = client.post(
        "/api/v1/members/households",
        json={"name": "Ada Household", "primary_member_id": member_id},
        headers=receptionist_headers,
    ).json()
    dependent = client.post(
        f"/api/v1/members/households/{household['id']}/people",
        json={
            "first_name": "Chris",
            "last_name": "Child",
            "person_type": "child",
            "relationship": "child",
            "can_self_check_in": False,
        },
        headers=receptionist_headers,
    ).json()
    event = client.post(
        "/api/v1/attendance/events",
        json={"name": "Family Sunday"},
        headers=usher_headers,
    ).json()
    token = client.get(
        f"/api/v1/attendance/events/{event['id']}/qr-token",
        headers=usher_headers,
    ).json()["token"]

    check_in_response = client.post(
        "/api/v1/attendance/qr-check-ins",
        json={
            "event_id": event["id"],
            "qr_token": token,
            "person_type": "household_person",
            "person_id": dependent["id"],
        },
    )

    assert check_in_response.status_code == 201
    assert check_in_response.json()["person_name"] == "Chris Child"


def test_qr_token_respects_attendance_window() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")
    people = client.get("/api/v1/members/", headers=receptionist_headers).json()
    member_id = people["members"][0]["id"]
    event = client.post(
        "/api/v1/attendance/events",
        json={
            "name": "Future Service",
            "qr_opens_at": "2099-01-01T10:00:00Z",
            "qr_closes_at": "2099-01-01T12:00:00Z",
        },
        headers=usher_headers,
    ).json()

    token_response = client.get(
        f"/api/v1/attendance/events/{event['id']}/qr-token",
        headers=usher_headers,
    )

    assert token_response.status_code == 200
    assert token_response.json()["active"] is False
    assert token_response.json()["token"] is None

    check_in_response = client.post(
        "/api/v1/attendance/qr-check-ins",
        json={
            "event_id": event["id"],
            "qr_token": "pcqr1.invalid.1.token",
            "person_type": "member",
            "person_id": member_id,
        },
    )

    assert check_in_response.status_code == 403

def test_geofence_check_in_member_inside_radius() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")

    people = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()
    member_id = people["members"][0]["id"]

    event = client.post(
        "/api/v1/attendance/events",
        json={"name": "Geofence Service"},
        headers=usher_headers,
    ).json()

    response = client.post(
        "/api/v1/attendance/geofence-check-ins",
        json={
            "event_id": event["id"],
            "person_type": "member",
            "person_id": member_id,
            "latitude": -6.7925,
            "longitude": 39.2084,
            "accuracy_meters": 15,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["check_in_method"] == "geofence"
    assert data["inside_geofence"] is True
    assert data["distance_meters"] < 100


def test_geofence_rejects_location_outside_radius() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")

    people = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()
    member_id = people["members"][0]["id"]

    event = client.post(
        "/api/v1/attendance/events",
        json={"name": "Outside Test"},
        headers=usher_headers,
    ).json()

    response = client.post(
        "/api/v1/attendance/geofence-check-ins",
        json={
            "event_id": event["id"],
            "person_type": "member",
            "person_id": member_id,
            "latitude": -6.8000,
            "longitude": 39.2200,
            "accuracy_meters": 10,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "outside_geofence"


def test_geofence_rejects_low_location_accuracy() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")

    people = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()
    member_id = people["members"][0]["id"]

    event = client.post(
        "/api/v1/attendance/events",
        json={"name": "Accuracy Test"},
        headers=usher_headers,
    ).json()

    response = client.post(
        "/api/v1/attendance/geofence-check-ins",
        json={
            "event_id": event["id"],
            "person_type": "member",
            "person_id": member_id,
            "latitude": -6.7924,
            "longitude": 39.2083,
            "accuracy_meters": 250,
        },
    )

    assert response.status_code == 422


def test_geofence_prevents_duplicate_check_in() -> None:
    client = build_client()
    receptionist_headers = auth_headers(client, "Receptionist")
    usher_headers = auth_headers(client, "Usher")

    people = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()
    member_id = people["members"][0]["id"]

    event = client.post(
        "/api/v1/attendance/events",
        json={"name": "Duplicate Geofence Test"},
        headers=usher_headers,
    ).json()

    payload = {
        "event_id": event["id"],
        "person_type": "member",
        "person_id": member_id,
        "latitude": -6.7924,
        "longitude": 39.2083,
        "accuracy_meters": 10,
    }

    first_response = client.post(
        "/api/v1/attendance/geofence-check-ins",
        json=payload,
    )
    duplicate_response = client.post(
        "/api/v1/attendance/geofence-check-ins",
        json=payload,
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
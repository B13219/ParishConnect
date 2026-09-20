from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, utc_now
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, Event, Member, PrayerRequest, Role
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
        branch = Branch(name="Test Parish", location="Dar es Salaam")
        db.add(branch)
        db.flush()
        add_test_user(db, branch, "Administrator")
        add_test_user(db, branch, "Receptionist")
        add_test_user(db, branch, "Pastor / Leader")
        db.add(Role(name="Member", description="Member portal access"))
        member = Member(
            branch_id=branch.id,
            first_name="Ada",
            last_name="Member",
            phone="+255700000001",
            email="ada.member@test.local",
            membership_status="active",
        )
        db.add(member)
        db.flush()
        event = Event(
            branch_id=branch.id,
            name="Sunday Service",
            event_type="service",
            starts_at=utc_now(),
        )
        prayer = PrayerRequest(
            branch_id=branch.id,
            member_id=member.id,
            category="family",
            body="Please pray for my family.",
            visibility="pastoral_team",
            allow_contact=True,
            status="submitted",
        )
        db.add_all([event, prayer])
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


def member_id(client: TestClient) -> str:
    people = client.get(
        "/api/v1/members/",
        headers=auth_headers(client, "Receptionist"),
    ).json()
    return people["members"][0]["id"]


def test_receptionist_can_provision_disable_and_reset_member_access() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")
    target_member_id = member_id(client)

    provision = client.post(
        f"/api/v1/staff/member-access/{target_member_id}",
        headers=headers,
        json={},
    )
    assert provision.status_code == 201
    data = provision.json()
    assert data["exists"] is True
    assert data["status"] == "active"
    assert data["temporary_password"]

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ada.member@test.local",
            "password": data["temporary_password"],
        },
    )
    assert login.status_code == 200
    assert login.json()["user"]["member_id"] == target_member_id

    disabled = client.patch(
        f"/api/v1/staff/member-access/{target_member_id}",
        headers=headers,
        json={"status": "inactive"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "inactive"

    blocked_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ada.member@test.local",
            "password": data["temporary_password"],
        },
    )
    assert blocked_login.status_code == 401

    client.patch(
        f"/api/v1/staff/member-access/{target_member_id}",
        headers=headers,
        json={"status": "active"},
    )
    reset = client.post(
        f"/api/v1/staff/member-access/{target_member_id}/reset-password",
        headers=headers,
    )
    assert reset.status_code == 200
    assert reset.json()["temporary_password"] != data["temporary_password"]


def test_member_access_rejects_duplicate_activation() -> None:
    client, _ = build_client()
    headers = auth_headers(client, "Receptionist")
    target_member_id = member_id(client)

    first = client.post(
        f"/api/v1/staff/member-access/{target_member_id}",
        headers=headers,
        json={},
    )
    second = client.post(
        f"/api/v1/staff/member-access/{target_member_id}",
        headers=headers,
        json={},
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_pastor_can_manage_prayer_workflow() -> None:
    client, _ = build_client()
    pastor = auth_headers(client, "Pastor / Leader")
    prayers = client.get("/api/v1/staff/prayers", headers=pastor)

    assert prayers.status_code == 200
    prayer = prayers.json()["prayers"][0]
    assert prayer["member_name"] == "Ada Member"

    update = client.patch(
        f"/api/v1/staff/prayers/{prayer['id']}",
        headers=pastor,
        json={
            "status": "answered",
            "pastoral_notes": "Followed up after Sunday service.",
            "assign_to_me": True,
        },
    )
    assert update.status_code == 200
    data = update.json()
    assert data["status"] == "answered"
    assert data["assigned_to"] == "Pastor / Leader User"
    assert data["answered_at"] is not None
    assert data["pastoral_notes"] == "Followed up after Sunday service."


def test_receptionist_cannot_view_pastoral_prayers() -> None:
    client, _ = build_client()
    response = client.get(
        "/api/v1/staff/prayers",
        headers=auth_headers(client, "Receptionist"),
    )
    assert response.status_code == 403


def test_pastor_can_publish_sermon_for_member_portal() -> None:
    client, _ = build_client()
    pastor = auth_headers(client, "Pastor / Leader")
    events = client.get("/api/v1/staff/sermons", headers=pastor).json()["events"]
    event_id = events[0]["event_id"]

    published = client.put(
        f"/api/v1/staff/sermons/{event_id}",
        headers=pastor,
        json={
            "title": "Remain in the Vine",
            "speaker": "Pastor Grace",
            "scripture_reference": "John 15:1-8",
            "summary": "Remain connected to Christ and bear lasting fruit.",
            "published": True,
        },
    )
    assert published.status_code == 200
    assert published.json()["published"] is True

    target_member_id = member_id(client)
    provision = client.post(
        f"/api/v1/staff/member-access/{target_member_id}",
        headers=auth_headers(client, "Receptionist"),
        json={},
    ).json()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ada.member@test.local",
            "password": provision["temporary_password"],
        },
    ).json()
    member_headers = {
        "Authorization": "Bearer " + login["access_token"],
    }

    sermons = client.get(
        "/api/v1/member-portal/sermons",
        headers=member_headers,
    )
    assert sermons.status_code == 200
    assert sermons.json()[0]["title"] == "Remain in the Vine"

    unpublished = client.put(
        f"/api/v1/staff/sermons/{event_id}",
        headers=pastor,
        json={
            "title": "Remain in the Vine",
            "summary": "Remain connected to Christ.",
            "published": False,
        },
    )
    assert unpublished.status_code == 200
    assert unpublished.json()["published"] is False

    sermons_after = client.get(
        "/api/v1/member-portal/sermons",
        headers=member_headers,
    )
    assert sermons_after.json() == []

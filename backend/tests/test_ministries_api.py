from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Branch, Member
from tests.auth_helpers import add_test_user, auth_headers


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(engine)

    with TestingSessionLocal() as db:
        branch = Branch(
            name="Test Parish",
            location="Test City",
        )
        db.add(branch)
        db.flush()

        add_test_user(db, branch, "Administrator")
        add_test_user(db, branch, "Pastor / Leader")
        add_test_user(db, branch, "Receptionist")

        db.add(
            Member(
                branch_id=branch.id,
                first_name="Ada",
                last_name="Member",
            )
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


def test_create_and_list_ministry() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    response = client.post(
        "/api/v1/members/ministries",
        json={
            "name": "Choir",
        },
        headers=receptionist_headers,
    )

    assert response.status_code == 201

    ministry = response.json()

    assert ministry["name"] == "Choir"
    assert ministry["member_count"] == 0

    listing = client.get(
        "/api/v1/members/ministries",
        headers=receptionist_headers,
    )

    assert listing.status_code == 200
    assert len(listing.json()["ministries"]) == 1


def test_add_member_to_ministry() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Youth Ministry"},
        headers=receptionist_headers,
    ).json()

    response = client.post(
        f"/api/v1/members/ministries/{ministry['id']}/members",
        json={
            "member_id": member_id,
            "role": "member",
        },
        headers=receptionist_headers,
    )

    assert response.status_code == 201

    membership = response.json()

    assert membership["member_id"] == member_id
    assert membership["member_name"] == "Ada Member"
    assert membership["role"] == "member"
    assert membership["status"] == "active"


def test_reject_duplicate_ministry_membership() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Ushers"},
        headers=receptionist_headers,
    ).json()

    payload = {
        "member_id": member_id,
        "role": "member",
    }

    first = client.post(
        f"/api/v1/members/ministries/{ministry['id']}/members",
        json=payload,
        headers=receptionist_headers,
    )

    second = client.post(
        f"/api/v1/members/ministries/{ministry['id']}/members",
        json=payload,
        headers=receptionist_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_remove_member_from_ministry() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Media Team"},
        headers=receptionist_headers,
    ).json()

    client.post(
        f"/api/v1/members/ministries/{ministry['id']}/members",
        json={"member_id": member_id},
        headers=receptionist_headers,
    )

    response = client.delete(
        (
            f"/api/v1/members/ministries/"
            f"{ministry['id']}/members/{member_id}"
        ),
        headers=receptionist_headers,
    )

    assert response.status_code == 204

    listing = client.get(
        "/api/v1/members/ministries",
        headers=receptionist_headers,
    ).json()

    assert listing["ministries"][0]["member_count"] == 0


def test_pastor_can_change_ministry_leader() -> None:
    client = build_client()

    pastor_headers = auth_headers(
        client,
        "Pastor / Leader",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=pastor_headers,
    ).json()["members"][0]["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Choir"},
        headers=pastor_headers,
    ).json()

    response = client.patch(
        f"/api/v1/members/ministries/{ministry['id']}",
        json={
            "leader_member_id": member_id,
        },
        headers=pastor_headers,
    )

    assert response.status_code == 200
    assert response.json()["leader_member_id"] == member_id
    assert response.json()["leader_name"] == "Ada Member"


def test_receptionist_cannot_change_ministry_leader() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Choir"},
        headers=receptionist_headers,
    ).json()

    response = client.patch(
        f"/api/v1/members/ministries/{ministry['id']}",
        json={
            "leader_member_id": member_id,
        },
        headers=receptionist_headers,
    )

    assert response.status_code == 403
    
def test_member_profile_includes_ministry_membership() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    members = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"]

    member_id = members[0]["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Choir"},
        headers=receptionist_headers,
    ).json()

    response = client.post(
        f"/api/v1/members/ministries/{ministry['id']}/members",
        json={
            "member_id": member_id,
            "role": "singer",
        },
        headers=receptionist_headers,
    )

    assert response.status_code == 201

    members = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"]

    member = next(
        item
        for item in members
        if item["id"] == member_id
    )

    assert len(member["ministries"]) == 1

    membership = member["ministries"][0]

    assert membership["id"] == ministry["id"]
    assert membership["name"] == "Choir"
    assert membership["role"] == "singer"
    assert membership["is_leader"] is False
    
def test_assigning_ministry_leader_creates_membership() -> None:
    client = build_client()

    pastor_headers = auth_headers(
        client,
        "Pastor / Leader",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=pastor_headers,
    ).json()["members"][0]["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Choir"},
        headers=pastor_headers,
    ).json()

    response = client.patch(
        f"/api/v1/members/ministries/{ministry['id']}",
        json={
            "leader_member_id": member_id,
        },
        headers=pastor_headers,
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["leader_member_id"] == member_id
    assert updated["member_count"] == 1

    membership = updated["members"][0]

    assert membership["member_id"] == member_id
    assert membership["role"] == "leader"
    assert membership["status"] == "active"
    
def test_changing_ministry_leader_demotes_previous_leader() -> None:
    client = build_client()

    pastor_headers = auth_headers(
        client,
        "Pastor / Leader",
    )

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    members = client.get(
        "/api/v1/members/",
        headers=pastor_headers,
    ).json()["members"]

    first_member_id = members[0]["id"]

    second_response = client.post(
        "/api/v1/members/",
        json={
            "first_name": "Grace",
            "last_name": "Leader",
        },
        headers=receptionist_headers,
    )

    assert second_response.status_code == 201

    second = second_response.json()
    second_member_id = second["id"]

    ministry = client.post(
        "/api/v1/members/ministries",
        json={"name": "Choir"},
        headers=pastor_headers,
    ).json()

    first_update = client.patch(
        f"/api/v1/members/ministries/{ministry['id']}",
        json={"leader_member_id": first_member_id},
        headers=pastor_headers,
    )

    assert first_update.status_code == 200

    second_update = client.patch(
        f"/api/v1/members/ministries/{ministry['id']}",
        json={"leader_member_id": second_member_id},
        headers=pastor_headers,
    )

    assert second_update.status_code == 200

    updated = second_update.json()

    roles = {
        item["member_id"]: item["role"]
        for item in updated["members"]
    }

    assert roles[first_member_id] == "member"
    assert roles[second_member_id] == "leader"
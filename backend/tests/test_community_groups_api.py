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

def test_create_and_list_community_group() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    response = client.post(
        "/api/v1/members/communities",
        json={
            "name": "St. Joseph Community",
            "group_type": "local_community",
            "leader_member_id": member_id,
            "area": "Mikocheni",
            "meeting_day": "Wednesday",
            "notes": "Weekly community gathering.",
        },
        headers=receptionist_headers,
    )

    assert response.status_code == 201

    community = response.json()

    assert community["name"] == "St. Joseph Community"
    assert community["leader_member_id"] == member_id
    assert community["leader_name"] == "Ada Member"
    assert community["area"] == "Mikocheni"
    assert community["member_count"] == 0

    listing = client.get(
        "/api/v1/members/communities",
        headers=receptionist_headers,
    )

    assert listing.status_code == 200
    assert len(listing.json()["communities"]) == 1
    
def test_add_member_to_community() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    community = client.post(
        "/api/v1/members/communities",
        json={
            "name": "Upendo Community",
        },
        headers=receptionist_headers,
    ).json()

    response = client.post(
        f"/api/v1/members/communities/{community['id']}/members",
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

    listing = client.get(
        "/api/v1/members/communities",
        headers=receptionist_headers,
    ).json()

    assert listing["communities"][0]["member_count"] == 1
    
def test_reject_duplicate_community_membership() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    community = client.post(
        "/api/v1/members/communities",
        json={"name": "Neema Community"},
        headers=receptionist_headers,
    ).json()

    payload = {
        "member_id": member_id,
        "role": "member",
    }

    first = client.post(
        f"/api/v1/members/communities/{community['id']}/members",
        json=payload,
        headers=receptionist_headers,
    )

    second = client.post(
        f"/api/v1/members/communities/{community['id']}/members",
        json=payload,
        headers=receptionist_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    
def test_remove_member_from_community() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    community = client.post(
        "/api/v1/members/communities",
        json={"name": "Amani Community"},
        headers=receptionist_headers,
    ).json()

    client.post(
        f"/api/v1/members/communities/{community['id']}/members",
        json={"member_id": member_id},
        headers=receptionist_headers,
    )

    response = client.delete(
        (
            f"/api/v1/members/communities/"
            f"{community['id']}/members/{member_id}"
        ),
        headers=receptionist_headers,
    )

    assert response.status_code == 204

    listing = client.get(
        "/api/v1/members/communities",
        headers=receptionist_headers,
    ).json()

    assert listing["communities"][0]["member_count"] == 0
    
def test_member_profile_includes_community_membership() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    people = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()

    member_id = people["members"][0]["id"]

    community = client.post(
        "/api/v1/members/communities",
        json={
            "name": "St. Joseph Community",
            "area": "Mikocheni",
        },
        headers=receptionist_headers,
    ).json()

    response = client.post(
        f"/api/v1/members/communities/{community['id']}/members",
        json={
            "member_id": member_id,
            "role": "member",
        },
        headers=receptionist_headers,
    )

    assert response.status_code == 201

    people = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()

    member = people["members"][0]

    assert len(member["communities"]) == 1

    membership = member["communities"][0]

    assert membership["id"] == community["id"]
    assert membership["name"] == "St. Joseph Community"
    assert membership["area"] == "Mikocheni"
    assert membership["role"] == "member"
    assert membership["status"] == "active"
    
def test_update_community_and_change_leader() -> None:
    client = build_client()

    receptionist_headers = auth_headers(
        client,
        "Receptionist",
    )

    member_id = client.get(
        "/api/v1/members/",
        headers=receptionist_headers,
    ).json()["members"][0]["id"]

    community = client.post(
        "/api/v1/members/communities",
        json={
            "name": "Old Community Name",
            "area": "Old Area",
        },
        headers=receptionist_headers,
    ).json()

    response = client.patch(
        f"/api/v1/members/communities/{community['id']}",
        json={
            "name": "St. Joseph Community",
            "area": "Mikocheni",
            "meeting_day": "Wednesday",
            "leader_member_id": member_id,
        },
        headers=receptionist_headers,
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["name"] == "St. Joseph Community"
    assert updated["area"] == "Mikocheni"
    assert updated["meeting_day"] == "Wednesday"
    assert updated["leader_member_id"] == member_id
    assert updated["leader_name"] == "Ada Member"
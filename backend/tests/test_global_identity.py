from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_password_reset_token, password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import (
    Branch,
    ChurchFollow,
    ChurchMembership,
    Contribution,
    Member,
    Profile,
    Role,
    User,
    UserRole,
)


@pytest.fixture
def identity():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        a, b = Branch(name="Church A"), Branch(name="Church B")
        role = Role(name="Administrator")
        db.add_all([a, b, role])
        db.flush()
        ids = {"a": str(a.id), "b": str(b.id)}
        for name, church in (("a", a), ("b", b)):
            admin = User(
                branch_id=church.id,
                name=f"Admin {name}",
                email=f"{name}@test.local",
                password_hash=password_hash("test-password"),
            )
            db.add(admin)
            db.flush()
            db.add(UserRole(user_id=admin.id, role_id=role.id))
        offline = Member(
            branch_id=a.id, first_name="Ada", last_name="Person", email="ada@test.local"
        )
        other = Member(branch_id=b.id, first_name="Private", last_name="B")
        db.add_all([offline, other])
        db.flush()
        ids.update(offline=str(offline.id), other=str(other.id))
        db.add(
            Contribution(branch_id=b.id, member_id=other.id, amount=99, contribution_type="tithe")
        )
        db.commit()
    app = create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:

        def login(email):
            r = client.post(
                "/api/v1/auth/login", json={"email": email, "password": "test-password"}
            )
            assert r.status_code == 200
            return {"Authorization": "Bearer " + r.json()["access_token"]}

        ids["admin_a"] = login("a@test.local")
        ids["admin_b"] = login("b@test.local")
        yield client, sessions, ids


def register(client, email="ada@test.local"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Person",
            "email": email,
            "password": "long-test-password",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}, response.json()["user"][
        "id"
    ]


def request(client, headers, church):
    r = client.post(f"/api/v1/identity/churches/{church}/requests", headers=headers, json={})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def approve(client, ids, request_id, church="a", member=None):
    payload = {"status": "approved"}
    if member:
        payload["matched_member_id"] = member
    return client.post(
        f"/api/v1/identity/requests/{request_id}/review",
        headers=ids["admin_" + church],
        json=payload,
    )


def test_registration_has_no_church_and_keeps_existing_person(identity):
    client, sessions, _ids = identity
    headers, _user_id = register(client)
    assert client.get("/api/v1/identity/me", headers=headers).json()["email"] == "ada@test.local"
    assert client.get("/api/v1/identity/memberships", headers=headers).json() == []
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.get("/api/v1/member-portal/me", headers=headers).status_code == 403
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Member)) == 2
        assert db.scalar(select(func.count()).select_from(Profile)) == 3
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Person",
            "email": "ADA@TEST.LOCAL",
            "password": "long-test-password",
        },
    )
    assert duplicate.status_code == 409


def test_follows_never_grant_membership_or_staff_access(identity):
    client, sessions, ids = identity
    headers, _ = register(client)
    for church in (ids["a"], ids["b"]):
        for _ in range(2):
            assert (
                client.put(
                    f"/api/v1/identity/churches/{church}/follow", headers=headers
                ).status_code
                == 200
            )
    assert len(client.get("/api/v1/identity/follows", headers=headers).json()) == 2
    assert client.get("/api/v1/identity/memberships", headers=headers).json() == []
    for path in (
        "member-portal/me",
        "member-portal/groups",
        "member-portal/messages",
        "member-portal/events",
        "members/",
        "stewardship/",
        "admin/users",
    ):
        assert client.get("/api/v1/" + path, headers=headers).status_code == 403
    assert (
        client.delete(f"/api/v1/identity/churches/{ids['b']}/follow", headers=headers).status_code
        == 200
    )
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(ChurchFollow)) == 1


def test_review_reuses_offline_member_and_rejects_cross_church(identity):
    client, sessions, ids = identity
    headers, _ = register(client)
    rid = request(client, headers, ids["a"])
    assert (
        client.post(
            f"/api/v1/identity/churches/{ids['a']}/requests", headers=headers, json={}
        ).status_code
        == 409
    )
    assert approve(client, ids, rid, church="b", member=ids["offline"]).status_code == 404
    assert approve(client, ids, rid, member=ids["other"]).status_code == 404
    assert approve(client, ids, rid).status_code == 409  # Never duplicate matching legacy person.
    assert approve(client, ids, rid, member=ids["offline"]).status_code == 200
    assert approve(client, ids, rid, member=ids["offline"]).status_code == 409
    memberships = client.get("/api/v1/identity/memberships", headers=headers).json()
    assert len(memberships) == 1 and not memberships[0]["is_primary"]
    assert memberships[0]["legacy_member_id"] == ids["offline"]
    assert (
        client.put(
            f"/api/v1/identity/memberships/{memberships[0]['id']}/primary", headers=headers
        ).status_code
        == 200
    )
    assert client.get("/api/v1/member-portal/me", headers=headers).status_code == 200
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Member)) == 2


def test_home_switch_preserves_memberships_and_private_giving(identity):
    client, _sessions, ids = identity
    headers, _ = register(client)
    assert (
        approve(client, ids, request(client, headers, ids["a"]), member=ids["offline"]).status_code
        == 200
    )
    assert approve(client, ids, request(client, headers, ids["b"]), church="b").status_code == 200
    memberships = client.get("/api/v1/identity/memberships", headers=headers).json()
    b = next(m for m in memberships if m["church_id"] == ids["b"])
    assert (
        client.put(f"/api/v1/identity/memberships/{b['id']}/primary", headers=headers).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/member-portal/giving",
            headers=headers,
            json={
                "contribution_type": "tithe",
                "amount": "10",
            },
        ).status_code
        == 201
    )
    b_home = client.get("/api/v1/member-portal/me", headers=headers).json()
    assert b_home["profile"]["branch_id"] == ids["b"]
    assert b_home["giving"]["total_amount"] == "10.00"
    a_home = client.get(
        "/api/v1/member-portal/me", headers={**headers, "X-Church-ID": ids["a"]}
    ).json()
    assert a_home["giving"]["total_amount"] == "0.00"
    assert (
        client.get(
            "/api/v1/member-portal/me", headers={**headers, "X-Church-ID": str(uuid4())}
        ).status_code
        == 403
    )
    memberships = client.get("/api/v1/identity/memberships", headers=headers).json()
    assert len(memberships) == 2 and sum(m["is_primary"] for m in memberships) == 1
    assert all(m["status"] == "active" for m in memberships)
    # Suspension in B leaves login and A membership intact, with no legacy fallback.
    assert (
        client.patch(
            f"/api/v1/identity/memberships/{b['id']}",
            headers=ids["admin_b"],
            json={"status": "suspended"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/member-portal/me", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert (
        client.get(
            "/api/v1/member-portal/me", headers={**headers, "X-Church-ID": ids["a"]}
        ).status_code
        == 200
    )


def test_staff_lists_exports_and_writes_are_church_scoped(identity):
    client, sessions, ids = identity
    headers = ids["admin_a"]
    response = client.get("/api/v1/members/", headers=headers)
    assert response.status_code == 200
    assert [m["id"] for m in response.json()["members"]] == [ids["offline"]]
    assert "Private" not in client.get("/api/v1/members/export.csv", headers=headers).text
    assert (
        client.patch(
            f"/api/v1/members/{ids['other']}", headers=headers, json={"first_name": "Stolen"}
        ).status_code
        == 404
    )
    finance = client.get("/api/v1/stewardship/", headers=headers).json()
    assert finance["latest"] == [] and finance["contribution_count"] == 0
    assert finance["by_type"] == []
    assert (
        client.get(f"/api/v1/identity/churches/{ids['b']}/memberships", headers=headers).status_code
        == 403
    )
    created = client.post(
        "/api/v1/members/",
        headers=ids["admin_b"],
        json={"first_name": "New", "last_name": "Offline"},
    )
    assert created.status_code == 201, created.text
    with sessions() as db:
        membership = db.scalar(
            select(ChurchMembership).where(
                ChurchMembership.legacy_member_id == UUID(created.json()["id"])
            )
        )
        assert str(membership.church_id) == ids["b"] and membership.user_id is None


def test_request_cancellation_and_owner_isolation(identity):
    client, _sessions, ids = identity
    headers, _ = register(client)
    stranger, _ = register(client, "stranger@test.local")
    rid = request(client, headers, ids["a"])
    assert (
        client.post(f"/api/v1/identity/requests/{rid}/cancel", headers=stranger).status_code == 404
    )
    assert client.get("/api/v1/identity/requests", headers=stranger).json() == []
    assert (
        client.post(f"/api/v1/identity/requests/{rid}/cancel", headers=headers).status_code == 200
    )
    assert approve(client, ids, rid, member=ids["offline"]).status_code == 409
    assert request(client, headers, ids["a"]) != rid


def test_reset_token_cannot_authenticate(identity):
    client, sessions, _ids = identity
    with sessions() as db:
        token = create_password_reset_token(
            db.scalar(select(User).where(User.email == "a@test.local"))
        )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code
        == 401
    )


def test_payload_cannot_assign_identity_or_privileges(identity):
    client, _sessions, ids = identity
    headers, _ = register(client)
    r = client.post(
        f"/api/v1/identity/churches/{ids['a']}/requests",
        headers=headers,
        json={"status": "approved", "user_id": str(uuid4())},
    )
    assert r.status_code == 422
    rid = request(client, headers, ids["a"])
    assert client.post(
        f"/api/v1/identity/requests/{rid}/review", headers=headers, json={"status": "approved"}
    ).status_code in (403, 404)


def test_second_account_cannot_take_claimed_member(identity):
    client, _sessions, ids = identity
    first, _ = register(client)
    second, _ = register(client, "second@test.local")
    assert (
        approve(client, ids, request(client, first, ids["a"]), member=ids["offline"]).status_code
        == 200
    )
    assert (
        approve(client, ids, request(client, second, ids["a"]), member=ids["offline"]).status_code
        == 409
    )
    assert client.get("/api/v1/identity/memberships", headers=second).json() == []


@pytest.mark.parametrize("state", ["more_info_required", "rejected"])
def test_request_review_states(identity, state):
    client, _sessions, ids = identity
    headers, _ = register(client)
    rid = request(client, headers, ids["a"])
    reviewed = client.post(
        f"/api/v1/identity/requests/{rid}/review",
        headers=ids["admin_a"],
        json={"status": state, "reason": "Please contact the church office."},
    )
    assert reviewed.status_code == 200 and reviewed.json()["status"] == state
    assert client.get("/api/v1/identity/memberships", headers=headers).json() == []
    retry = client.post(f"/api/v1/identity/churches/{ids['a']}/requests", headers=headers, json={})
    assert retry.status_code == (409 if state == "more_info_required" else 201)


def test_self_managed_legacy_account_cannot_be_reset_or_disabled_by_church(identity):
    client, sessions, ids = identity
    with sessions() as db:
        user = User(
            branch_id=UUID(ids["a"]),
            member_id=UUID(ids["offline"]),
            name="Ada Person",
            email="ada@test.local",
            identity_self_managed=True,
            password_hash=password_hash("test-password"),
        )
        db.add(user)
        db.commit()
        uid = str(user.id)
    for path, payload in (
        (f"admin/users/{uid}", {"password": "stolen-password"}),
        (f"staff/member-access/{ids['offline']}", {"status": "inactive"}),
    ):
        assert (
            client.patch("/api/v1/" + path, headers=ids["admin_a"], json=payload).status_code == 403
        )
    assert (
        client.post(
            f"/api/v1/staff/member-access/{ids['offline']}/reset-password", headers=ids["admin_a"]
        ).status_code
        == 403
    )

"""Real migration/RLS, serialized approval and hidden shared-unit checks."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import create_app
from app.models import OrganizationAccessGrant, OrganizationUnit
from tests.test_organization_setup import API, tag_payload
from tests.test_template_governance import GOV, approval, release, review

pytest_plugins = ["tests.test_identity_postgres"]


def test_governance_nonowner_atomic_history_and_hidden_shared_leaf(postgres_identity, monkeypatch):
    owner, runtime, ids = postgres_identity
    sessions = sessionmaker(bind=runtime, autoflush=False)
    app = create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as c:
        headers = {}
        for key in ("a", "b"):
            login = c.post(
                "/api/v1/auth/login",
                json={"email": f"admin-{key}@test.local", "password": "test-password"},
            )
            headers[key] = {"Authorization": "Bearer " + login.json()["access_token"]}
        installed = c.post(API + "/confirm", headers=headers["a"], json=tag_payload(public=True))
        assert installed.status_code == 200, installed.text
        local_id = UUID(installed.json()["local_unit_id"])
        actor_id = c.get("/api/v1/auth/me", headers=headers["a"]).json()["user"]["id"]
        assignment = c.put(
            API + "/assignments",
            headers=headers["a"],
            json={
                "user_id": actor_id,
                "organization_unit_id": str(local_id),
                "position_key": installed.json()["hierarchy_snapshot"]["levels"][-1]["positions"][
                    0
                ]["key"],
                "permission_role": "administrator",
            },
        )
        assert assignment.status_code == 200, assignment.text
        with Session(owner) as db:
            db.add(
                OrganizationAccessGrant(
                    user_id=UUID(actor_id),
                    organization_unit_id=local_id,
                    permission_role="administrator",
                    scope_mode="unit_only",
                )
            )
            db.commit()
        with owner.connect() as conn:
            sensitive = [
                "church_memberships",
                "members",
                "organization_access_grants",
                "organization_office_assignments",
                "branches",
            ]
            before = {
                table: list(conn.execute(text(f"SELECT * FROM {table} ORDER BY id")).mappings())
                for table in sensitive
            }
            actor = conn.scalar(text("SELECT id FROM users WHERE email='admin-a@test.local'"))
        release(monkeypatch)
        data = review(c, headers["a"], target_version=2)
        payload = approval(data, target_version=2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: c.post(GOV + "/approve", headers=headers["a"], json=payload), range(2)
                )
            )
        assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
        assert sorted(r.json()["idempotent"] for r in results) == [False, True]
        assert len(c.get(GOV + "/history", headers=headers["a"]).json()["items"]) == 1
        assert c.get(GOV + "/history", headers=headers["b"]).json()["items"] == []
        assert (
            c.post(
                GOV + "/approve",
                headers={**headers["a"], "X-Vinyrd-Branch-ID": str(ids["b"])},
                json=payload,
            ).status_code
            == 403
        )
        with owner.connect() as conn:
            for table in sensitive:
                assert (
                    list(conn.execute(text(f"SELECT * FROM {table} ORDER BY id")).mappings())
                    == before[table]
                )
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "20260930_0021"
        with runtime.begin() as conn:
            conn.execute(
                text("SELECT set_config('vinyrd.user_id',:actor,true)"), {"actor": str(actor)}
            )
            for field in ["canonical_name", "denomination", "match_key"]:
                with pytest.raises(DBAPIError), conn.begin_nested():
                    conn.execute(
                        text(f"UPDATE organization_units SET {field}='invalid' WHERE id=:id"),
                        {"id": local_id},
                    )
        # Create a private child held by another tenant: local SELECT cannot see
        # it, but the boolean DB guard must still reject publication.
        with Session(owner) as db:
            unit = db.get(OrganizationUnit, local_id)
            db.add(
                OrganizationUnit(
                    denomination=unit.denomination,
                    level_key="custom_child",
                    canonical_name="Private B",
                    normalized_name="private b",
                    parent_id=unit.id,
                    owner_branch_id=UUID(str(ids["b"])),
                    match_key=uuid4().hex,
                    labels_snapshot={"en": "Private"},
                )
            )
            db.commit()
        patch = [{"level_key": "local_church", "labels": {"en": "Changed leaf"}}]
        blocked = review(c, headers["a"], overrides=patch)
        assert blocked["compatibility_status"] == "requires_review"
        assert (
            c.post(
                GOV + "/approve", headers=headers["a"], json=approval(blocked, overrides=patch)
            ).status_code
            == 409
        )
        with runtime.begin() as conn:
            conn.execute(
                text("SELECT set_config('vinyrd.user_id',:actor,true)"), {"actor": str(actor)}
            )
            assert (
                conn.execute(
                    text("UPDATE organization_units SET labels_snapshot='{}' WHERE id=:id"),
                    {"id": local_id},
                ).rowcount
                == 0
            )
            assert (
                conn.scalar(
                    text("SELECT count(*) FROM organization_units WHERE level_key='custom_child'")
                )
                == 0
            )

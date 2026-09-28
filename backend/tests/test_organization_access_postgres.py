"""Real migrated PostgreSQL, non-owner role, HTTP and raw-SQL denial checks."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import OrganizationAccessGrant
from tests.test_organization_access import API, login, seed_scope

pytest_plugins = ["tests.test_identity_postgres"]


def test_hierarchy_nonowner_postgres(postgres_identity):
    owner, runtime, legacy = postgres_identity
    with sessionmaker(bind=owner)() as db:
        ids = seed_scope(db, legacy["a"], legacy["b"])
    with owner.connect() as conn:
        columns = inspect(conn).get_columns("organization_access_grants")
        assert {c["name"] for c in columns} == set(
            Base.metadata.tables["organization_access_grants"].columns.keys()
        )
        assert {i["name"] for i in inspect(conn).get_indexes("organization_access_grants")} >= {
            "ix_org_grant_user_status",
            "ix_org_grant_unit_status",
            "uq_org_grant_equivalent",
        }
        assert conn.scalar(
            text("SELECT relrowsecurity FROM pg_class WHERE relname='organization_access_grants'")
        )
        assert not any(c["default"] for c in columns)
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "20260928_0020"
    sessions = sessionmaker(bind=runtime, autoflush=False)
    app = create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as c:
        district = login(c, "district")
        tree = c.get(API + "/tree", headers=district)
        assert tree.status_code == 200, tree.text
        assert {b["id"] for b in tree.json()["branches"]} == {
            ids["branches"][k] for k in ("a", "b", "c")
        }
        assert ids["units"]["national"] not in {u["id"] for u in tree.json()["units"]}
        headers = {**district, "X-Vinyrd-Branch-ID": ids["branches"]["b"]}
        assert c.get("/api/v1/members/", headers=headers).status_code == 200
        # Legacy hooks insert the offline membership under the verified branch context.
        created = c.post(
            "/api/v1/members/", headers=headers, json={"first_name": "New", "last_name": "Scoped"}
        )
        assert created.status_code in (200, 201), created.text
        assert c.get("/api/v1/network/admin/requests", headers=headers).status_code == 200
        assert (
            c.get(
                "/api/v1/stewardship/",
                headers={**login(c, "pastor"), "X-Vinyrd-Branch-ID": ids["branches"]["b"]},
            ).status_code
            == 403
        )
        assert (
            c.get(
                "/api/v1/members/",
                headers={**login(c, "accountant"), "X-Vinyrd-Branch-ID": ids["branches"]["b"]},
            ).status_code
            == 403
        )
        for key in ("d", "e"):
            assert (
                c.get(
                    "/api/v1/members/",
                    headers={**district, "X-Vinyrd-Branch-ID": ids["branches"][key]},
                ).status_code
                == 403
            )
        payload = {
            "user_id": ids["users"]["target"],
            "organization_unit_id": ids["units"]["section"],
            "permission_role": "administrator",
            "scope_mode": "descendants",
        }
        r = c.post(API + "/grants", headers=district, json=payload)
        assert r.status_code == 201, r.text
        grant = r.json()["id"]
        assert len(c.get(API + "/tree", headers=login(c, "target")).json()["branches"]) == 2
        assert (
            c.post(
                API + "/grants",
                headers=district,
                json={**payload, "organization_unit_id": ids["units"]["national"]},
            ).status_code
            == 403
        )
        r = c.put(
            API + "/grants/" + grant,
            headers=district,
            json={
                "permission_role": "administrator",
                "scope_mode": "descendants",
                "status": "revoked",
            },
        )
        assert r.status_code == 200, r.text
        assert c.get(API + "/tree", headers=login(c, "target")).json()["branches"] == []
        # Public output never gains private authorization metadata.
        public = c.get("/api/v1/network/churches").text
        assert "permission_role" not in public and "granted_by" not in public
    with runtime.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM organization_access_grants")) == 0
        conn.execute(
            text("SELECT set_config('vinyrd.user_id', :id,true)"), {"id": ids["users"]["section"]}
        )
        assert not conn.scalar(
            text("SELECT vinyrd_org_manage(:id,'descendants')"), {"id": ids["units"]["national"]}
        )
        # A forged branch setting alone is insufficient for RLS-protected identity rows.
        conn.execute(
            text("SELECT set_config('vinyrd.branch_id', :id,true)"), {"id": ids["branches"]["e"]}
        )
        assert (
            conn.scalar(
                text("SELECT count(*) FROM church_memberships WHERE church_id=:id"),
                {"id": ids["branches"]["e"]},
            )
            == 0
        )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("""INSERT INTO organization_access_grants
              (id,user_id,organization_unit_id,permission_role,scope_mode,status,granted_by,created_at,updated_at)
              VALUES(gen_random_uuid(),:u,:n,'administrator','descendants','active',:actor,now(),now())"""),
                {
                    "u": ids["users"]["target"],
                    "n": ids["units"]["national"],
                    "actor": ids["users"]["section"],
                },
            )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("SELECT vinyrd_org_covers(:id,:id,'descendants')"),
                {"id": ids["units"]["national"]},
            )
    with sessionmaker(bind=owner)() as db:
        rows = db.scalars(
            select(OrganizationAccessGrant).where(
                OrganizationAccessGrant.user_id == UUID(ids["users"]["target"])
            )
        ).all()
        assert len(rows) == 1 and rows[0].status == "revoked"

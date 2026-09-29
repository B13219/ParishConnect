"""Apply the actual migration chain and exercise organization RLS as a non-owner."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.core.security import password_hash
from app.db.base import Base
from app.db.session import database_connect_args, get_db
from app.main import create_app
from app.models import Branch, Role, User, UserRole
from tests.test_organization_setup import API, tag_payload

pytest_plugins = ["tests.test_identity_postgres"]


def test_organization_migration_runtime_rls_and_concurrent_confirmation(postgres_identity):
    owner, runtime, ids = postgres_identity
    utc_runtime = create_engine(runtime.url, connect_args=database_connect_args(str(runtime.url)))
    try:
        with utc_runtime.connect() as conn:
            assert conn.scalar(text("SHOW timezone")) == "UTC"
    finally:
        utc_runtime.dispose()
    tables = (
        "organization_units",
        "church_organization_configurations",
        "organization_office_assignments",
    )
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "20260928_0020"
        assert (
            conn.scalar(
                text("SELECT count(*) FROM branches WHERE organization_unit_id IS NOT NULL")
            )
            == 0
        )
        for table in tables:
            columns = inspect(conn).get_columns(table)
            assert {c["name"] for c in columns} == set(Base.metadata.tables[table].columns.keys())
            assert conn.scalar(
                text("SELECT relrowsecurity FROM pg_class WHERE relname=:name"), {"name": table}
            )
        actors = {
            key: conn.scalar(
                text("SELECT id FROM users WHERE email=:email"),
                {"email": f"admin-{key}@test.local"},
            )
            for key in ("a", "b")
        }
        before = conn.scalar(text("SELECT count(*) FROM church_memberships"))
    sessions = sessionmaker(bind=runtime, autoflush=False)
    app = create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        headers = {}
        for key in ("a", "b"):
            login = client.post(
                "/api/v1/auth/login",
                json={"email": f"admin-{key}@test.local", "password": "test-password"},
            )
            assert login.status_code == 200, login.text
            headers[key] = {"Authorization": "Bearer " + login.json()["access_token"]}
        preview = client.post(API + "/preview", headers=headers["a"], json={"denomination": "TAG"})
        assert preview.status_code == 200, preview.text
        with owner.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM organization_units")) == 0

        def confirm(_):
            return client.post(API + "/confirm", headers=headers["a"], json=tag_payload())

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(confirm, range(2)))
        assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
        assert responses[0].json() == responses[1].json()
        config_a = responses[0].json()
        response_b = client.post(API + "/confirm", headers=headers["b"], json=tag_payload())
        assert response_b.status_code == 200, response_b.text
        config_b = response_b.json()
        assignment = {
            "user_id": str(actors["a"]),
            "organization_unit_id": config_a["local_unit_id"],
            "position_key": config_a["hierarchy_snapshot"]["levels"][-1]["positions"][0]["key"],
            "permission_role": "administrator",
        }
        saved = client.put(API + "/assignments", headers=headers["a"], json=assignment)
        assert saved.status_code == 200, saved.text
        assert (
            client.put(API + "/assignments", headers=headers["b"], json=assignment).status_code
            == 403
        )
        legacy = client.post(
            "/api/v1/auth/login", json={"email": "ada@legacy.test", "password": "test-password"}
        )
        member_headers = {"Authorization": "Bearer " + legacy.json()["access_token"]}
        assert client.get(API + "/setup", headers=member_headers).status_code == 403
        assert (
            client.put(API + "/assignments", headers=member_headers, json=assignment).status_code
            == 403
        )
        assert client.get("/api/v1/member-portal/me", headers=member_headers).status_code == 200
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM organization_units")) == 10
        assert conn.scalar(text("SELECT count(*) FROM church_memberships")) == before
    with runtime.begin() as conn:
        for table in tables:
            assert conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        conn.execute(text("SELECT set_config('vinyrd.user_id', :u, true)"), {"u": str(actors["a"])})
        assert conn.scalar(text("SELECT count(*) FROM organization_units")) == 5
        assert conn.scalar(text("SELECT count(*) FROM church_organization_configurations")) == 1
        assert conn.scalar(text("SELECT count(*) FROM organization_office_assignments")) == 1
        # Immutable units: even their custodian cannot reparent/rename them via runtime SQL.
        assert (
            conn.execute(text("UPDATE organization_units SET canonical_name='tampered'")).rowcount
            == 0
        )
        assert conn.execute(text("DELETE FROM organization_units")).rowcount == 0
        assert (
            conn.execute(
                text(
                    "UPDATE church_organization_configurations SET denomination='tampered' WHERE branch_id=:b"
                ),
                {"b": ids["b"]},
            ).rowcount
            == 0
        )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("""INSERT INTO organization_units
            SELECT :new, denomination, level_key, canonical_name, normalized_name, parent_id,
            country, region, city, localized_names, labels_snapshot, status, is_managed,
            is_published, :foreign_branch, match_key, created_at, updated_at
            FROM organization_units LIMIT 1"""),
                {"new": uuid4(), "foreign_branch": ids["b"]},
            )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("UPDATE organization_office_assignments SET organization_unit_id=:unit"),
                {"unit": config_b["local_unit_id"]},
            )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("UPDATE organization_office_assignments SET user_id=:u"), {"u": actors["b"]}
            )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("UPDATE organization_office_assignments SET organization_unit_id=:unit"),
                {"unit": config_a["organization_path"][0]["id"]},
            )
    # Neither another tenant nor a regular member can see/change private assignment rows.
    for actor in (actors["b"], ids["user"]):
        with runtime.begin() as conn:
            conn.execute(text("SELECT set_config('vinyrd.user_id', :u, true)"), {"u": str(actor)})
            assert conn.scalar(text("SELECT count(*) FROM organization_office_assignments")) == 0
            assert (
                conn.execute(
                    text(
                        "UPDATE organization_office_assignments SET permission_role='administrator'"
                    )
                ).rowcount
                == 0
            )


def test_public_parent_reuse_and_projection_with_nonowner_role(postgres_identity):
    owner, runtime, _ = postgres_identity
    owner_sessions = sessionmaker(bind=owner)
    with owner_sessions() as db:
        role = db.scalar(select(Role).where(Role.name == "Administrator"))
        for suffix in ("national", "local"):
            branch = Branch(name="Organization " + suffix)
            db.add(branch)
            db.flush()
            user = User(
                branch_id=branch.id,
                name="Organization admin",
                email=suffix + "@organization.test",
                password_hash=password_hash("test-password"),
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
    sessions = sessionmaker(bind=runtime, autoflush=False)
    app = create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        configs, headers = {}, {}
        for suffix in ("national", "local"):
            login = client.post(
                "/api/v1/auth/login",
                json={"email": suffix + "@organization.test", "password": "test-password"},
            )
            headers[suffix] = {"Authorization": "Bearer " + login.json()["access_token"]}
            payload = tag_payload(public=True)
            if suffix == "national":
                payload["organization_level"] = "national_church"
                payload["units"] = payload["units"][:1]
            response = client.post(API + "/confirm", headers=headers[suffix], json=payload)
            assert response.status_code == 200, response.text
            configs[suffix] = response.json()
        assert (
            configs["local"]["organization_path"][0]["id"] == configs["national"]["local_unit_id"]
        )
        assert (
            client.put(
                "/api/v1/network/admin/profile",
                headers=headers["local"],
                json={
                    "name": "TAG Mikocheni",
                    "country": "TZ",
                    "denomination": "TAG",
                    "is_published": True,
                },
            ).status_code
            == 200
        )
        public = client.get("/api/v1/network/churches/" + configs["local"]["branch_id"]).json()
        assert len(public["organization_path"]) == 5
        assert all(
            set(unit) == {"level_key", "name", "labels", "presentation"}
            for unit in public["organization_path"]
        )
        assert client.get(API + "/assignments", headers=headers["local"]).json()["items"] == []
    with runtime.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM organization_units")) == 5
        assert conn.scalar(text("SELECT count(*) FROM church_organization_configurations")) == 0
        assert conn.scalar(text("SELECT count(*) FROM organization_office_assignments")) == 0

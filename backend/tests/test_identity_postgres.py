"""Real migration/RLS tests. Set VINYRD_TEST_POSTGRES_URL to a disposable local cluster.

Creates and removes only a uniquely named test database and role. Never uses the
application DATABASE_URL or production settings to select the target cluster.
"""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.core.security import password_hash
from app.db.session import get_db
from app.main import create_app


@pytest.fixture(scope="module")
def postgres_identity():
    configured = os.environ.get("VINYRD_TEST_POSTGRES_URL")
    if not configured:
        pytest.skip("Set VINYRD_TEST_POSTGRES_URL to run PostgreSQL migration/RLS tests")
    url = make_url(configured)
    if url.host not in ("localhost", "127.0.0.1"):
        pytest.fail(
            "Identity integration tests require an explicitly local disposable PostgreSQL cluster"
        )
    name = "vinyrd_identity_" + uuid4().hex
    role = "vinyrd_runtime_" + uuid4().hex
    runtime_password = uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
        conn.execute(
            text(
                f"CREATE ROLE \"{role}\" LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{runtime_password}'"
            )
        )
    target = url.set(database=name)
    owner = create_engine(target)
    env = {**os.environ, "PARISHCONNECT_DATABASE_URL": target.render_as_string(hide_password=False)}
    root = Path(__file__).resolve().parents[1]

    def migrate(revision):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            env=env,
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        migrate("20260921_0014")
        metadata = MetaData()
        metadata.reflect(owner)
        now = datetime.now(UTC)

        def insert(conn, table, **values):
            # Frozen legacy rows, inserted without current ORM compatibility hooks.
            values.setdefault("id", uuid4())
            for column in metadata.tables[table].columns:
                if column.name in values or column.nullable:
                    continue
                if column.name in (
                    "created_at",
                    "updated_at",
                    "received_at",
                    "checked_in_at",
                    "starts_at",
                ):
                    values[column.name] = now
                elif column.type.python_type is bool:
                    values[column.name] = False
                elif column.type.python_type is int:
                    values[column.name] = 60
                elif column.type.python_type is str:
                    values[column.name] = (
                        "test"[: column.type.length] if column.type.length else "test"
                    )
            conn.execute(metadata.tables[table].insert().values(**values))
            return values["id"]

        with owner.begin() as conn:
            a = insert(conn, "branches", name="Legacy A")
            b = insert(conn, "branches", name="Legacy B")
            member_a = insert(
                conn,
                "members",
                branch_id=a,
                first_name="Ada",
                last_name="Legacy",
                email="ada@legacy.test",
                membership_status="active",
            )
            member_b = insert(
                conn,
                "members",
                branch_id=b,
                first_name="Offline",
                last_name="B",
                membership_status="active",
            )
            user = insert(
                conn,
                "users",
                branch_id=a,
                member_id=member_a,
                name="Ada Legacy",
                email="ada@legacy.test",
                status="active",
                password_hash=password_hash("test-password"),
            )
            admin_role = insert(conn, "roles", name="Administrator")
            for church, email in ((a, "admin-a@test.local"), (b, "admin-b@test.local")):
                staff = insert(
                    conn,
                    "users",
                    branch_id=church,
                    name="Admin",
                    email=email,
                    status="active",
                    password_hash=password_hash("test-password"),
                )
                conn.execute(
                    metadata.tables["user_roles"].insert().values(user_id=staff, role_id=admin_role)
                )
            insert(
                conn,
                "contributions",
                branch_id=a,
                member_id=member_a,
                amount=123,
                contribution_type="tithe",
            )
            event_id = insert(conn, "events", branch_id=a, name="Legacy service")
            insert(
                conn,
                "attendance_records",
                branch_id=a,
                event_id=event_id,
                member_id=member_a,
                person_type="member",
            )
            group = insert(conn, "community_groups", branch_id=a, name="Legacy group")
            insert(
                conn, "community_group_memberships", community_group_id=group, member_id=member_a
            )
            before = {
                table.name: [dict(row) for row in conn.execute(select(table)).mappings()]
                for table in metadata.sorted_tables
                if table.name != "alembic_version"
            }
        migrate("head")
        with owner.begin() as conn:
            # Reading with the old reflected column set proves preservation of
            # every legacy value (including password hashes and relationship IDs).
            for table in metadata.sorted_tables:
                if table.name != "alembic_version":
                    after = [dict(row) for row in conn.execute(select(table)).mappings()]
                    assert after == before[table.name], table.name
            conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            conn.execute(
                text(
                    f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"'
                )
            )
            policies = conn.execute(text("SELECT tablename FROM pg_policies")).scalars().all()
            assert {
                "profiles",
                "church_memberships",
                "membership_requests",
                "church_follows",
            } <= set(policies)
        runtime = create_engine(target.set(username=role, password=runtime_password))
        yield (
            owner,
            runtime,
            {"a": a, "b": b, "member_a": member_a, "member_b": member_b, "user": user},
        )
        runtime.dispose()
    finally:
        owner.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
            conn.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()


def test_backfill_and_nonowner_rls(postgres_identity):
    owner, runtime, ids = postgres_identity
    with owner.connect() as conn:
        rows = (
            conn.execute(text("SELECT * FROM church_memberships ORDER BY user_id NULLS LAST"))
            .mappings()
            .all()
        )
        assert len(rows) == 2
        assert rows[0]["user_id"] == ids["user"] and rows[0]["is_primary"]
        assert rows[1]["user_id"] is None
    with runtime.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM profiles")) == 0
        assert conn.scalar(text("SELECT count(*) FROM church_memberships")) == 0
        conn.execute(text("SELECT set_config('vinyrd.user_id', :u, true)"), {"u": str(ids["user"])})
        assert conn.scalar(text("SELECT count(*) FROM profiles")) == 1
        assert conn.scalar(text("SELECT count(*) FROM church_memberships")) == 1
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(text("UPDATE church_memberships SET status='suspended', is_primary=false"))
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("""INSERT INTO church_follows
                (id,user_id,church_id,created_at,updated_at) VALUES (:id,:u,:c,now(),now())"""),
                {"id": uuid4(), "u": uuid4(), "c": ids["a"]},
            )
        request_id = uuid4()
        conn.execute(
            text("""INSERT INTO membership_requests
            (id,user_id,church_id,status,created_at,updated_at)
            VALUES (:id,:u,:c,'pending',now(),now())"""),
            {"id": request_id, "u": ids["user"], "c": ids["b"]},
        )
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(
                text("UPDATE membership_requests SET status='approved' WHERE id=:id"),
                {"id": request_id},
            )
        conn.execute(
            text("UPDATE membership_requests SET status='cancelled' WHERE id=:id"),
            {"id": request_id},
        )
    with runtime.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM profiles")) == 0  # pooled context cleared


def test_api_with_rls_runtime_role(postgres_identity):
    _owner, runtime, ids = postgres_identity
    sessions = sessionmaker(bind=runtime, autoflush=False)
    app = create_app()

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:

        def login(email, password="test-password"):
            response = client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
            assert response.status_code == 200, response.text
            return {"Authorization": "Bearer " + response.json()["access_token"]}

        old = login("ada@legacy.test")
        assert client.get("/api/v1/member-portal/me", headers=old).status_code == 200
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Global",
                "last_name": "Person",
                "email": "global@test.local",
                "password": "long-test-password",
            },
        )
        assert registered.status_code == 201, registered.text
        headers = {"Authorization": "Bearer " + registered.json()["access_token"]}
        assert client.get("/api/v1/identity/me", headers=headers).status_code == 200
        for key in ("a", "b"):
            staff = login(f"admin-{key}@test.local")
            request = client.post(
                f"/api/v1/identity/churches/{ids[key]}/requests", headers=headers, json={}
            )
            assert request.status_code == 201, request.text
            response = client.post(
                f"/api/v1/identity/requests/{request.json()['id']}/review",
                headers=staff,
                json={"status": "approved"},
            )
            assert response.status_code == 200, response.text
        memberships = client.get("/api/v1/identity/memberships", headers=headers).json()
        assert len(memberships) == 2
        for membership in memberships:
            response = client.put(
                f"/api/v1/identity/memberships/{membership['id']}/primary", headers=headers
            )
            assert response.status_code == 200, response.text
        assert (
            sum(
                m["is_primary"]
                for m in client.get("/api/v1/identity/memberships", headers=headers).json()
            )
            == 1
        )

        def switch_home(membership):
            return client.put(
                f"/api/v1/identity/memberships/{membership['id']}/primary", headers=headers
            ).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(switch_home, memberships * 3)) == [200] * 6
        assert (
            sum(
                m["is_primary"]
                for m in client.get("/api/v1/identity/memberships", headers=headers).json()
            )
            == 1
        )
        staff_a = login("admin-a@test.local")
        data = client.get(
            f"/api/v1/identity/churches/{ids['a']}/memberships", headers=staff_a
        ).json()
        assert all(m["church_id"] == str(ids["a"]) for m in data)
        assert (
            client.get("/api/v1/identity/me", headers=staff_a).json()["email"]
            == "admin-a@test.local"
        )

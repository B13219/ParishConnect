"""Verify actual privilege provisioning, exhaustive backups and restored HTTP startup."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from app.db.session import database_connect_args
from app.scripts.start_backend import runtime_environment
from app.scripts.verify_backup_restore import snapshot
from app.services.database_privileges import provision, runtime_issues
from tests.test_organization_access import seed_scope

pytest_plugins = ["tests.test_identity_postgres"]


def test_runtime_environment_removes_operator_credentials():
    source = {
        "PARISHCONNECT_DATABASE_URL": "runtime",
        "PARISHCONNECT_MIGRATION_DATABASE_URL": "owner",
        "PARISHCONNECT_BACKUP_DATABASE_URL": "backup",
        "PARISHCONNECT_RESTORE_DATABASE_URL": "restore",
        "VINYRD_ALLOW_AUTHORITY_BOOTSTRAP": "true",
        "VINYRD_ALLOW_AUTHORITY_RECOVERY": "true",
        "PGPASSWORD": "secret",
    }
    assert runtime_environment(source) == {"PARISHCONNECT_DATABASE_URL": "runtime"}


def test_minimum_runtime_and_backup_restore(postgres_identity, tmp_path):
    from sqlalchemy import create_engine

    owner, runtime, ids = postgres_identity
    with sessionmaker(bind=owner)() as db:
        seed_scope(db, ids["a"], ids["b"])
    backup_role = "vinyrd_backup_" + uuid4().hex
    restore_role = "vinyrd_restore_" + uuid4().hex
    password = uuid4().hex
    with owner.begin() as connection:
        connection.execute(
            text(
                f"CREATE ROLE {backup_role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS PASSWORD '{password}'"
            )
        )
        connection.execute(
            text(
                f"CREATE ROLE {restore_role} LOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD '{password}'"
            )
        )
        provision(connection, runtime.url.username, backup_role)
    checked = create_engine(runtime.url, connect_args=database_connect_args(str(runtime.url)))
    try:
        with checked.connect() as connection:
            assert runtime_issues(connection) == []
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(text("CREATE TABLE public.runtime_must_not_create(id int)"))
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(text("SELECT vinyrd_org_covers(NULL,NULL,'unit_only')"))
        with pytest.raises(DBAPIError):
            snapshot(runtime.url.render_as_string(hide_password=False))
        with owner.connect() as connection:
            assert runtime_issues(connection)
        if not shutil.which("pg_dump"):
            pytest.skip("PostgreSQL client tools required for restore integration")
        env = {
            **os.environ,
            "PARISHCONNECT_DATABASE_URL": runtime.url.render_as_string(hide_password=False),
            "PARISHCONNECT_MIGRATION_DATABASE_URL": "",
            "PARISHCONNECT_BACKUP_DATABASE_URL": owner.url.set(
                username=backup_role, password=password
            ).render_as_string(hide_password=False),
            "PARISHCONNECT_RESTORE_DATABASE_URL": owner.url.set(
                username=restore_role, password=password, database="postgres"
            ).render_as_string(hide_password=False),
            "PYTHONIOENCODING": "utf-8",
        }
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.scripts.verify_backup_restore",
                "--backup-path",
                str(tmp_path / "verified.dump"),
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Verified tables: 31" in completed.stdout
        assert "organization grants retained: 9" in completed.stdout
        assert "Restored application startup" in completed.stdout
    finally:
        checked.dispose()
        with owner.begin() as connection:
            connection.execute(text(f"DROP OWNED BY {backup_role}"))
            connection.execute(text(f"DROP ROLE {backup_role}"))
            connection.execute(text(f"DROP ROLE {restore_role}"))

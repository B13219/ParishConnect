"""Verify an exhaustive backup with explicit backup, restore and runtime credentials."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.settings import settings
from app.db.session import database_connect_args
from app.scripts.start_backend import runtime_environment
from app.services.database_privileges import provision, runtime_permissions


def command_env(url):
    env = runtime_environment(os.environ)
    env.update(PGTZ="UTC", PGOPTIONS="-c timezone=UTC -c row_security=off")
    if url.password:
        env["PGPASSWORD"] = url.password
    return env


def pg_args(url):
    args = []
    if url.host:
        args.extend(["-h", url.host])
    if url.port:
        args.extend(["-p", str(url.port)])
    if url.username:
        args.extend(["-U", url.username])
    return args


def snapshot(database_url):
    engine = create_engine(
        database_url, connect_args={"options": "-c timezone=UTC -c row_security=off"}
    )
    try:
        names = set(inspect(engine).get_table_names()) - {"alembic_version"}
        if not set(runtime_permissions()) <= names:
            raise RuntimeError("Backup source omits required application tables.")
        with engine.connect() as connection:
            quote = connection.dialect.identifier_preparer.quote
            counts = {
                name: int(connection.scalar(text(f"SELECT count(*) FROM public.{quote(name)}")))
                for name in sorted(names)
            }
            grants = list(
                connection.execute(
                    text("SELECT * FROM organization_access_grants ORDER BY id")
                ).mappings()
            )
            head = connection.scalar(text("SELECT version_num FROM alembic_version"))
            governance = {
                table: list(connection.execute(text(f"SELECT * FROM {table} ORDER BY {key}")).mappings())
                for table, key in (("church_organization_configurations", "branch_id"),
                                   ("organization_units", "id"))
            }
            governance["approvals"] = list(connection.execute(text(
                "SELECT * FROM audit_logs WHERE action='organization.template_approved' ORDER BY id"
            )).mappings())
            return counts, grants, head, governance
    finally:
        engine.dispose()


def row_counts(database_url):
    return snapshot(database_url)[0]


def restored_startup(runtime_url):
    # Only the newly created restore database is passed to the HTTP worker.
    env = runtime_environment(os.environ)
    env.update(
        PARISHCONNECT_DATABASE_URL=runtime_url, PARISHCONNECT_ENVIRONMENT="staging", PGTZ="UTC"
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env["PORT"] = str(port)
    with tempfile.TemporaryFile(mode="w+b") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.scripts.start_backend"],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    log.seek(0)
                    diagnostic = log.read().decode("utf-8", errors="replace")[-3000:]
                    diagnostic = diagnostic.replace(runtime_url, "[runtime database]")
                    password = make_url(runtime_url).password
                    if password:
                        diagnostic = diagnostic.replace(password, "[redacted]")
                    raise RuntimeError("Restored runtime failed startup: " + diagnostic)
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        if response.status == 200:
                            print(
                                "Restored application startup, runtime privileges, UTC, migration head and health verified."
                            )
                            return
                except (URLError, TimeoutError):
                    pass
                time.sleep(0.1)
            raise RuntimeError("Restored application health check timed out.")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-path", default="")
    args = parser.parse_args()
    for executable in ("pg_dump", "pg_restore", "createdb", "dropdb"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"{executable} is required.")
    if not settings.backup_database_url or not settings.restore_database_url:
        raise RuntimeError(
            "Explicit BACKUP_DATABASE_URL and RESTORE_DATABASE_URL are required; runtime credentials are never used for restore."
        )
    runtime = make_url(settings.database_url)
    backup = make_url(settings.backup_database_url)
    restore = make_url(settings.restore_database_url)
    if any(url.get_backend_name() != "postgresql" for url in (runtime, backup, restore)):
        raise RuntimeError("PostgreSQL connections are required.")
    if (runtime.host, runtime.port, runtime.database) != (
        backup.host,
        backup.port,
        backup.database,
    ):
        raise RuntimeError("Backup credential must target the runtime source database.")
    if runtime.username in (backup.username, restore.username):
        raise RuntimeError("Use separate operational credentials, never the runtime login.")
    path = (
        Path(args.backup_path)
        if args.backup_path
        else Path(tempfile.gettempdir()) / "vinyrd-pilot-backup.dump"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    original = snapshot(settings.backup_database_url)
    subprocess.run(
        ["pg_dump", *pg_args(backup), "-Fc", "-f", str(path), backup.database],
        env=command_env(backup),
        check=True,
    )
    name = "vinyrd_restore_verify_" + uuid4().hex
    restored = restore.set(database=name)
    created = False
    try:
        subprocess.run(
            [
                "createdb",
                *pg_args(restore),
                "--maintenance-db",
                restore.database or "postgres",
                name,
            ],
            env=command_env(restore),
            check=True,
        )
        created = True
        subprocess.run(
            [
                "pg_restore",
                *pg_args(restore),
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "-d",
                name,
                str(path),
            ],
            env=command_env(restore),
            check=True,
        )
        result = snapshot(restored.render_as_string(hide_password=False))
        if result != original:
            raise RuntimeError(
                "Restore differs in table counts, grants, governance snapshots/history or migration head."
            )
        engine = create_engine(restored, connect_args=database_connect_args(str(restored)))
        try:
            with engine.begin() as connection:
                provision(connection, runtime.username)
        finally:
            engine.dispose()
        runtime_restored = runtime.set(host=restore.host, port=restore.port, database=name)
        restored_startup(runtime_restored.render_as_string(hide_password=False))
    finally:
        if created:
            subprocess.run(
                [
                    "dropdb",
                    *pg_args(restore),
                    "--maintenance-db",
                    restore.database or "postgres",
                    name,
                ],
                env=command_env(restore),
                check=True,
            )
    print(f"Vinyrd backup verified: {path}")
    print(
        f"Verified tables: {len(original[0])}; organization grants retained: {len(original[1])}; migration head: {original[2]}"
    )
    print(f"Governance snapshots, unit labels and {len(original[3]['approvals'])} approvals restored exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

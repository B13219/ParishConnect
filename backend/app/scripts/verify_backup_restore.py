from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from app.core.settings import settings


def command_env(url: URL) -> dict[str, str]:
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password
    return env


def pg_args(url: URL) -> list[str]:
    args: list[str] = []
    if url.host:
        args.extend(["-h", url.host])
    if url.port:
        args.extend(["-p", str(url.port)])
    if url.username:
        args.extend(["-U", url.username])
    return args


def row_counts(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        table_names = [
            name
            for name in inspect(engine).get_table_names()
            if name != "alembic_version"
        ]
        with engine.connect() as connection:
            return {
                name: int(
                    connection.execute(
                        text(f'SELECT COUNT(*) FROM "{name}"')
                    ).scalar_one()
                )
                for name in sorted(table_names)
            }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a PostgreSQL Vinyrd backup and verify it by restoring it."
    )
    parser.add_argument("--backup-path", default="")
    args = parser.parse_args()

    for executable in ("pg_dump", "pg_restore", "createdb", "dropdb"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"{executable} is required for backup verification.")

    url = make_url(settings.database_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Backup verification requires PostgreSQL.")
    if not url.database:
        raise RuntimeError("Database name is missing.")

    backup_path = (
        Path(args.backup_path)
        if args.backup_path
        else Path(tempfile.gettempdir()) / "vinyrd-pilot-backup.dump"
    )
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    env = command_env(url)
    common = pg_args(url)
    subprocess.run(
        ["pg_dump", *common, "-Fc", "-f", str(backup_path), url.database],
        check=True,
        env=env,
    )

    original_counts = row_counts(settings.database_url)
    restore_database = f"{url.database}_restore_verify_{os.getpid()}"
    restore_url = url.set(database=restore_database)

    try:
        subprocess.run(
            ["createdb", *common, restore_database],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                "pg_restore",
                *common,
                "--no-owner",
                "--no-privileges",
                "-d",
                restore_database,
                str(backup_path),
            ],
            check=True,
            env=env,
        )
        restored_counts = row_counts(restore_url.render_as_string(hide_password=False))
        if original_counts != restored_counts:
            raise RuntimeError(
                "Backup restore row-count verification failed: "
                f"original={original_counts}, restored={restored_counts}"
            )
    finally:
        subprocess.run(
            ["dropdb", *common, "--if-exists", restore_database],
            check=True,
            env=env,
        )

    print(f"Vinyrd backup verified: {backup_path}")
    print(f"Verified tables: {len(original_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Production entrypoint: optional owner migration, then verified least-privilege HTTP."""

import os
import subprocess
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.settings import settings
from app.db.session import database_connect_args
from app.services.database_privileges import provision, runtime_issues

OPERATOR_KEYS = (
    "PARISHCONNECT_MIGRATION_DATABASE_URL",
    "PARISHCONNECT_BACKUP_DATABASE_URL",
    "PARISHCONNECT_RESTORE_DATABASE_URL",
    "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD",
    "VINYRD_ALLOW_AUTHORITY_BOOTSTRAP",
    "VINYRD_ALLOW_AUTHORITY_RECOVERY",
    "PGPASSWORD",
    "PGOPTIONS",
)


def runtime_environment(source):
    return {key: value for key, value in source.items() if key not in OPERATOR_KEYS}


def validate_runtime(url):
    engine = create_engine(url, connect_args=database_connect_args(url))
    try:
        with engine.connect() as connection:
            issues = runtime_issues(connection)
            expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            if connection.scalar(text("SELECT version_num FROM alembic_version")) != expected:
                issues.append("Runtime database is not at the current migration head.")
            if issues:
                raise RuntimeError("Runtime database is not ready: " + " ".join(issues))
    finally:
        engine.dispose()


def main():
    if settings.migration_database_url:
        operational = {
            **os.environ,
            "PARISHCONNECT_DATABASE_URL": settings.migration_database_url,
            "PGTZ": "UTC",
        }
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], env=operational, check=True
        )
        subprocess.run(
            [sys.executable, "-m", "app.scripts.bootstrap_admin"], env=operational, check=True
        )
        engine = create_engine(
            settings.migration_database_url,
            connect_args=database_connect_args(settings.migration_database_url),
        )
        try:
            with engine.begin() as connection:
                provision(connection, make_url(settings.database_url).username)
        finally:
            engine.dispose()
    if settings.environment.lower() in {"production", "staging"}:
        validate_runtime(settings.database_url)
    environment = runtime_environment(os.environ)
    environment["PGTZ"] = "UTC"
    if os.name == "nt":
        # Windows execve does not preserve the monitored process lifetime.
        # Run the worker in this process after clearing operator configuration.
        os.environ.clear()
        os.environ.update(environment)
        for name in (
            "migration_database_url",
            "backup_database_url",
            "restore_database_url",
            "bootstrap_admin_password",
        ):
            setattr(settings, name, "")
        import uvicorn

        uvicorn.run("app.main:app", host="0.0.0.0", port=int(environment.get("PORT", "8000")))
        return
    os.execve(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.environ.get("PORT", "8000"),
        ],
        environment,
    )


if __name__ == "__main__":
    main()

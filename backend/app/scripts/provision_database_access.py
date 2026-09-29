"""Provision existing runtime/backup roles using the migration-owner credential."""

import argparse

from sqlalchemy import create_engine

from app.core.settings import settings
from app.db.session import database_connect_args
from app.services.database_privileges import provision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-role", required=True)
    parser.add_argument("--backup-role")
    args = parser.parse_args()
    url = settings.migration_database_url or settings.database_url
    engine = create_engine(url, connect_args=database_connect_args(url))
    try:
        with engine.begin() as connection:
            provision(connection, args.runtime_role, args.backup_role)
        print("Runtime/backup privileges provisioned; no roles or credentials created.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

"""One-shot, deployment-owner authority initialization or controlled recovery.

No HTTP route and no persistent enabled mode. Verify governance and local admin
identity before using this operator-only command. Permission role is Administrator.
"""

import argparse
import os
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import database_connect_args
from app.services.authority_bootstrap import bootstrap_authority


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-user-id", type=UUID, required=True)
    parser.add_argument("--user-id", type=UUID, required=True)
    parser.add_argument("--organization-unit-id", type=UUID, required=True)
    parser.add_argument("--permission-role", choices=["administrator"], required=True)
    parser.add_argument("--scope-mode", choices=["descendants"], required=True)
    parser.add_argument("--authority-reference", required=True)
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    flag = "VINYRD_ALLOW_AUTHORITY_RECOVERY" if args.recover else "VINYRD_ALLOW_AUTHORITY_BOOTSTRAP"
    # Consume the operator guard in this process; never propagate it to HTTP workers.
    enabled = os.environ.pop(flag, "false").lower() == "true"
    url = settings.migration_database_url or settings.database_url
    engine = create_engine(url, connect_args=database_connect_args(url))
    try:
        with Session(engine) as db:
            try:
                grant, created = bootstrap_authority(
                    db,
                    actor_id=args.actor_user_id,
                    target_id=args.user_id,
                    root_id=args.organization_unit_id,
                    reason=args.authority_reference,
                    enabled=enabled,
                    recovery=args.recover,
                )
                db.commit()
                print(
                    f"Authority {'recorded' if created else 'already recorded'}: {grant.id}. No office or membership changed."
                )
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

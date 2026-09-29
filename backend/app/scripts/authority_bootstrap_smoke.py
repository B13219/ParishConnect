"""Exercise one-shot authority CLI on the existing disposable organization smoke tree."""

import os
import subprocess
import sys
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.session import engine
from app.models import OrganizationUnit, User


def main():
    if os.getenv("VINYRD_SMOKE_DISPOSABLE_DATABASE") != "1" or engine.url.host not in (
        "localhost",
        "127.0.0.1",
    ):
        raise RuntimeError("Requires an explicitly disposable loopback database.")
    with Session(engine) as db:
        actor = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email))
        root = db.scalar(select(OrganizationUnit).where(OrganizationUnit.parent_id.is_(None)))
        assert actor and root
        counts = lambda: tuple(
            db.scalar(text("SELECT count(*) FROM " + table))
            for table in ("church_memberships", "organization_office_assignments")
        )
        before = counts()
        command = [
            sys.executable,
            "-m",
            "app.scripts.provision_organization_grant",
            "--actor-user-id",
            str(actor.id),
            "--user-id",
            str(actor.id),
            "--organization-unit-id",
            str(root.id),
            "--permission-role",
            "administrator",
            "--scope-mode",
            "descendants",
            "--authority-reference",
            "disposable-ci-verified-initial-authority",
        ]
        env = {**os.environ, "VINYRD_ALLOW_AUTHORITY_BOOTSTRAP": "false"}
        assert subprocess.run(command, env=env, capture_output=True, check=False).returncode != 0
        env["VINYRD_ALLOW_AUTHORITY_BOOTSTRAP"] = "true"
        first = subprocess.run(command, env=env, check=True, capture_output=True, text=True)
        second = subprocess.run(command, env=env, check=True, capture_output=True, text=True)
        assert "already recorded" in second.stdout
        grant_id = UUID(first.stdout.split(": ")[1].split(".")[0])
        assert (
            db.scalar(
                text("SELECT count(*) FROM organization_access_grants WHERE id=:id"),
                {"id": grant_id},
            )
            == 1
        )
        assert before == counts()
        print(
            "Operator CLI: disabled guard denied; explicit bootstrap and idempotency passed; offices/memberships unchanged."
        )


if __name__ == "__main__":
    main()

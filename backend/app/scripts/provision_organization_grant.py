"""Trusted first-grant provisioning; never exposed through HTTP.

Run only using the migration-owner connection after independently verifying the
organization's authority. Local branch custody cannot bootstrap parent authority.
"""

import argparse
from uuid import UUID

from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models import OrganizationAccessGrant, OrganizationUnit, User
from app.services.audit import write_audit_log
from app.services.organization_access import PERMISSION_ROLES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=UUID, required=True)
    parser.add_argument("--organization-unit-id", type=UUID, required=True)
    parser.add_argument("--permission-role", choices=sorted(PERMISSION_ROLES), required=True)
    parser.add_argument("--scope-mode", choices=["unit_only", "descendants"], required=True)
    parser.add_argument(
        "--authority-reference", required=True, help="Non-sensitive approval/ticket reference"
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        if db.bind.dialect.name != "postgresql" or not db.scalar(
            text("""SELECT EXISTS(
            SELECT 1 FROM pg_tables WHERE schemaname='public'
            AND tablename='organization_access_grants' AND tableowner=current_user)""")
        ):
            raise SystemExit(
                "Use the PostgreSQL migration owner; runtime accounts cannot provision authority."
            )
        user = db.get(User, args.user_id)
        unit = db.get(OrganizationUnit, args.organization_unit_id)
        if user is None or user.status != "active" or unit is None:
            raise SystemExit("An active account and existing organization are required.")
        if not db.scalar(text("SELECT vinyrd_org_covers(:id,:id,'unit_only')"), {"id": unit.id}):
            raise SystemExit("Organization ancestry is inactive or malformed.")
        if db.scalar(
            select(OrganizationAccessGrant.id).where(
                OrganizationAccessGrant.user_id == user.id,
                OrganizationAccessGrant.organization_unit_id == unit.id,
                OrganizationAccessGrant.permission_role == args.permission_role,
                OrganizationAccessGrant.scope_mode == args.scope_mode,
            )
        ):
            raise SystemExit("Equivalent grant exists; use authorized grant management.")
        grant = OrganizationAccessGrant(
            user_id=user.id,
            organization_unit_id=unit.id,
            permission_role=args.permission_role,
            scope_mode=args.scope_mode,
        )
        db.add(grant)
        db.flush()
        write_audit_log(
            db,
            actor=None,
            action="organization.grant_bootstrapped",
            entity_type="organization_access_grant",
            entity_id=grant.id,
            metadata={
                "target_user_id": user.id,
                "organization_unit_id": unit.id,
                "permission_role": grant.permission_role,
                "scope_mode": grant.scope_mode,
                "authority_reference": args.authority_reference,
            },
        )
        db.commit()
        print(f"Provisioned explicit grant {grant.id}; no office or membership was changed.")


if __name__ == "__main__":
    main()

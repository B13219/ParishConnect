"""Deployment-authorized initial authority and controlled recovery; no HTTP entry point."""

import json

from sqlalchemy import select, text

from app.models import (
    AuditLog,
    Branch,
    ChurchOrganizationConfiguration,
    OrganizationAccessGrant,
    OrganizationUnit,
    Role,
    User,
    UserRole,
)
from app.services.audit import write_audit_log


def require_operator(db):
    if db.bind.dialect.name != "postgresql" or not db.scalar(
        text("""SELECT EXISTS(
        SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='organization_access_grants'
        AND tableowner=current_user)""")
    ):
        raise ValueError(
            "A migration-owner operational connection is required, never HTTP runtime."
        )
    return db.scalar(text("SELECT current_user"))


def trusted_local_admin(db, user_id, root_id):
    user = db.get(User, user_id)
    if user is None or user.status != "active" or user.branch_id is None:
        raise ValueError("An active, configured local Administrator is required.")
    if not db.scalar(
        select(UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == user.id, Role.name == "Administrator")
    ):
        raise ValueError("Existing local Administrator authority is required.")
    branch = db.get(Branch, user.branch_id)
    config = db.get(ChurchOrganizationConfiguration, user.branch_id)
    if (
        config is None
        or config.setup_status != "configured"
        or branch.organization_unit_id is None
        or config.local_unit_id != branch.organization_unit_id
    ):
        raise ValueError(
            "Complete and verify this administrator's church organization setup first."
        )
    if not db.scalar(
        text("SELECT vinyrd_org_covers(:root,:local,'descendants')"),
        {"root": root_id, "local": branch.organization_unit_id},
    ):
        raise ValueError(
            "Administrator's configured church is outside the selected organization tree."
        )
    return user


def bootstrap_authority(db, *, actor_id, target_id, root_id, reason, enabled=False, recovery=False):
    if not enabled:
        raise ValueError(
            "Authority bootstrap/recovery is disabled; authorize one operator invocation explicitly."
        )
    if not reason or not reason.strip() or len(reason) > 300:
        raise ValueError(
            "A non-sensitive verified approval reference (1-300 characters) is required."
        )
    operator = require_operator(db)
    # Serializes all initial/recovery invocations for this exact tree, including retries.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:root,0))"), {"root": str(root_id)}
    )
    root = db.get(OrganizationUnit, root_id)
    if root is None or root.parent_id is not None or root.status != "active":
        raise ValueError("Select the existing active root of the configured organization tree.")
    actor = trusted_local_admin(db, actor_id, root_id)
    trusted_local_admin(db, target_id, root_id)
    action = (
        "organization.authority_recovered" if recovery else "organization.authority_bootstrapped"
    )
    previous = list(db.scalars(select(AuditLog).where(AuditLog.action == action)))
    for log in previous:
        data = json.loads(log.metadata_json or "{}")
        if (
            log.actor_user_id == actor_id
            and data.get("organization_unit_id") == str(root_id)
            and data.get("target_user_id") == str(target_id)
            and data.get("authority_reference") == reason.strip()
        ):
            grant = db.get(OrganizationAccessGrant, log.entity_id)
            if (
                grant is not None
                and grant.status == "active"
                and grant.user_id == target_id
                and grant.organization_unit_id == root_id
                and grant.permission_role == "administrator"
                and grant.scope_mode == "descendants"
            ):
                return grant, False
            if not recovery:
                raise ValueError(
                    "Initial authority has been revoked or changed; use controlled recovery."
                )
    history = list(
        db.scalars(
            select(OrganizationAccessGrant)
            .where(
                text(
                    """organization_access_grants.organization_unit_id IN (
        WITH RECURSIVE tree(id) AS (SELECT id FROM organization_units WHERE id=:root
          UNION SELECT u.id FROM organization_units u JOIN tree t ON u.parent_id=t.id)
        SELECT id FROM tree)"""
                )
            )
            .params(root=root_id)
        )
    )
    initialized = any(
        json.loads(log.metadata_json or "{}").get("organization_unit_id") == str(root_id)
        for log in db.scalars(
            select(AuditLog).where(
                AuditLog.action.in_(
                    [
                        "organization.authority_bootstrapped",
                        "organization.grant_bootstrapped",
                        "organization.authority_recovered",
                    ]
                )
            )
        )
    )
    if not recovery and (history or initialized):
        raise ValueError(
            "This tree already has authority history; use normal delegation or controlled recovery."
        )
    if recovery:
        if not history and not initialized:
            raise ValueError("No authority history exists; use initial bootstrap instead.")
        active_root = [
            g
            for g in history
            if g.organization_unit_id == root_id
            and g.permission_role == "administrator"
            and g.scope_mode == "descendants"
            and g.status == "active"
            and db.get(User, g.user_id).status == "active"
        ]
        if active_root:
            raise ValueError(
                "Active root authority exists; use contained delegation, not recovery."
            )
    grant = next(
        (
            g
            for g in history
            if g.user_id == target_id
            and g.organization_unit_id == root_id
            and g.permission_role == "administrator"
            and g.scope_mode == "descendants"
        ),
        None,
    )
    if grant is None:
        grant = OrganizationAccessGrant(
            user_id=target_id,
            organization_unit_id=root_id,
            permission_role="administrator",
            scope_mode="descendants",
            granted_by=actor_id,
        )
        db.add(grant)
    grant.status = "active"
    db.flush()
    write_audit_log(
        db,
        actor=actor,
        action=action,
        entity_type="organization_access_grant",
        entity_id=grant.id,
        metadata={
            "target_user_id": target_id,
            "organization_unit_id": root_id,
            "permission_role": "administrator",
            "scope_mode": "descendants",
            "bootstrap_type": "deployment_recovery" if recovery else "initial_authority",
            "authority_reference": reason.strip(),
            "operator_database_role": operator,
        },
    )
    return grant, True

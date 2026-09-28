"""Explicit organization access management. Never infers authority from office."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_db
from app.models import (
    AttendanceRecord,
    Contribution,
    Member,
    OrganizationAccessGrant,
    OrganizationOfficeAssignment,
    User,
)
from app.services.audit import write_audit_log
from app.services.organization_access import PERMISSION_ROLES, OrganizationScope, enter_branch

router = APIRouter()


class GrantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permission_role: Literal[
        "administrator", "pastor_leader", "accountant", "receptionist", "usher"
    ]
    scope_mode: Literal["unit_only", "descendants"]
    status: Literal["active", "inactive", "revoked"] = "active"


class GrantCreate(GrantUpdate):
    user_id: UUID
    organization_unit_id: UUID


class ContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch_id: UUID


def unit_data(unit, visible, scope):
    from app.services.denominations import denomination_catalog

    return {
        "positions": [
            p
            for t in denomination_catalog()
            if t["value"] == unit.denomination
            for level in t["levels"]
            if level["key"] == unit.level_key
            for p in level["positions"]
        ],
        "id": unit.id,
        "level_key": unit.level_key,
        "labels": unit.labels_snapshot,
        "canonical_name": unit.canonical_name,
        "localized_names": unit.localized_names,
        "denomination": unit.denomination,
        "parent_id": unit.parent_id if unit.parent_id in visible else None,
        "has_children": any(i in visible for i in scope.children.get(unit.id, [])),
        "linked_branch_id": scope.linked_branches.get(unit.id),
        "can_manage": scope.can_manage(unit.id),
        "can_manage_descendants": scope.can_manage(unit.id, "descendants"),
    }


@router.get("/tree")
def tree(user=Depends(current_user), db: Session = Depends(get_db)):
    scope = OrganizationScope(db, user)
    visible = scope.unit_ids()
    return {
        "units": [unit_data(scope.units[i], visible, scope) for i in sorted(visible, key=str)],
        "branches": [
            {
                "id": b.id,
                "name": b.name,
                "organization_unit_id": b.organization_unit_id,
                "roles": sorted(scope.roles_for_branch(b.id)),
                "local_access": b.id == user.branch_id and bool(scope.local_roles),
            }
            for b in scope.branches
            if b.id in scope.branch_ids()
        ],
        "permission_profiles": sorted(PERMISSION_ROLES),
    }


@router.post("/context")
def context(payload: ContextInput, user=Depends(current_user), db: Session = Depends(get_db)):
    roles = enter_branch(db, user, payload.branch_id, PERMISSION_ROLES)
    write_audit_log(
        db,
        actor=user,
        action="organization.context_selected",
        entity_type="branch",
        entity_id=payload.branch_id,
        metadata={"branch_id": payload.branch_id},
    )
    db.commit()
    return {"branch_id": payload.branch_id, "roles": sorted(roles)}


def grant_data(row, scope, names):
    # Paths deliberately stop at the actor's visibility boundary.
    path = [
        {"id": unit.id, "name": unit.canonical_name, "labels": unit.labels_snapshot}
        for unit in scope.visible_path(row.organization_unit_id)
    ]
    return {
        "id": row.id,
        "user": {"id": row.user_id, "name": names.get(row.user_id)},
        "organization_unit_id": row.organization_unit_id,
        "organization_path": path,
        "permission_role": row.permission_role,
        "scope_mode": row.scope_mode,
        "status": row.status,
        "can_manage": row.user_id != scope.user.id
        and scope.can_manage(row.organization_unit_id, row.scope_mode),
    }


@router.get("/grants")
def grants(user=Depends(current_user), db: Session = Depends(get_db)):
    scope = OrganizationScope(db, user)
    rows = [
        g
        for g in db.scalars(select(OrganizationAccessGrant))
        if g.user_id == user.id or scope.can_manage(g.organization_unit_id, g.scope_mode)
    ]
    names = dict(
        db.execute(select(User.id, User.name).where(User.id.in_({g.user_id for g in rows}))).all()
    )
    return {"items": [grant_data(g, scope, names) for g in rows]}


def check_manage(scope, target_user_id, unit_id, mode):
    if target_user_id == scope.user.id:
        raise HTTPException(403, "Another authorized administrator must manage your grants.")
    if not scope.can_manage(unit_id, mode):
        raise HTTPException(403, "Grant scope exceeds your administrative authority.")


def save(db, actor, row, payload, action):
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    try:
        db.flush()
        write_audit_log(
            db,
            actor=actor,
            action=action,
            entity_type="organization_access_grant",
            entity_id=row.id,
            metadata={
                "target_user_id": row.user_id,
                "organization_unit_id": row.organization_unit_id,
                "permission_role": row.permission_role,
                "scope_mode": row.scope_mode,
                "status": row.status,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An equivalent grant already exists; update it instead.") from exc
    return {"id": row.id, "status": row.status}


@router.post("/grants", status_code=201)
def create_grant(payload: GrantCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    scope = OrganizationScope(db, user)
    check_manage(scope, payload.user_id, payload.organization_unit_id, payload.scope_mode)
    target = db.get(User, payload.user_id)
    if target is None or target.status != "active":
        raise HTTPException(404, "Active VINYRD account not found.")
    row = OrganizationAccessGrant(granted_by=user.id)
    return save(db, user, row, payload, "organization.grant_created")


@router.put("/grants/{grant_id}")
def update_grant(
    grant_id: UUID, payload: GrantUpdate, user=Depends(current_user), db: Session = Depends(get_db)
):
    row = db.scalar(
        select(OrganizationAccessGrant)
        .where(OrganizationAccessGrant.id == grant_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Grant not found.")
    scope = OrganizationScope(db, user)
    check_manage(scope, row.user_id, row.organization_unit_id, row.scope_mode)
    check_manage(scope, row.user_id, row.organization_unit_id, payload.scope_mode)
    action = (
        "organization.grant_revoked"
        if payload.status == "revoked"
        else "organization.grant_changed"
    )
    return save(db, user, row, payload, action)


@router.get("/offices")
def offices(user=Depends(current_user), db: Session = Depends(get_db)):
    scope = OrganizationScope(db, user)
    units = {i for i in scope.unit_ids() if scope.can_manage(i)}
    rows = list(
        db.scalars(
            select(OrganizationOfficeAssignment).where(
                OrganizationOfficeAssignment.organization_unit_id.in_(units)
            )
        )
    )
    names = dict(
        db.execute(select(User.id, User.name).where(User.id.in_({r.user_id for r in rows}))).all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "organization_unit_id": r.organization_unit_id,
                "user": {"id": r.user_id, "name": names.get(r.user_id)},
                "position_key": r.position_key,
                "status": r.status,
            }
            for r in rows
        ]
    }


@router.get("/summary")
def summary(unit_id: UUID | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    scope = OrganizationScope(db, user)
    branches = scope.branch_ids()
    if unit_id is not None:
        if unit_id not in scope.unit_ids():
            raise HTTPException(403, "Organization is outside your scope.")
        # Traverse only already-authorized nodes; never use selected context to add scope.
        descendants = scope.descendants(unit_id)
        branches &= {b.id for b in scope.branches if b.organization_unit_id in descendants}
    people = branches & scope.branch_ids({"administrator", "pastor_leader", "receptionist"})
    attendance = branches & scope.branch_ids(
        {"administrator", "pastor_leader", "receptionist", "usher"}
    )
    finance = branches & scope.branch_ids({"administrator", "accountant"})
    return {
        "accessible_church_count": len(branches),
        "members": {
            "church_count": len(people),
            "count": db.scalar(select(func.count(Member.id)).where(Member.branch_id.in_(people)))
            if people
            else None,
        },
        "attendance": {
            "church_count": len(attendance),
            "count": db.scalar(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.branch_id.in_(attendance)
                )
            )
            if attendance
            else None,
        },
        "finance": {
            "church_count": len(finance),
            "totals": [
                {"currency": currency, "amount": str(amount)}
                for currency, amount in db.execute(
                    select(Contribution.currency, func.sum(Contribution.amount))
                    .where(Contribution.branch_id.in_(finance))
                    .group_by(Contribution.currency)
                )
            ],
        }
        if finance
        else None,
    }


class OfficeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    organization_unit_id: UUID
    position_key: str
    status: Literal["active", "inactive"] = "active"


@router.put("/offices")
def save_office(payload: OfficeInput, user=Depends(current_user), db: Session = Depends(get_db)):
    from app.services.denominations import denomination_catalog

    scope = OrganizationScope(db, user)
    if not scope.can_manage(payload.organization_unit_id):
        raise HTTPException(403, "Office is outside your administrative scope.")
    unit = scope.units[payload.organization_unit_id]
    positions = [
        p
        for t in denomination_catalog()
        if t["value"] == unit.denomination
        for level in t["levels"]
        if level["key"] == unit.level_key
        for p in level["positions"]
    ]
    position = next((p for p in positions if p["key"] == payload.position_key), None)
    if position is None:
        raise HTTPException(422, "Use a verified office key for this denomination level.")
    target = db.get(User, payload.user_id)
    if target is None or target.status != "active":
        raise HTTPException(404, "Active VINYRD account not found.")
    if (
        not any(
            g.permission_role == "administrator" and unit.id in scope.coverage[g.id]
            for g in scope.grants
        )
        and target.branch_id != user.branch_id
    ):
        raise HTTPException(403, "Local office assignment requires a local staff account.")
    row = db.scalar(
        select(OrganizationOfficeAssignment).where(
            OrganizationOfficeAssignment.organization_unit_id == unit.id,
            OrganizationOfficeAssignment.user_id == target.id,
            OrganizationOfficeAssignment.position_key == payload.position_key,
        )
    )
    if row is None:
        row = OrganizationOfficeAssignment(
            branch_id=unit.owner_branch_id,
            organization_unit_id=unit.id,
            user_id=target.id,
            position_key=payload.position_key,
            permission_role=position["permission_role"],
        )
    row.status = payload.status
    db.add(row)
    try:
        db.flush()
        write_audit_log(
            db,
            actor=user,
            action="organization.office_changed",
            entity_type="organization_office_assignment",
            entity_id=row.id,
            metadata={
                "target_user_id": row.user_id,
                "organization_unit_id": unit.id,
                "position_key": row.position_key,
                "status": row.status,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Office changed concurrently; refresh and retry.") from exc
    return {"id": row.id, "status": row.status}

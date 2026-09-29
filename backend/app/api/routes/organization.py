"""Branch administrators explicitly install immutable organization snapshots."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import current_user, role_slug
from app.db.session import get_db
from app.models import Branch, OrganizationOfficeAssignment, Role, User
from app.services.global_identity import require_church_admin
from app.services.organizations import (
    AssignmentInput,
    ConfirmInput,
    SetupInput,
    configuration_data,
    confirm_setup,
    save_assignment,
    setup_preview,
)
from app.services.terminology import Terminology, runtime_levels, user_locale

router = APIRouter()


def admin(user=Depends(current_user), db: Session = Depends(get_db)):
    if db.info.get("requested_staff_branch") not in (None, user.branch_id):
        raise HTTPException(
            403, "Organization setup remains local; use Organization Administration."
        )
    require_church_admin(db, user, user.branch_id)
    return user


@router.get("/setup")
def setup(user=Depends(admin), db: Session = Depends(get_db)):
    return {
        **configuration_data(db, user.branch_id),
        "locale": user_locale(db, user, db.get(Branch, user.branch_id)),
    }


@router.post("/preview")
def preview(payload: SetupInput, user=Depends(admin), db: Session = Depends(get_db)):
    data = setup_preview(payload)
    levels = runtime_levels(Terminology(denomination=data["denomination"]))
    return {
        **data,
        "locale": user_locale(db, user, db.get(Branch, user.branch_id)),
        "levels": levels,
        "expected_parents": [
            l for l in levels if l["key"] in {p["key"] for p in data["expected_parents"]}
        ],
        "available_offices": next(
            (l["positions"] for l in levels if l["key"] == data["organization_level"]), []
        ),
    }


@router.post("/confirm")
def confirm(payload: ConfirmInput, user=Depends(admin), db: Session = Depends(get_db)):
    try:
        confirm_setup(db, user, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Organization setup conflicts with an existing record.") from exc
    return {
        **configuration_data(db, user.branch_id),
        "locale": user_locale(db, user, db.get(Branch, user.branch_id)),
    }


def assignment_data(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "organization_unit_id",
            "user_id",
            "position_key",
            "permission_role",
            "status",
        )
    }


@router.get("/assignments")
def assignments(user=Depends(admin), db: Session = Depends(get_db)):
    return {
        "items": [
            assignment_data(row)
            for row in db.scalars(
                select(OrganizationOfficeAssignment).where(
                    OrganizationOfficeAssignment.branch_id == user.branch_id
                )
            )
        ],
        "staff": [
            {"id": row.id, "name": row.name}
            for row in db.scalars(
                select(User)
                .where(User.branch_id == user.branch_id, User.status == "active")
                .order_by(User.name)
            )
        ],
        "permission_profiles": sorted({role_slug(name) for name in db.scalars(select(Role.name))}),
    }


@router.put("/assignments")
def assign(payload: AssignmentInput, user=Depends(admin), db: Session = Depends(get_db)):
    try:
        row = save_assignment(db, user, payload)
        result = assignment_data(row)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Office assignment conflicts with an existing record.") from exc

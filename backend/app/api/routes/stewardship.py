from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import Branch, Contribution, Member, User
from app.services.audit import write_audit_log

router = APIRouter()


class ContributionCreate(BaseModel):
    contribution_type: str
    amount: Decimal
    currency: str = "TZS"
    member_id: UUID | None = None
    payment_method: str = "cash"
    reference_code: str | None = None
    notes: str | None = None


def get_default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create or seed a branch before adding contributions.",
        )
    return branch


def serialize_contribution(contribution: Contribution, db: Session) -> dict[str, object]:
    member = db.get(Member, contribution.member_id) if contribution.member_id else None
    return {
        "id": str(contribution.id),
        "type": contribution.contribution_type,
        "amount": str(contribution.amount),
        "currency": contribution.currency,
        "received_at": contribution.received_at.isoformat(),
        "member_id": str(contribution.member_id) if contribution.member_id else None,
        "member_name": f"{member.first_name} {member.last_name}" if member else "Anonymous / Visitor",
        "payment_method": contribution.payment_method,
        "reference_code": contribution.reference_code,
        "notes": contribution.notes,
    }


@router.get("/")
def stewardship_summary(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "accountant")),
) -> dict[str, object]:
    total_amount = db.scalar(select(func.coalesce(func.sum(Contribution.amount), Decimal("0.00"))))
    contribution_count = db.scalar(select(func.count()).select_from(Contribution)) or 0
    latest = db.scalars(select(Contribution).order_by(Contribution.received_at.desc()).limit(10)).all()
    by_type = db.execute(
        select(
            Contribution.contribution_type,
            func.coalesce(func.sum(Contribution.amount), Decimal("0.00")),
            func.count(Contribution.id),
        )
        .group_by(Contribution.contribution_type)
        .order_by(func.sum(Contribution.amount).desc())
    ).all()

    return {
        "module": "stewardship",
        "status": "demo-data-ready",
        "contribution_count": contribution_count,
        "total_amount": str(total_amount or Decimal("0.00")),
        "currency": latest[0].currency if latest else "TZS",
        "by_type": [
            {
                "type": contribution_type,
                "amount": str(amount),
                "count": count,
                "currency": latest[0].currency if latest else "TZS",
            }
            for contribution_type, amount, count in by_type
        ],
        "latest": [serialize_contribution(contribution, db) for contribution in latest],
    }


@router.post("/contributions", status_code=status.HTTP_201_CREATED)
def create_contribution(
    payload: ContributionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("accountant")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    if payload.amount <= 0:
        raise HTTPException(
            status_code=422,
            detail="Contribution amount must be greater than zero.",
        )
    if payload.member_id and db.get(Member, payload.member_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    contribution = Contribution(
        branch_id=branch.id,
        member_id=payload.member_id,
        contribution_type=payload.contribution_type,
        amount=payload.amount,
        currency=payload.currency.upper(),
        payment_method=payload.payment_method,
        reference_code=payload.reference_code,
        received_at=utc_now(),
        recorded_by=actor.id,
        notes=payload.notes,
    )
    db.add(contribution)
    db.flush()
    write_audit_log(
        db,
        actor=actor,
        action="stewardship.contribution_created",
        entity_type="contribution",
        entity_id=contribution.id,
        metadata={
            "amount": str(contribution.amount),
            "currency": contribution.currency,
            "contribution_type": contribution.contribution_type,
            "payment_method": contribution.payment_method,
        },
    )
    db.commit()
    db.refresh(contribution)
    return serialize_contribution(contribution, db)

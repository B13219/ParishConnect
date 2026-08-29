from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import Branch, Contribution, Household, Member, Message, MessageRecipient, User
from app.services.audit import write_audit_log

router = APIRouter()


class ContributionCreate(BaseModel):
    contribution_type: str
    amount: Decimal
    currency: str = "TZS"
    member_id: UUID | None = None
    household_id: UUID | None = None
    contributor_scope: str = "individual"
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

def serialize_contribution(
    contribution: Contribution,
    db: Session,
) -> dict[str, object]:
    member = (
        db.get(Member, contribution.member_id)
        if contribution.member_id
        else None
    )

    household = (
        db.get(Household, contribution.household_id)
        if contribution.household_id
        else None
    )

    return {
        "id": str(contribution.id),
        "type": contribution.contribution_type,
        "amount": str(contribution.amount),
        "currency": contribution.currency,
        "received_at": contribution.received_at.isoformat(),

        "contributor_scope": contribution.contributor_scope,

        "member_id": (
            str(contribution.member_id)
            if contribution.member_id
            else None
        ),
        "member_name": (
            f"{member.first_name} {member.last_name}"
            if member
            else None
        ),

        "household_id": (
            str(contribution.household_id)
            if contribution.household_id
            else None
        ),
        "household_name": household.name if household else None,

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

def create_contribution_acknowledgement(
    db: Session,
    *,
    contribution: Contribution,
    branch: Branch,
    actor: User,
) -> None:
    recipient_member: Member | None = None

    if contribution.contributor_scope == "individual":
        if contribution.member_id:
            recipient_member = db.get(Member, contribution.member_id)

    elif (
    contribution.contributor_scope == "household"
    and contribution.household_id
    ):
        household = db.get(
           Household,
             contribution.household_id,
        )
        if household and household.primary_member_id:
                recipient_member = db.get(
                    Member,
                    household.primary_member_id,
                )

    if recipient_member is None:
        return

    reference_line = (
        f"\nReference: {contribution.reference_code}"
        if contribution.reference_code
        else ""
    )

    message = Message(
        branch_id=branch.id,
        sender_user_id=actor.id,
        channel="sms",
        subject="Contribution received",
        body=(
            f"We have received your {contribution.contribution_type} "
            f"of {contribution.currency} {contribution.amount}."
            f"{reference_line}\n\nThank you."
        ),
        audience_type="contribution_acknowledgement",
        status="sent",
        scheduled_at=None,
        sent_at=utc_now(),
    )

    db.add(message)
    db.flush()

    recipient = MessageRecipient(
        message_id=message.id,
        member_id=recipient_member.id,
        visitor_id=None,
        phone=recipient_member.phone,
        delivery_status="queued",
        provider_reference=None,
    )

    db.add(recipient)

@router.post("/contributions", status_code=status.HTTP_201_CREATED)
def create_contribution(
    payload: ContributionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("accountant")),
) -> dict[str, object]:
    branch = get_default_branch(db)

    if payload.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contribution amount must be greater than zero.",
        )

    if payload.contributor_scope not in {"individual", "household"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="contributor_scope must be individual or household.",
        )

    if payload.contributor_scope == "individual":
        if payload.member_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Individual contributions require member_id.",
            )

        if payload.household_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Individual contributions cannot include household_id.",
            )

        if db.get(Member, payload.member_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found.",
            )

    if payload.contributor_scope == "household":
        if payload.household_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Household contributions require household_id.",
            )

        if payload.member_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Household contributions cannot include member_id.",
            )

        if db.get(Household, payload.household_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Household not found.",
            )

    contribution = Contribution(
        branch_id=branch.id,
        member_id=payload.member_id,
        household_id=payload.household_id,
        contributor_scope=payload.contributor_scope,
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
    
    create_contribution_acknowledgement(
        db,
        contribution=contribution,
        branch=branch,
        actor=actor,
    )

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

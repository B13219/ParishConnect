from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.base import utc_now
from app.db.session import get_db
from app.models import Branch, Contribution, Event, Household, HouseholdPerson, Member, Message, User

router = APIRouter()


class MemberGivingCreate(BaseModel):
    contribution_type: str
    amount: Decimal
    currency: str = "TZS"
    payment_method: str = "mobile_money"
    reference_code: str | None = None
    notes: str | None = None


def get_current_member(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Member:
    if user.member_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not linked to a member profile.",
        )

    member = db.get(Member, user.member_id)
    if member is None or member.membership_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member profile is unavailable.",
        )

    if user.branch_id is not None and user.branch_id != member.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member profile belongs to a different branch.",
        )
    return member


def serialize_member_profile(member: Member, branch: Branch | None) -> dict[str, object]:
    return {
        "id": str(member.id),
        "member_code": f"VIN-{str(member.id).replace('-', '')[:8].upper()}",
        "first_name": member.first_name,
        "last_name": member.last_name,
        "name": f"{member.first_name} {member.last_name}",
        "phone": member.phone,
        "email": member.email,
        "status": member.membership_status,
        "branch_id": str(member.branch_id),
        "branch_name": branch.name if branch else "Church branch",
        "address": member.address,
        "area": member.area,
        "preferred_language": member.preferred_language,
    }


def serialize_member_contribution(contribution: Contribution) -> dict[str, object]:
    return {
        "id": str(contribution.id),
        "type": contribution.contribution_type,
        "amount": str(contribution.amount),
        "currency": contribution.currency,
        "received_at": contribution.received_at.isoformat(),
        "payment_method": contribution.payment_method,
        "reference_code": contribution.reference_code,
    }


def household_for_member(member: Member, db: Session) -> Household | None:
    household_person = db.scalar(
        select(HouseholdPerson).where(HouseholdPerson.member_id == member.id).limit(1)
    )
    return db.get(Household, household_person.household_id) if household_person else None


def household_people(
    household: Household | None,
    member: Member,
    db: Session,
) -> list[dict[str, object]]:
    if household is None:
        return []
    people = db.scalars(
        select(HouseholdPerson)
        .where(HouseholdPerson.household_id == household.id)
        .order_by(HouseholdPerson.created_at.asc())
    ).all()
    return [
        {
            "id": str(person.id),
            "name": f"{person.first_name or ''} {person.last_name or ''}".strip()
            or "Linked member",
            "person_type": person.person_type,
            "relationship": person.relationship,
            "can_self_check_in": person.can_self_check_in == "yes",
        }
        for person in people
        if person.member_id != member.id
    ]


@router.get("/me")
def member_home(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    branch = db.get(Branch, member.branch_id)
    household = household_for_member(member, db)
    events = db.scalars(
        select(Event)
        .where(Event.branch_id == member.branch_id)
        .order_by(Event.starts_at.asc())
        .limit(6)
    ).all()
    messages = db.scalars(
        select(Message)
        .where(Message.branch_id == member.branch_id, Message.status == "sent")
        .order_by(Message.created_at.desc())
        .limit(5)
    ).all()
    contributions = db.scalars(
        select(Contribution)
        .where(Contribution.member_id == member.id)
        .order_by(Contribution.received_at.desc())
        .limit(6)
    ).all()
    contribution_total = db.scalar(
        select(func.coalesce(func.sum(Contribution.amount), Decimal("0.00"))).where(
            Contribution.member_id == member.id
        )
    )

    return {
        "module": "member_portal",
        "status": "authenticated-member",
        "profile": serialize_member_profile(member, branch),
        "household": {
            "id": str(household.id),
            "name": household.name,
            "people": household_people(household, member, db),
        }
        if household
        else None,
        "events": [
            {
                "id": str(event.id),
                "name": event.name,
                "type": event.event_type,
                "starts_at": event.starts_at.isoformat(),
                "location": event.location,
            }
            for event in events
        ],
        "messages": [
            {
                "id": str(message.id),
                "channel": message.channel,
                "subject": message.subject,
                "body": message.body,
                "status": message.status,
            }
            for message in messages
        ],
        "giving": {
            "total_amount": str(contribution_total or Decimal("0.00")),
            "currency": contributions[0].currency if contributions else "TZS",
            "latest": [
                serialize_member_contribution(contribution)
                for contribution in contributions
            ],
        },
    }


@router.post("/giving", status_code=status.HTTP_201_CREATED)
def create_member_giving(
    payload: MemberGivingCreate,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="Giving amount must be greater than zero.")

    contribution = Contribution(
        branch_id=member.branch_id,
        member_id=member.id,
        contribution_type=payload.contribution_type,
        amount=payload.amount,
        currency=payload.currency.upper(),
        payment_method=payload.payment_method,
        reference_code=payload.reference_code,
        received_at=utc_now(),
        notes=payload.notes,
    )
    db.add(contribution)
    db.commit()
    db.refresh(contribution)
    return serialize_member_contribution(contribution)

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.session import get_db
from app.models import Contribution, Event, Household, HouseholdPerson, Member, Message

router = APIRouter()


class MemberGivingCreate(BaseModel):
    contribution_type: str
    amount: Decimal
    currency: str = "TZS"
    payment_method: str = "mobile_money"
    reference_code: str | None = None
    notes: str | None = None


def get_demo_member(db: Session) -> Member:
    member = db.scalar(
        select(Member)
        .where(Member.membership_status == "active")
        .order_by(Member.created_at.asc())
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active member profile is available for the demo portal.",
        )
    return member


def serialize_member_profile(member: Member) -> dict[str, object]:
    return {
        "id": str(member.id),
        "first_name": member.first_name,
        "last_name": member.last_name,
        "name": f"{member.first_name} {member.last_name}",
        "phone": member.phone,
        "email": member.email,
        "status": member.membership_status,
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
def member_home(db: Session = Depends(get_db)) -> dict[str, object]:
    member = get_demo_member(db)
    household = household_for_member(member, db)
    events = db.scalars(select(Event).order_by(Event.starts_at.asc()).limit(6)).all()
    messages = db.scalars(select(Message).order_by(Message.created_at.desc()).limit(5)).all()
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
        "status": "demo-member",
        "profile": serialize_member_profile(member),
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
    db: Session = Depends(get_db),
) -> dict[str, object]:
    member = get_demo_member(db)
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

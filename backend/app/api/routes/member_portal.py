from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.attendance import CheckInCreate, create_attendance_record, qr_window
from app.core.security import current_user
from app.db.base import utc_now
from app.db.session import get_db
from app.models import (
    AttendanceRecord,
    Branch,
    CommunityGroup,
    CommunityGroupMembership,
    Contribution,
    Event,
    Household,
    HouseholdPerson,
    Member,
    Message,
    Ministry,
    MinistryMembership,
    User,
)
from app.services.geofence import is_inside_geofence

router = APIRouter()


class MemberGivingCreate(BaseModel):
    contribution_type: str
    amount: Decimal
    currency: str = "TZS"
    payment_method: str = "mobile_money"
    reference_code: str | None = None
    notes: str | None = None


class MemberLocationCheckInCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, gt=0)


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



def serialize_member_event(
    event: Event,
    member: Member,
    branch: Branch | None,
    db: Session,
) -> dict[str, object]:
    checked_in = db.scalar(
        select(AttendanceRecord.id).where(
            AttendanceRecord.event_id == event.id,
            AttendanceRecord.person_type == "member",
            AttendanceRecord.member_id == member.id,
        )
    )
    opens_at, closes_at = qr_window(event)
    now = utc_now()
    attendance_window_open = (
        event.attendance_status == "open"
        and opens_at <= now <= closes_at
    )
    geofence_available = bool(
        branch
        and branch.geofence_enabled
        and branch.latitude is not None
        and branch.longitude is not None
    )

    return {
        "id": str(event.id),
        "name": event.name,
        "type": event.event_type,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat() if event.ends_at else None,
        "location": event.location,
        "attendance_status": event.attendance_status,
        "attendance_window_open": attendance_window_open,
        "geofence_available": geofence_available,
        "checked_in": checked_in is not None,
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



@router.get("/groups")
def member_groups(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    branch = db.get(Branch, member.branch_id)

    community_memberships = db.scalars(
        select(CommunityGroupMembership)
        .where(
            CommunityGroupMembership.member_id == member.id,
            CommunityGroupMembership.status == "active",
        )
        .order_by(CommunityGroupMembership.created_at.asc())
    ).all()

    communities: list[dict[str, object]] = []
    for membership in community_memberships:
        group = db.get(CommunityGroup, membership.community_group_id)
        if group is None or group.branch_id != member.branch_id or group.status != "active":
            continue

        leader = db.get(Member, group.leader_member_id) if group.leader_member_id else None
        member_count = db.scalar(
            select(func.count())
            .select_from(CommunityGroupMembership)
            .where(
                CommunityGroupMembership.community_group_id == group.id,
                CommunityGroupMembership.status == "active",
            )
        ) or 0

        communities.append(
            {
                "id": str(group.id),
                "name": group.name,
                "group_type": group.group_type,
                "role": membership.role,
                "area": group.area,
                "meeting_day": group.meeting_day,
                "leader_name": (
                    f"{leader.first_name} {leader.last_name}"
                    if leader
                    else None
                ),
                "member_count": member_count,
                "is_leader": group.leader_member_id == member.id,
            }
        )

    ministry_memberships = db.scalars(
        select(MinistryMembership)
        .where(
            MinistryMembership.member_id == member.id,
            MinistryMembership.status == "active",
        )
        .order_by(MinistryMembership.created_at.asc())
    ).all()

    ministries: list[dict[str, object]] = []
    for membership in ministry_memberships:
        ministry = db.get(Ministry, membership.ministry_id)
        if ministry is None or ministry.branch_id != member.branch_id:
            continue

        leader = (
            db.get(Member, ministry.leader_member_id)
            if ministry.leader_member_id
            else None
        )
        member_count = db.scalar(
            select(func.count())
            .select_from(MinistryMembership)
            .where(
                MinistryMembership.ministry_id == ministry.id,
                MinistryMembership.status == "active",
            )
        ) or 0

        ministries.append(
            {
                "id": str(ministry.id),
                "name": ministry.name,
                "role": membership.role,
                "leader_name": (
                    f"{leader.first_name} {leader.last_name}"
                    if leader
                    else None
                ),
                "member_count": member_count,
                "is_leader": ministry.leader_member_id == member.id,
            }
        )

    return {
        "community_label": (
            branch.community_label
            if branch and branch.community_label
            else "Community Group"
        ),
        "communities": communities,
        "ministries": ministries,
        "total_memberships": len(communities) + len(ministries),
    }


@router.get("/events")
def member_events(
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    branch = db.get(Branch, member.branch_id)
    events = db.scalars(
        select(Event)
        .where(Event.branch_id == member.branch_id)
        .order_by(Event.starts_at.asc())
        .limit(50)
    ).all()
    return [serialize_member_event(event, member, branch, db) for event in events]


@router.post("/events/{event_id}/check-in/location", status_code=status.HTTP_201_CREATED)
def member_location_check_in(
    event_id: UUID,
    payload: MemberLocationCheckInCreate,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    event = db.get(Event, event_id)
    if event is None or event.branch_id != member.branch_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    if event.attendance_status != "open":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Attendance is not open for this event.",
        )

    branch = db.get(Branch, member.branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member branch not found.",
        )

    if not branch.geofence_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location attendance is disabled for this branch.",
        )

    if branch.latitude is None or branch.longitude is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The branch location has not been configured.",
        )

    opens_at, closes_at = qr_window(event)
    now = utc_now()
    if now < opens_at or now > closes_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location check-in is outside the attendance window.",
        )

    if (
        payload.accuracy_meters is not None
        and payload.accuracy_meters > branch.attendance_radius_meters
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Location accuracy is too low to confirm attendance.",
        )

    inside, distance_meters = is_inside_geofence(
        church_latitude=branch.latitude,
        church_longitude=branch.longitude,
        device_latitude=payload.latitude,
        device_longitude=payload.longitude,
        radius_meters=branch.attendance_radius_meters,
    )
    if not inside:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "reason": "outside_geofence",
                "distance_meters": round(distance_meters, 1),
                "allowed_radius_meters": branch.attendance_radius_meters,
            },
        )

    attendance = create_attendance_record(
        CheckInCreate(
            event_id=event.id,
            person_type="member",
            person_id=member.id,
            check_in_method="geofence",
        ),
        db,
    )
    attendance["distance_meters"] = round(distance_meters, 1)
    attendance["allowed_radius_meters"] = branch.attendance_radius_meters
    attendance["inside_geofence"] = True
    return attendance


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

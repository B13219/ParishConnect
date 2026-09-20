import secrets
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import password_hash, require_roles, role_slug
from app.db.base import utc_now
from app.db.session import get_db
from app.models import (
    Branch,
    Event,
    Member,
    PrayerRequest,
    Role,
    User,
    UserRole,
)
from app.services.audit import write_audit_log

router = APIRouter()


class MemberAccessCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = Field(default=None, max_length=255)


class MemberAccessStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "inactive"]


class PrayerWorkflowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "submitted",
        "in_prayer",
        "contacted",
        "answered",
        "closed",
    ] | None = None
    pastoral_notes: str | None = Field(default=None, max_length=4000)
    assign_to_me: bool | None = None


class SermonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=160)
    speaker: str | None = Field(default=None, max_length=160)
    scripture_reference: str | None = Field(default=None, max_length=160)
    summary: str | None = Field(default=None, max_length=6000)
    published: bool = False


def actor_branch(actor: User, db: Session) -> Branch:
    branch = db.get(Branch, actor.branch_id) if actor.branch_id else None
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff account is not linked to a church branch.",
        )
    return branch


def branch_member(member_id: UUID, actor: User, db: Session) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found.",
        )
    if actor.branch_id and member.branch_id != actor.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member belongs to a different branch.",
        )
    return member


def member_role(db: Session) -> Role:
    roles = db.scalars(select(Role).order_by(Role.name.asc())).all()
    role = next((item for item in roles if role_slug(item.name) == "member"), None)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member role is not configured.",
        )
    return role


def serialize_member_access(member: Member, db: Session) -> dict[str, object]:
    account = db.scalar(select(User).where(User.member_id == member.id))
    if account is None:
        return {
            "member_id": str(member.id),
            "exists": False,
            "email": member.email,
            "status": "not_activated",
            "created_at": None,
            "updated_at": None,
        }

    return {
        "member_id": str(member.id),
        "exists": True,
        "account_id": str(account.id),
        "email": account.email,
        "status": account.status,
        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
    }


def serialize_prayer(prayer: PrayerRequest, db: Session) -> dict[str, object]:
    member = db.get(Member, prayer.member_id)
    assigned = db.get(User, prayer.assigned_user_id) if prayer.assigned_user_id else None
    return {
        "id": str(prayer.id),
        "member_id": str(prayer.member_id),
        "member_name": (
            f"{member.first_name} {member.last_name}"
            if member
            else "Unknown member"
        ),
        "member_phone": member.phone if member else None,
        "member_email": member.email if member else None,
        "category": prayer.category,
        "body": prayer.body,
        "visibility": prayer.visibility,
        "allow_contact": prayer.allow_contact,
        "status": prayer.status,
        "assigned_user_id": (
            str(prayer.assigned_user_id)
            if prayer.assigned_user_id
            else None
        ),
        "assigned_to": assigned.name if assigned else None,
        "pastoral_notes": prayer.pastoral_notes,
        "contacted_at": (
            prayer.contacted_at.isoformat()
            if prayer.contacted_at
            else None
        ),
        "answered_at": (
            prayer.answered_at.isoformat()
            if prayer.answered_at
            else None
        ),
        "created_at": prayer.created_at.isoformat(),
        "updated_at": prayer.updated_at.isoformat(),
    }


def serialize_sermon(event: Event) -> dict[str, object]:
    return {
        "event_id": str(event.id),
        "event_name": event.name,
        "event_type": event.event_type,
        "starts_at": event.starts_at.isoformat(),
        "location": event.location,
        "title": event.sermon_title,
        "speaker": event.sermon_speaker,
        "scripture_reference": event.sermon_scripture,
        "summary": event.sermon_summary,
        "published": event.sermon_published_at is not None,
        "published_at": (
            event.sermon_published_at.isoformat()
            if event.sermon_published_at
            else None
        ),
    }


@router.get("/member-access/{member_id}")
def get_member_access(
    member_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("receptionist", "pastor_leader")),
) -> dict[str, object]:
    member = branch_member(member_id, actor, db)
    return serialize_member_access(member, db)


@router.post("/member-access/{member_id}", status_code=status.HTTP_201_CREATED)
def provision_member_access(
    member_id: UUID,
    payload: MemberAccessCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("receptionist")),
) -> dict[str, object]:
    member = branch_member(member_id, actor, db)
    if db.scalar(select(User).where(User.member_id == member.id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This member already has a Vinyrd account.",
        )

    email = (payload.email or member.email or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An email address is required to create member access.",
        )
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email address is already used by another account.",
        )

    temporary_password = secrets.token_urlsafe(9)
    account = User(
        branch_id=member.branch_id,
        member_id=member.id,
        name=f"{member.first_name} {member.last_name}",
        email=email,
        phone=member.phone,
        password_hash=password_hash(temporary_password),
        status="active",
    )
    db.add(account)
    db.flush()
    role = member_role(db)
    db.add(UserRole(user_id=account.id, role_id=role.id))
    write_audit_log(
        db,
        actor=actor,
        action="member_access.provisioned",
        entity_type="user",
        entity_id=account.id,
        metadata={"member_id": str(member.id), "email": email},
    )
    db.commit()
    db.refresh(account)

    result = serialize_member_access(member, db)
    result["temporary_password"] = temporary_password
    return result


@router.post("/member-access/{member_id}/reset-password")
def reset_member_password(
    member_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("receptionist")),
) -> dict[str, object]:
    member = branch_member(member_id, actor, db)
    account = db.scalar(select(User).where(User.member_id == member.id))
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member account has not been activated.",
        )

    temporary_password = secrets.token_urlsafe(9)
    account.password_hash = password_hash(temporary_password)
    write_audit_log(
        db,
        actor=actor,
        action="member_access.password_reset",
        entity_type="user",
        entity_id=account.id,
        metadata={"member_id": str(member.id)},
    )
    db.commit()
    result = serialize_member_access(member, db)
    result["temporary_password"] = temporary_password
    return result


@router.patch("/member-access/{member_id}")
def update_member_access_status(
    member_id: UUID,
    payload: MemberAccessStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("receptionist")),
) -> dict[str, object]:
    member = branch_member(member_id, actor, db)
    account = db.scalar(select(User).where(User.member_id == member.id))
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member account has not been activated.",
        )

    account.status = payload.status
    write_audit_log(
        db,
        actor=actor,
        action="member_access.status_updated",
        entity_type="user",
        entity_id=account.id,
        metadata={
            "member_id": str(member.id),
            "status": payload.status,
        },
    )
    db.commit()
    return serialize_member_access(member, db)


@router.get("/prayers")
def list_pastoral_prayers(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    branch = actor_branch(actor, db)
    prayers = db.scalars(
        select(PrayerRequest)
        .where(PrayerRequest.branch_id == branch.id)
        .order_by(PrayerRequest.created_at.desc())
        .limit(100)
    ).all()
    return {
        "module": "pastoral_care",
        "prayers": [serialize_prayer(prayer, db) for prayer in prayers],
    }


@router.patch("/prayers/{prayer_id}")
def update_pastoral_prayer(
    prayer_id: UUID,
    payload: PrayerWorkflowUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    branch = actor_branch(actor, db)
    prayer = db.get(PrayerRequest, prayer_id)
    if prayer is None or prayer.branch_id != branch.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prayer request not found.",
        )

    changed: list[str] = []
    if payload.status is not None:
        prayer.status = payload.status
        changed.append("status")
        if payload.status == "contacted" and prayer.contacted_at is None:
            prayer.contacted_at = utc_now()
        if payload.status == "answered" and prayer.answered_at is None:
            prayer.answered_at = utc_now()

    if payload.pastoral_notes is not None:
        prayer.pastoral_notes = payload.pastoral_notes.strip() or None
        changed.append("pastoral_notes")

    if payload.assign_to_me is True:
        prayer.assigned_user_id = actor.id
        changed.append("assigned_user_id")
    elif payload.assign_to_me is False:
        prayer.assigned_user_id = None
        changed.append("assigned_user_id")

    write_audit_log(
        db,
        actor=actor,
        action="pastoral.prayer_updated",
        entity_type="prayer_request",
        entity_id=prayer.id,
        metadata={"updated_fields": changed, "status": prayer.status},
    )
    db.commit()
    db.refresh(prayer)
    return serialize_prayer(prayer, db)


@router.get("/sermons")
def list_staff_sermons(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    branch = actor_branch(actor, db)
    events = db.scalars(
        select(Event)
        .where(Event.branch_id == branch.id)
        .order_by(Event.starts_at.desc())
        .limit(100)
    ).all()
    return {
        "module": "sermons",
        "events": [serialize_sermon(event) for event in events],
    }


@router.put("/sermons/{event_id}")
def update_event_sermon(
    event_id: UUID,
    payload: SermonUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    branch = actor_branch(actor, db)
    event = db.get(Event, event_id)
    if event is None or event.branch_id != branch.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service or event not found.",
        )

    title = payload.title.strip() if payload.title else None
    speaker = payload.speaker.strip() if payload.speaker else None
    scripture = (
        payload.scripture_reference.strip()
        if payload.scripture_reference
        else None
    )
    summary = payload.summary.strip() if payload.summary else None

    if payload.published and (not title or not summary):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A title and summary are required before publishing a sermon.",
        )

    event.sermon_title = title
    event.sermon_speaker = speaker
    event.sermon_scripture = scripture
    event.sermon_summary = summary
    if payload.published:
        event.sermon_published_at = event.sermon_published_at or utc_now()
    else:
        event.sermon_published_at = None

    write_audit_log(
        db,
        actor=actor,
        action="sermon.updated",
        entity_type="event",
        entity_id=event.id,
        metadata={
            "published": payload.published,
            "title": title,
        },
    )
    db.commit()
    db.refresh(event)
    return serialize_sermon(event)

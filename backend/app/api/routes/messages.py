from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import Branch, Member, Message, MessageRecipient, User, Visitor
from app.services.audit import write_audit_log

router = APIRouter()


class MessageCreate(BaseModel):
    channel: str
    body: str
    subject: str | None = None
    audience_type: str = "all_members"
    status: str = "draft"
    scheduled_at: datetime | None = None
    sender_user_id: UUID | None = None


def get_default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create or seed a branch before sending messages.",
        )
    return branch


def demo_delivery_status(channel: str, message_status: str) -> str:
    if message_status == "draft":
        return "draft"
    if message_status == "scheduled":
        return "scheduled"
    if channel == "sms":
        return "queued"
    return "delivered"


def recipient_people(db: Session, message: Message) -> list[Member | Visitor]:
    if message.audience_type == "visitors":
        return list(
            db.scalars(
                select(Visitor)
                .where(Visitor.branch_id == message.branch_id)
                .order_by(Visitor.created_at.desc())
                .limit(50)
            ).all()
        )
    return list(
        db.scalars(
            select(Member)
            .where(Member.branch_id == message.branch_id, Member.membership_status == "active")
            .order_by(Member.created_at.desc())
            .limit(50)
        ).all()
    )


def create_recipients(db: Session, message: Message) -> list[MessageRecipient]:
    existing = db.scalars(
        select(MessageRecipient).where(MessageRecipient.message_id == message.id)
    ).all()
    if existing:
        return list(existing)

    recipients: list[MessageRecipient] = []
    delivery_status = demo_delivery_status(message.channel, message.status)
    for person in recipient_people(db, message):
        recipient = MessageRecipient(
            message_id=message.id,
            member_id=person.id if isinstance(person, Member) else None,
            visitor_id=person.id if isinstance(person, Visitor) else None,
            phone=person.phone,
            delivery_status=delivery_status,
            provider_reference=f"demo-{message.channel}-{person.id}" if message.status == "sent" else None,
        )
        db.add(recipient)
        recipients.append(recipient)
    return recipients


def delivery_counts(db: Session, message_id: UUID) -> dict[str, int]:
    counts = db.execute(
        select(MessageRecipient.delivery_status, func.count(MessageRecipient.id))
        .where(MessageRecipient.message_id == message_id)
        .group_by(MessageRecipient.delivery_status)
    ).all()
    return {status: count for status, count in counts}


def serialize_message(
    message: Message,
    db: Session,
    *,
    include_body: bool = False,
) -> dict[str, object]:
    counts = delivery_counts(db, message.id)
    recipient_count = sum(counts.values())
    payload: dict[str, object] = {
        "id": str(message.id),
        "channel": message.channel,
        "subject": message.subject,
        "status": message.status,
        "audience_type": message.audience_type,
        "recipient_count": recipient_count,
        "delivery_counts": counts,
        "scheduled_at": message.scheduled_at.isoformat() if message.scheduled_at else None,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
    }
    if include_body:
        payload["body"] = message.body
    return payload


def serialize_recipient(recipient: MessageRecipient, db: Session) -> dict[str, object]:
    member = db.get(Member, recipient.member_id) if recipient.member_id else None
    visitor = db.get(Visitor, recipient.visitor_id) if recipient.visitor_id else None
    person = member or visitor
    return {
        "id": str(recipient.id),
        "name": f"{person.first_name} {person.last_name}" if person else "Unknown recipient",
        "person_type": "member" if member else "visitor" if visitor else "unknown",
        "phone": recipient.phone,
        "delivery_status": recipient.delivery_status,
        "provider_reference": recipient.provider_reference,
        "created_at": recipient.created_at.isoformat(),
    }


@router.get("/")
def list_messages(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    messages = db.scalars(select(Message).order_by(Message.created_at.desc()).limit(20)).all()

    return {
        "module": "messages",
        "status": "demo-data-ready",
        "messages": [serialize_message(message, db, include_body=True) for message in messages],
    }


@router.post("/", status_code=201)
def create_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    if payload.sender_user_id and db.get(User, payload.sender_user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender not found.")

    status_value = payload.status
    scheduled_at = payload.scheduled_at
    sent_at = None
    if status_value == "send_now":
        status_value = "sent"
        sent_at = utc_now()
    elif status_value == "scheduled" and scheduled_at is None:
        scheduled_at = utc_now()

    message = Message(
        branch_id=branch.id,
        sender_user_id=payload.sender_user_id or actor.id,
        channel=payload.channel,
        subject=payload.subject,
        body=payload.body,
        audience_type=payload.audience_type,
        status=status_value,
        scheduled_at=scheduled_at,
        sent_at=sent_at,
    )
    db.add(message)
    db.flush()
    create_recipients(db, message)
    write_audit_log(
        db,
        actor=actor,
        action="messages.message_created",
        entity_type="message",
        entity_id=message.id,
        metadata={
            "channel": message.channel,
            "status": message.status,
            "audience_type": message.audience_type,
        },
    )
    db.commit()
    db.refresh(message)
    return serialize_message(message, db, include_body=True)


@router.get("/{message_id}/recipients")
def list_message_recipients(
    message_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    recipients = db.scalars(
        select(MessageRecipient)
        .where(MessageRecipient.message_id == message.id)
        .order_by(MessageRecipient.created_at.desc())
    ).all()
    if not recipients:
        recipients = create_recipients(db, message)
        db.commit()
    return {
        "module": "messages",
        "message": serialize_message(message, db, include_body=True),
        "recipients": [serialize_recipient(recipient, db) for recipient in recipients],
    }


@router.post("/{message_id}/dispatch")
def dispatch_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
    if message.status == "sent":
        return serialize_message(message, db, include_body=True)

    message.status = "sent"
    message.sent_at = utc_now()
    recipients = create_recipients(db, message)
    for recipient in recipients:
        recipient.delivery_status = demo_delivery_status(message.channel, message.status)
        recipient.provider_reference = f"demo-{message.channel}-{recipient.id}"
    write_audit_log(
        db,
        actor=actor,
        action="messages.message_dispatched",
        entity_type="message",
        entity_id=message.id,
        metadata={"channel": message.channel, "recipient_count": len(recipients)},
    )
    db.commit()
    db.refresh(message)
    return serialize_message(message, db, include_body=True)

from datetime import datetime
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.core.settings import settings
from app.db.base import utc_now
from app.db.session import get_db
from app.models import (
    Branch,
    Member,
    Message,
    MessageRecipient,
    Ministry,
    MinistryMembership,
    User,
    Visitor,
)
from app.services.audit import write_audit_log
from app.services.sms import (
    SmsProviderError,
    delivery_report_status,
    normalize_phone_number,
    send_sms,
    sms_provider_status,
)

router = APIRouter()

ALLOWED_CHANNELS = {"in_app", "sms", "push"}
ALLOWED_STATUSES = {"draft", "send_now", "scheduled"}
ALLOWED_AUDIENCES = {"all_members", "visitors", "ministry"}
ACCEPTED_SMS_STATUSES = {"queued", "sent", "submitted", "buffered", "delivered"}


class MessageCreate(BaseModel):
    channel: str
    body: str
    subject: str | None = None
    audience_type: str = "all_members"
    audience_id: UUID | None = None
    status: str = "draft"
    scheduled_at: datetime | None = None
    sender_user_id: UUID | None = None


class SmsTestRequest(BaseModel):
    phone: str
    body: str = "VINYRD SMS sandbox connection test."


def get_default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create or seed a branch before sending messages.",
        )
    return branch


def initial_delivery_status(channel: str, message_status: str) -> str:
    if message_status == "draft":
        return "draft"
    if message_status == "scheduled":
        return "scheduled"
    if channel == "sms":
        return "pending"
    return "pending"


def recipient_people(
    db: Session,
    message: Message,
    *,
    audience_id: UUID | None = None,
) -> list[Member | Visitor]:
    if message.audience_type == "visitors":
        return list(
            db.scalars(
                select(Visitor)
                .where(Visitor.branch_id == message.branch_id)
                .order_by(Visitor.created_at.desc())
                .limit(500)
            ).all()
        )

    if message.audience_type == "ministry":
        if audience_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select a ministry before creating a ministry message.",
            )
        ministry = db.get(Ministry, audience_id)
        if ministry is None or ministry.branch_id != message.branch_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ministry not found for this branch.",
            )
        return list(
            db.scalars(
                select(Member)
                .join(
                    MinistryMembership,
                    MinistryMembership.member_id == Member.id,
                )
                .where(
                    MinistryMembership.ministry_id == ministry.id,
                    MinistryMembership.status == "active",
                    Member.branch_id == message.branch_id,
                    Member.membership_status == "active",
                )
                .order_by(Member.created_at.desc())
            ).all()
        )

    return list(
        db.scalars(
            select(Member)
            .where(
                Member.branch_id == message.branch_id,
                Member.membership_status == "active",
            )
            .order_by(Member.created_at.desc())
            .limit(500)
        ).all()
    )


def create_recipients(
    db: Session,
    message: Message,
    *,
    audience_id: UUID | None = None,
) -> list[MessageRecipient]:
    existing = db.scalars(
        select(MessageRecipient).where(MessageRecipient.message_id == message.id)
    ).all()
    if existing:
        return list(existing)

    recipients: list[MessageRecipient] = []
    delivery_status = initial_delivery_status(message.channel, message.status)
    for person in recipient_people(db, message, audience_id=audience_id):
        recipient = MessageRecipient(
            message_id=message.id,
            member_id=person.id if isinstance(person, Member) else None,
            visitor_id=person.id if isinstance(person, Visitor) else None,
            phone=normalize_phone_number(person.phone),
            delivery_status=delivery_status,
            provider_reference=None,
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
    return {delivery_status: count for delivery_status, count in counts}


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


def dispatch_recipients(
    db: Session,
    message: Message,
    recipients: list[MessageRecipient],
) -> None:
    if message.channel != "sms":
        for recipient in recipients:
            recipient.delivery_status = "delivered"
        message.status = "sent"
        message.sent_at = utc_now()
        return

    valid_recipients: list[MessageRecipient] = []
    for recipient in recipients:
        recipient.phone = normalize_phone_number(recipient.phone)
        if recipient.phone:
            valid_recipients.append(recipient)
        else:
            recipient.delivery_status = "missing_phone"
            recipient.provider_reference = None

    if not valid_recipients:
        message.status = "failed"
        message.sent_at = None
        raise SmsProviderError("No recipients have valid phone numbers.")

    results = send_sms(message.body, [recipient.phone for recipient in valid_recipients])
    result_by_phone = {result.phone: result for result in results}

    accepted_count = 0
    for recipient in valid_recipients:
        result = result_by_phone.get(recipient.phone or "")
        if result is None:
            recipient.delivery_status = "provider_error"
            recipient.provider_reference = None
            continue

        recipient.delivery_status = result.delivery_status
        recipient.provider_reference = result.provider_reference
        if result.delivery_status in ACCEPTED_SMS_STATUSES:
            accepted_count += 1

    message.status = "sent" if accepted_count else "failed"
    message.sent_at = utc_now() if accepted_count else None


@router.get("/")
def list_messages(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    messages = db.scalars(select(Message).order_by(Message.created_at.desc()).limit(20)).all()

    return {
        "module": "messages",
        "status": "ready",
        "messages": [serialize_message(message, db, include_body=True) for message in messages],
    }


@router.get("/sms/provider")
def get_sms_provider(
    _user=Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    provider = sms_provider_status()
    provider["delivery_report_path"] = "/api/v1/messages/sms/delivery-report"
    return provider


@router.post("/sms/test")
def send_test_sms(
    payload: SmsTestRequest,
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    mode = settings.sms_mode.lower().strip()
    if mode not in {"simulate", "sandbox"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test SMS is only available in simulate or sandbox mode.",
        )

    phone = normalize_phone_number(payload.phone)
    if phone is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid phone number.",
        )

    try:
        result = send_sms(payload.body.strip() or "VINYRD SMS sandbox connection test.", [phone])[0]
    except SmsProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return {
        "provider": settings.sms_provider,
        "mode": mode,
        "phone": result.phone,
        "delivery_status": result.delivery_status,
        "provider_reference": result.provider_reference,
        "status_code": result.status_code,
        "cost": result.cost,
        "error": result.error,
    }


@router.post("/sms/delivery-report")
async def sms_delivery_report(
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    mode = settings.sms_mode.lower().strip()
    if mode in {"sandbox", "live"} and not settings.sms_callback_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS delivery callback token is not configured.",
        )
    if settings.sms_callback_token and token != settings.sms_callback_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid callback token.")

    body = (await request.body()).decode("utf-8", errors="replace")
    parsed = parse_qs(body)
    payload = {key: values[-1] for key, values in parsed.items() if values}

    provider_reference = payload.get("id") or payload.get("messageId")
    status_text = payload.get("status")
    phone = normalize_phone_number(payload.get("phoneNumber") or payload.get("phone"))

    recipient = None
    if provider_reference:
        recipient = db.scalar(
            select(MessageRecipient).where(
                MessageRecipient.provider_reference == provider_reference
            )
        )

    if recipient is None:
        return {
            "status": "ignored",
            "provider_reference": provider_reference,
            "phone": phone,
        }

    recipient.delivery_status = delivery_report_status(status_text)
    db.commit()
    return {
        "status": "ok",
        "provider_reference": provider_reference,
        "delivery_status": recipient.delivery_status,
    }


@router.post("/", status_code=201)
def create_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    branch = get_default_branch(db)

    if payload.channel not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported message channel: {payload.channel}",
        )
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported message status: {payload.status}",
        )
    if payload.audience_type not in ALLOWED_AUDIENCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This audience is not ready for safe messaging yet.",
        )
    if payload.audience_type == "ministry" and payload.audience_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a ministry before creating a ministry message.",
        )
    if payload.sender_user_id and db.get(User, payload.sender_user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender not found.")

    status_value = payload.status
    scheduled_at = payload.scheduled_at
    if status_value == "send_now":
        status_value = "sending"
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
        sent_at=None,
    )
    db.add(message)
    db.flush()

    recipients = create_recipients(db, message, audience_id=payload.audience_id)

    if payload.status == "send_now":
        try:
            dispatch_recipients(db, message, recipients)
        except SmsProviderError as exc:
            message.status = "failed"
            for recipient in recipients:
                if recipient.delivery_status == "pending":
                    recipient.delivery_status = "provider_error"
            write_audit_log(
                db,
                actor=actor,
                action="messages.sms_dispatch_failed",
                entity_type="message",
                entity_id=message.id,
                metadata={
                    "channel": message.channel,
                    "audience_type": message.audience_type,
                    "reason": str(exc),
                },
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

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
            "recipient_count": len(recipients),
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

    recipients = list(
        db.scalars(
            select(MessageRecipient).where(MessageRecipient.message_id == message.id)
        ).all()
    )
    if not recipients:
        recipients = create_recipients(db, message)

    for recipient in recipients:
        if recipient.delivery_status in {"draft", "scheduled", "provider_error"}:
            recipient.delivery_status = "pending"

    try:
        dispatch_recipients(db, message, recipients)
    except SmsProviderError as exc:
        message.status = "failed"
        for recipient in recipients:
            if recipient.delivery_status == "pending":
                recipient.delivery_status = "provider_error"
        write_audit_log(
            db,
            actor=actor,
            action="messages.sms_dispatch_failed",
            entity_type="message",
            entity_id=message.id,
            metadata={
                "channel": message.channel,
                "recipient_count": len(recipients),
                "reason": str(exc),
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

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

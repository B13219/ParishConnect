import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.security import require_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import AttendanceRecord, Branch, Event, HouseholdPerson, Member, ServiceTemplate, Visitor
from app.services.qr_code import make_qr_svg
from app.services.geofence import is_inside_geofence

router = APIRouter()
QR_TOKEN_VERSION = "pcqr1"

class ServiceTemplateCreate(BaseModel):
    name: str
    event_type: str = "service"
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str | None = None
    location: str | None = None
    qr_open_minutes_before: int = Field(default=30, ge=0, le=240)
    qr_close_minutes_after: int = Field(default=30, ge=0, le=240)
    qr_rotation_seconds: int = Field(default=60, ge=30)
    is_active: bool = True


class ServiceTemplateUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    qr_open_minutes_before: int | None = Field(default=None, ge=0, le=240)
    qr_close_minutes_after: int | None = Field(default=None, ge=0, le=240)
    qr_rotation_seconds: int | None = Field(default=None, ge=30)
    is_active: bool | None = None

class EventCreate(BaseModel):
    name: str
    event_type: str = "service"
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = None
    qr_opens_at: datetime | None = None
    qr_closes_at: datetime | None = None
    qr_rotation_seconds: int = 60

class EventUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = None
    qr_opens_at: datetime | None = None
    qr_closes_at: datetime | None = None
    qr_rotation_seconds: int | None = None

class CheckInCreate(BaseModel):
    event_id: UUID
    person_type: str
    person_id: UUID
    check_in_method: str = "manual"


class QrCheckInCreate(BaseModel):
    event_id: UUID
    qr_token: str
    person_type: str
    person_id: UUID

class GeofenceCheckInCreate(BaseModel):
    event_id: UUID
    person_type: str
    person_id: UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, gt=0)

def parse_time_value(value: str | None):
    if value is None:
        return None

    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Time values must use HH:MM format.",
        ) from exc

def serialize_service_template(
    template: ServiceTemplate,
) -> dict[str, object]:
    return {
        "id": str(template.id),
        "name": template.name,
        "event_type": template.event_type,
        "day_of_week": template.day_of_week,
        "start_time": template.start_time.strftime("%H:%M"),
        "end_time": (
            template.end_time.strftime("%H:%M")
            if template.end_time
            else None
        ),
        "location": template.location,
        "qr_open_minutes_before": template.qr_open_minutes_before,
        "qr_close_minutes_after": template.qr_close_minutes_after,
        "qr_rotation_seconds": template.qr_rotation_seconds,
        "is_active": template.is_active,
    }

def next_service_occurrence(
    day_of_week: int,
    start_time,
    *,
    from_date: datetime | None = None,
) -> datetime:
    now = from_date or utc_now()

    days_ahead = (day_of_week - now.weekday()) % 7

    occurrence = datetime.combine(
        (now + timedelta(days=days_ahead)).date(),
        start_time,
        tzinfo=now.tzinfo,
    )

    # If today's service time has already passed,
    # generate next week's occurrence instead.
    if occurrence <= now:
        occurrence += timedelta(days=7)

    return occurrence

def get_default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create or seed a branch before adding attendance records.",
        )
    return branch


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def qr_window(event: Event) -> tuple[datetime, datetime]:
    starts_at = to_utc(event.starts_at)
    opens_at = to_utc(event.qr_opens_at) if event.qr_opens_at else starts_at - timedelta(minutes=30)
    closes_at = (
        to_utc(event.qr_closes_at)
        if event.qr_closes_at
        else to_utc(event.ends_at)
        if event.ends_at
        else starts_at + timedelta(hours=2)
    )
    return opens_at, closes_at


def qr_bucket(now: datetime, rotation_seconds: int) -> int:
    return int(to_utc(now).timestamp() // max(rotation_seconds, 30))


def sign_qr_token(event_id: UUID, bucket: int) -> str:
    message = f"{QR_TOKEN_VERSION}:{event_id}:{bucket}".encode()
    digest = hmac.new(settings.qr_token_secret.encode(), message, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest[:18]).decode().rstrip("=")
    return f"{QR_TOKEN_VERSION}.{event_id}.{bucket}.{signature}"


def validate_qr_token(event: Event, token: str, now: datetime) -> None:
    opens_at, closes_at = qr_window(event)
    current = to_utc(now)
    if current < opens_at or current > closes_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="QR check-in is outside the allowed attendance window.",
        )

    parts = token.split(".")
    if len(parts) != 4 or parts[0] != QR_TOKEN_VERSION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid QR token.")

    try:
        token_event_id = UUID(parts[1])
        token_bucket = int(parts[2])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid QR token.") from exc

    if token_event_id != event.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="QR token event mismatch.")

    current_bucket = qr_bucket(current, event.qr_rotation_seconds)
    allowed_buckets = {current_bucket, current_bucket - 1}
    if token_bucket not in allowed_buckets:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="QR token expired.")

    expected = sign_qr_token(event.id, token_bucket)
    if not hmac.compare_digest(expected, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid QR token.")


def serialize_event(event: Event, check_ins: int = 0) -> dict[str, object]:
    opens_at, closes_at = qr_window(event)
    now = utc_now()
    return {
        "id": str(event.id),
        "name": event.name,
        "type": event.event_type,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat() if event.ends_at else None,
        "location": event.location,
        "qr_opens_at": opens_at.isoformat(),
        "qr_closes_at": closes_at.isoformat(),
        "qr_rotation_seconds": event.qr_rotation_seconds,
        "qr_active": opens_at <= now <= closes_at,
        "check_ins": check_ins,
    }


def serialize_attendance_record(record: AttendanceRecord, db: Session) -> dict[str, object]:
    event = db.get(Event, record.event_id)
    person: Member | Visitor | None
    household_person: HouseholdPerson | None = None
    if record.person_type == "member":
        person = db.get(Member, record.member_id)
    elif record.person_type == "visitor":
        person = db.get(Visitor, record.visitor_id)
    else:
        household_person = db.get(HouseholdPerson, record.household_person_id)
        person = None

    return {
        "id": str(record.id),
        "event_id": str(record.event_id),
        "event_name": event.name if event else "Unknown event",
        "person_type": record.person_type,
        "person_id": str(record.member_id or record.visitor_id or record.household_person_id),
        "person_name": f"{person.first_name} {person.last_name}"
        if person
        else f"{household_person.first_name} {household_person.last_name}"
        if household_person
        else "Unknown person",
        "check_in_method": record.check_in_method,
        "checked_in_at": record.checked_in_at.isoformat(),
    }


@router.get("/")
def attendance_summary(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "receptionist", "usher")),
) -> dict[str, object]:
    total_records = db.scalar(select(func.count()).select_from(AttendanceRecord)) or 0
    events = db.scalars(select(Event).order_by(Event.starts_at.asc()).limit(10)).all()
    recent_records = db.scalars(
        select(AttendanceRecord).order_by(AttendanceRecord.checked_in_at.desc()).limit(10)
    ).all()

    return {
        "module": "attendance",
        "status": "demo-data-ready",
        "total_check_ins": total_records,
        "events": [
            serialize_event(
                event,
                db.scalar(
                    select(func.count())
                    .select_from(AttendanceRecord)
                    .where(AttendanceRecord.event_id == event.id)
                )
                or 0,
            )
            for event in events
        ],
        "recent_check_ins": [serialize_attendance_record(record, db) for record in recent_records],
    }

@router.get("/events")
def list_events(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "receptionist", "usher")),
) -> list[dict[str, object]]:
    events = db.scalars(
        select(Event).order_by(Event.starts_at.asc())
    ).all()

    return [
        serialize_event(
            event,
            db.scalar(
                select(func.count())
                .select_from(AttendanceRecord)
                .where(AttendanceRecord.event_id == event.id)
            )
            or 0,
        )
        for event in events
    ]

@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "usher")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    starts_at = payload.starts_at or utc_now()
    event = Event(
        branch_id=branch.id,
        name=payload.name,
        event_type=payload.event_type,
        starts_at=starts_at,
        ends_at=payload.ends_at,
        location=payload.location,
        qr_opens_at=payload.qr_opens_at,
        qr_closes_at=payload.qr_closes_at,
        qr_rotation_seconds=max(payload.qr_rotation_seconds, 30),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return serialize_event(event)

@router.patch("/events/{event_id}")
def update_event(
    event_id: UUID,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader")),
) -> dict[str, object]:
    event = db.get(Event, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if field == "qr_rotation_seconds" and value is not None:
            value = max(value, 30)

        setattr(event, field, value)

    db.commit()
    db.refresh(event)

    return serialize_event(event)

@router.get("/service-templates")
def list_service_templates(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "administrator")),
) -> list[dict[str, object]]:
    templates = db.scalars(
        select(ServiceTemplate).order_by(
            ServiceTemplate.day_of_week.asc(),
            ServiceTemplate.start_time.asc(),
        )
    ).all()

    return [serialize_service_template(template) for template in templates]

@router.post("/service-templates", status_code=status.HTTP_201_CREATED)
def create_service_template(
    payload: ServiceTemplateCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "administrator")),
) -> dict[str, object]:
    branch = get_default_branch(db)

    template = ServiceTemplate(
        branch_id=branch.id,
        name=payload.name,
        event_type=payload.event_type,
        day_of_week=payload.day_of_week,
        start_time=parse_time_value(payload.start_time),
        end_time=parse_time_value(payload.end_time),
        location=payload.location,
        qr_open_minutes_before=payload.qr_open_minutes_before,
        qr_close_minutes_after=payload.qr_close_minutes_after,
        qr_rotation_seconds=max(payload.qr_rotation_seconds, 30),
        is_active=payload.is_active,
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return serialize_service_template(template)

@router.post("/service-templates/generate")
def generate_service_events(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "administrator")),
) -> dict[str, object]:
    templates = db.scalars(
        select(ServiceTemplate).where(
            ServiceTemplate.is_active.is_(True)
        )
    ).all()

    created_events = []
    skipped = 0

    for template in templates:
        starts_at = next_service_occurrence(
            template.day_of_week,
            template.start_time,
        )

        existing = db.scalar(
            select(Event).where(
                Event.branch_id == template.branch_id,
                Event.name == template.name,
                Event.starts_at == starts_at,
            )
        )

        if existing is not None:
            skipped += 1
            continue

        ends_at = None

        if template.end_time:
            ends_at = datetime.combine(
                starts_at.date(),
                template.end_time,
                tzinfo=starts_at.tzinfo,
            )

            if ends_at <= starts_at:
                ends_at += timedelta(days=1)

        event = Event(
            branch_id=template.branch_id,
            name=template.name,
            event_type=template.event_type,
            starts_at=starts_at,
            ends_at=ends_at,
            location=template.location,
            qr_opens_at=(
                starts_at
                - timedelta(
                    minutes=template.qr_open_minutes_before
                )
            ),
            qr_closes_at=(
                (ends_at or starts_at)
                + timedelta(
                    minutes=template.qr_close_minutes_after
                )
            ),
            qr_rotation_seconds=template.qr_rotation_seconds,
        )

        db.add(event)
        created_events.append(event)

    db.commit()

    for event in created_events:
        db.refresh(event)

    return {
        "created": len(created_events),
        "skipped": skipped,
        "events": [
            serialize_event(event)
            for event in created_events
        ],
    }
@router.patch("/service-templates/{template_id}")
def update_service_template(
    template_id: UUID,
    payload: ServiceTemplateUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "administrator")),
) -> dict[str, object]:
    template = db.get(ServiceTemplate, template_id)

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service template not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if "start_time" in updates:
        updates["start_time"] = parse_time_value(updates["start_time"])

    if "end_time" in updates:
        updates["end_time"] = parse_time_value(updates["end_time"])

    if "qr_rotation_seconds" in updates and updates["qr_rotation_seconds"] is not None:
        updates["qr_rotation_seconds"] = max(
            updates["qr_rotation_seconds"],
            30,
        )

    for field, value in updates.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)

    return serialize_service_template(template)

@router.delete(
    "/service-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_service_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "administrator")),
) -> Response:
    template = db.get(ServiceTemplate, template_id)

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service template not found.",
        )

    db.delete(template)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader")),
) -> Response:
    event = db.get(Event, event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    attendance_count = db.scalar(
        select(func.count())
        .select_from(AttendanceRecord)
        .where(AttendanceRecord.event_id == event.id)
    ) or 0

    if attendance_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Events with attendance records cannot be deleted.",
        )

    db.delete(event)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events/{event_id}/qr-token")
def get_event_qr_token(
    event_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("usher", "pastor_leader")),
) -> dict[str, object]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    now = utc_now()
    opens_at, closes_at = qr_window(event)
    active = opens_at <= now <= closes_at
    bucket = qr_bucket(now, event.qr_rotation_seconds)
    expires_at = datetime.fromtimestamp((bucket + 1) * event.qr_rotation_seconds, UTC)

    return {
        "event": serialize_event(event),
        "active": active,
        "token": sign_qr_token(event.id, bucket) if active else None,
        "opens_at": opens_at.isoformat(),
        "closes_at": closes_at.isoformat(),
        "expires_at": expires_at.isoformat() if active else None,
        "rotation_seconds": event.qr_rotation_seconds,
        "scan_path": "/api/v1/attendance/qr-check-ins",
    }


@router.get("/events/{event_id}/qr-code.svg")
def get_event_qr_code(
    event_id: UUID,
    data: str = Query(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
) -> Response:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    try:
        svg = make_qr_svg(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return Response(content=svg, media_type="image/svg+xml")


def create_attendance_record(
    payload: CheckInCreate,
    db: Session,
    *,
    require_qr_token: str | None = None,
) -> dict[str, object]:
    event = db.get(Event, payload.event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    if require_qr_token:
        validate_qr_token(event, require_qr_token, utc_now())

    if payload.person_type not in {"member", "visitor", "household_person"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="person_type must be member, visitor, or household_person.",
        )

    member_id = payload.person_id if payload.person_type == "member" else None
    visitor_id = payload.person_id if payload.person_type == "visitor" else None
    household_person_id = payload.person_id if payload.person_type == "household_person" else None
    person_model = {
        "member": Member,
        "visitor": Visitor,
        "household_person": HouseholdPerson,
    }[payload.person_type]
    person = db.get(person_model, payload.person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found.")

    duplicate = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.event_id == payload.event_id,
            AttendanceRecord.person_type == payload.person_type,
            AttendanceRecord.member_id == member_id,
            AttendanceRecord.visitor_id == visitor_id,
            AttendanceRecord.household_person_id == household_person_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This person is already checked in for the selected event.",
        )

    record = AttendanceRecord(
        branch_id=event.branch_id,
        event_id=event.id,
        person_type=payload.person_type,
        member_id=member_id,
        visitor_id=visitor_id,
        household_person_id=household_person_id,
        check_in_method=payload.check_in_method,
        checked_in_at=utc_now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return serialize_attendance_record(record, db)


@router.post("/check-ins", status_code=status.HTTP_201_CREATED)
def create_check_in(
    payload: CheckInCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("usher", "receptionist")),
) -> dict[str, object]:
    return create_attendance_record(payload, db)


@router.post("/qr-check-ins", status_code=status.HTTP_201_CREATED)
def create_qr_check_in(payload: QrCheckInCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    return create_attendance_record(
        CheckInCreate(
            event_id=payload.event_id,
            person_type=payload.person_type,
            person_id=payload.person_id,
            check_in_method="qr",
        ),
        db,
        require_qr_token=payload.qr_token,
    )

@router.post("/geofence-check-ins", status_code=status.HTTP_201_CREATED)
def create_geofence_check_in(
    payload: GeofenceCheckInCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    event = db.get(Event, payload.event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    branch = db.get(Branch, event.branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event branch not found.",
        )

    if not branch.geofence_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Geofence attendance is disabled for this branch.",
        )

    if branch.latitude is None or branch.longitude is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The branch geofence location has not been configured.",
        )

    opens_at, closes_at = qr_window(event)
    now = utc_now()

    if now < opens_at or now > closes_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Geofence check-in is outside the allowed attendance window.",
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
            event_id=payload.event_id,
            person_type=payload.person_type,
            person_id=payload.person_id,
            check_in_method="geofence",
        ),
        db,
    )

    attendance["distance_meters"] = round(distance_meters, 1)
    attendance["allowed_radius_meters"] = branch.attendance_radius_meters
    attendance["inside_geofence"] = True

    return attendance
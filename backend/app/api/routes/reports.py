import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import (
    AttendanceRecord,
    Contribution,
    Event,
    HouseholdPerson,
    Member,
    Message,
    Visitor,
)

router = APIRouter()


def current_week_period() -> tuple[datetime, datetime]:
    now = utc_now()
    starts_at = (now - timedelta(days=now.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return starts_at, starts_at + timedelta(days=7)


def decimal_text(value: Decimal | None) -> str:
    return str(value or Decimal("0.00"))


def count_rows(db: Session, model: type, *conditions: object) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def weekly_observations(
    *,
    attendance_total: int,
    giving_total: Decimal,
    new_visitors: int,
    scheduled_messages: int,
    inactive_members: int,
    household_dependents: int,
) -> list[dict[str, str]]:
    observations: list[dict[str, str]] = []

    if attendance_total == 0:
        observations.append(
            {
                "tone": "warn",
                "title": "No attendance captured",
                "detail": "This week has no attendance records yet, so service reporting may be incomplete.",
            }
        )
    else:
        observations.append(
            {
                "tone": "good",
                "title": "Attendance flow is active",
                "detail": f"{attendance_total} check-ins have been recorded during this reporting week.",
            }
        )

    if giving_total > 0:
        observations.append(
            {
                "tone": "good",
                "title": "Stewardship records available",
                "detail": f"{decimal_text(giving_total)} has been recorded this week across giving channels.",
            }
        )

    if new_visitors > 0:
        observations.append(
            {
                "tone": "info",
                "title": "Visitor follow-up needed",
                "detail": f"{new_visitors} new visitor records were created this week.",
            }
        )

    if scheduled_messages > 0:
        observations.append(
            {
                "tone": "info",
                "title": "Scheduled communication pending",
                "detail": f"{scheduled_messages} scheduled messages are waiting for delivery.",
            }
        )

    if household_dependents > 0:
        observations.append(
            {
                "tone": "good",
                "title": "Family check-in is supported",
                "detail": f"{household_dependents} children or dependents can be handled through households.",
            }
        )

    if inactive_members > 0:
        observations.append(
            {
                "tone": "warn",
                "title": "Pastoral lifecycle review",
                "detail": f"{inactive_members} member records are marked transferred, deceased, or discontinued.",
            }
        )

    return observations


def build_weekly_report(db: Session) -> dict[str, object]:
    starts_at, ends_at = current_week_period()
    attendance_filters = (
        AttendanceRecord.checked_in_at >= starts_at,
        AttendanceRecord.checked_in_at < ends_at,
    )
    contribution_filters = (
        Contribution.received_at >= starts_at,
        Contribution.received_at < ends_at,
    )
    message_filters = (
        Message.created_at >= starts_at,
        Message.created_at < ends_at,
    )

    attendance_total = count_rows(db, AttendanceRecord, *attendance_filters)
    attendance_by_method = db.execute(
        select(AttendanceRecord.check_in_method, func.count(AttendanceRecord.id))
        .where(*attendance_filters)
        .group_by(AttendanceRecord.check_in_method)
        .order_by(func.count(AttendanceRecord.id).desc())
    ).all()
    attendance_by_event = db.execute(
        select(Event.name, func.count(AttendanceRecord.id))
        .join(AttendanceRecord, AttendanceRecord.event_id == Event.id)
        .where(*attendance_filters)
        .group_by(Event.name)
        .order_by(func.count(AttendanceRecord.id).desc())
    ).all()

    contribution_total = db.scalar(
        select(func.coalesce(func.sum(Contribution.amount), Decimal("0.00"))).where(
            *contribution_filters
        )
    )
    contribution_count = count_rows(db, Contribution, *contribution_filters)
    contribution_currency = db.scalar(
        select(Contribution.currency)
        .where(*contribution_filters)
        .order_by(Contribution.received_at.desc())
        .limit(1)
    ) or "TZS"
    contribution_by_type = db.execute(
        select(
            Contribution.contribution_type,
            func.coalesce(func.sum(Contribution.amount), Decimal("0.00")),
            func.count(Contribution.id),
        )
        .where(*contribution_filters)
        .group_by(Contribution.contribution_type)
        .order_by(func.sum(Contribution.amount).desc())
    ).all()
    contribution_by_payment = db.execute(
        select(
            Contribution.payment_method,
            func.coalesce(func.sum(Contribution.amount), Decimal("0.00")),
            func.count(Contribution.id),
        )
        .where(*contribution_filters)
        .group_by(Contribution.payment_method)
        .order_by(func.sum(Contribution.amount).desc())
    ).all()

    total_messages = count_rows(db, Message, *message_filters)
    sent_messages = count_rows(
        db,
        Message,
        Message.status == "sent",
        Message.sent_at >= starts_at,
        Message.sent_at < ends_at,
    )
    scheduled_messages = count_rows(db, Message, Message.status == "scheduled")
    messages_by_channel = db.execute(
        select(Message.channel, func.count(Message.id))
        .where(*message_filters)
        .group_by(Message.channel)
        .order_by(func.count(Message.id).desc())
    ).all()

    new_visitors = count_rows(
        db,
        Visitor,
        Visitor.created_at >= starts_at,
        Visitor.created_at < ends_at,
    )
    converted_visitors = count_rows(db, Visitor, Visitor.follow_up_status == "converted")
    active_members = count_rows(db, Member, Member.membership_status == "active")
    inactive_members = count_rows(db, Member, Member.membership_status != "active")
    household_dependents = count_rows(
        db,
        HouseholdPerson,
        HouseholdPerson.status == "active",
        HouseholdPerson.can_self_check_in == "no",
    )

    return {
        "module": "reports",
        "status": "demo-data-ready",
        "period": {
            "start": starts_at.isoformat(),
            "end": ends_at.isoformat(),
            "label": f"Week of {starts_at.date().isoformat()}",
        },
        "attendance": {
            "total": attendance_total,
            "members": count_rows(
                db,
                AttendanceRecord,
                *attendance_filters,
                AttendanceRecord.person_type == "member",
            ),
            "visitors": count_rows(
                db,
                AttendanceRecord,
                *attendance_filters,
                AttendanceRecord.person_type == "visitor",
            ),
            "household_dependents": count_rows(
                db,
                AttendanceRecord,
                *attendance_filters,
                AttendanceRecord.person_type == "household_person",
            ),
            "by_method": [
                {"method": method, "count": count}
                for method, count in attendance_by_method
            ],
            "by_event": [
                {"event_name": event_name, "count": count}
                for event_name, count in attendance_by_event
            ],
        },
        "stewardship": {
            "total_amount": decimal_text(contribution_total),
            "currency": contribution_currency,
            "count": contribution_count,
            "by_type": [
                {"type": contribution_type, "amount": decimal_text(amount), "count": count}
                for contribution_type, amount, count in contribution_by_type
            ],
            "by_payment_method": [
                {"method": method, "amount": decimal_text(amount), "count": count}
                for method, amount, count in contribution_by_payment
            ],
        },
        "communication": {
            "total_messages": total_messages,
            "sent": sent_messages,
            "scheduled": scheduled_messages,
            "by_channel": [
                {"channel": channel, "count": count}
                for channel, count in messages_by_channel
            ],
        },
        "people": {
            "new_visitors": new_visitors,
            "converted_visitors": converted_visitors,
            "active_members": active_members,
            "inactive_members": inactive_members,
            "household_dependents": household_dependents,
        },
        "observations": weekly_observations(
            attendance_total=attendance_total,
            giving_total=contribution_total or Decimal("0.00"),
            new_visitors=new_visitors,
            scheduled_messages=scheduled_messages,
            inactive_members=inactive_members,
            household_dependents=household_dependents,
        ),
    }


def render_weekly_briefing(report: dict[str, object]) -> str:
    period = report["period"]
    attendance = report["attendance"]
    stewardship = report["stewardship"]
    communication = report["communication"]
    people = report["people"]
    observations = report["observations"]

    lines = [
        "ParishConnect Weekly Leadership Briefing",
        str(period["label"]),
        "",
        "Attendance",
        f"- Total check-ins: {attendance['total']}",
        f"- Members: {attendance['members']}",
        f"- Visitors: {attendance['visitors']}",
        f"- Household dependents: {attendance['household_dependents']}",
        "",
        "Stewardship",
        f"- Total giving: {stewardship['total_amount']} {stewardship['currency']}",
        f"- Contribution records: {stewardship['count']}",
        "",
        "Communication",
        f"- Messages created: {communication['total_messages']}",
        f"- Sent this week: {communication['sent']}",
        f"- Scheduled: {communication['scheduled']}",
        "",
        "People",
        f"- New visitors: {people['new_visitors']}",
        f"- Converted visitors: {people['converted_visitors']}",
        f"- Active members: {people['active_members']}",
        f"- Pastoral lifecycle records: {people['inactive_members']}",
        "",
        "Critical Observations",
    ]
    lines.extend(f"- {item['title']}: {item['detail']}" for item in observations)
    return "\n".join(lines) + "\n"


def render_weekly_csv(report: dict[str, object]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "metric", "value", "detail"])

    attendance = report["attendance"]
    stewardship = report["stewardship"]
    communication = report["communication"]
    people = report["people"]
    observations = report["observations"]

    writer.writerow(["attendance", "total_check_ins", attendance["total"], ""])
    writer.writerow(["attendance", "members", attendance["members"], ""])
    writer.writerow(["attendance", "visitors", attendance["visitors"], ""])
    writer.writerow(["attendance", "household_dependents", attendance["household_dependents"], ""])
    for event in attendance["by_event"]:
        writer.writerow(["attendance_by_event", event["event_name"], event["count"], "check-ins"])
    for method in attendance["by_method"]:
        writer.writerow(["attendance_by_method", method["method"], method["count"], "records"])

    writer.writerow(
        [
            "stewardship",
            "total_giving",
            stewardship["total_amount"],
            stewardship["currency"],
        ]
    )
    writer.writerow(["stewardship", "contribution_records", stewardship["count"], ""])
    for item in stewardship["by_type"]:
        writer.writerow(["stewardship_by_type", item["type"], item["amount"], item["count"]])
    for item in stewardship["by_payment_method"]:
        writer.writerow(["stewardship_by_payment", item["method"], item["amount"], item["count"]])

    writer.writerow(["communication", "messages_created", communication["total_messages"], ""])
    writer.writerow(["communication", "sent", communication["sent"], ""])
    writer.writerow(["communication", "scheduled", communication["scheduled"], ""])
    writer.writerow(["people", "new_visitors", people["new_visitors"], ""])
    writer.writerow(["people", "converted_visitors", people["converted_visitors"], ""])
    writer.writerow(["people", "active_members", people["active_members"], ""])
    writer.writerow(["people", "inactive_members", people["inactive_members"], ""])
    for item in observations:
        writer.writerow(["observation", item["title"], item["tone"], item["detail"]])
    return output.getvalue()


@router.get("/weekly")
def weekly_report(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "accountant")),
) -> dict[str, object]:
    return build_weekly_report(db)


@router.get("/weekly/briefing", response_class=PlainTextResponse)
def weekly_report_briefing(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "accountant")),
) -> str:
    return render_weekly_briefing(build_weekly_report(db))


@router.get("/weekly.csv", response_class=PlainTextResponse)
def weekly_report_csv(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "accountant")),
) -> str:
    return render_weekly_csv(build_weekly_report(db))

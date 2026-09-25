"""Keep ORM-based staff creation/import/seed paths compatible with identity tables.

Connection-level mapper events stay in the caller's transaction. Migrations
perform the same backfill for existing records. External SQL writers must use
the API or run the documented reconciliation; no email-based automatic claiming.
"""

from uuid import uuid4

from sqlalchemy import event, inspect, select

from app.db.base import utc_now
from app.models import ChurchMembership, Member, Profile, User


def membership_status(value: str | None) -> str:
    if value in {"pending", "active", "inactive", "former", "suspended"}:
        return value
    return "former" if value in {"transferred", "deceased", "discontinued"} else "inactive"


@event.listens_for(Member, "after_insert")
def add_offline_membership(mapper, connection, member):
    now = utc_now()
    connection.execute(
        ChurchMembership.__table__.insert().values(
            id=uuid4(),
            church_id=member.branch_id,
            legacy_member_id=member.id,
            status=membership_status(member.membership_status),
            role="member",
            is_primary=False,
            joined_at=member.joined_at,
            created_at=now,
            updated_at=now,
        )
    )


@event.listens_for(Member, "after_update")
def sync_legacy_status(mapper, connection, member):
    if inspect(member).attrs.membership_status.history.has_changes():
        state = membership_status(member.membership_status)
        values = {"status": state, "updated_at": utc_now()}
        if state != "active":
            values["is_primary"] = False
        connection.execute(
            ChurchMembership.__table__.update()
            .where(ChurchMembership.legacy_member_id == member.id)
            .values(**values)
        )


@event.listens_for(User, "after_insert")
def add_user_identity(mapper, connection, user):
    first, _, last = user.name.partition(" ")
    now = utc_now()
    connection.execute(
        Profile.__table__.insert().values(
            user_id=user.id,
            first_name=first[:100],
            last_name=last[:100],
            phone=user.phone,
            created_at=now,
            updated_at=now,
        )
    )
    if user.member_id:
        membership = (
            connection.execute(
                select(ChurchMembership.__table__).where(
                    ChurchMembership.legacy_member_id == user.member_id
                )
            )
            .mappings()
            .first()
        )
        if membership and (user.branch_id is None or user.branch_id == membership["church_id"]):
            connection.execute(
                ChurchMembership.__table__.update()
                .where(ChurchMembership.id == membership["id"], ChurchMembership.user_id.is_(None))
                .values(
                    user_id=user.id, is_primary=membership["status"] == "active", updated_at=now
                )
            )

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Integer, Numeric, String, Text, Time, DateTime, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, utc_now
from datetime import datetime, time, date

class Branch(IdMixin, TimestampMixin, Base):
    __tablename__ = "branches"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    location: Mapped[str | None] = mapped_column(String(240))
    contact_phone: Mapped[str | None] = mapped_column(String(40))

    denomination: Mapped[str | None] = mapped_column(String(120))
    default_language: Mapped[str] = mapped_column(String(10), default="en")
    timezone: Mapped[str] = mapped_column(String(80), default="Africa/Dar_es_Salaam")
    community_label: Mapped[str] = mapped_column(
       String(120),
       default="Community Group",
    )

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    attendance_radius_meters: Mapped[int] = mapped_column(Integer, default=100)
    geofence_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    branch_id: Mapped[UUID | None] = mapped_column(ForeignKey("branches.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active")


class Role(IdMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), primary_key=True)


class AuditLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    branch_id: Mapped[UUID | None] = mapped_column(ForeignKey("branches.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID | None]
    metadata_json: Mapped[str | None] = mapped_column(Text)


class ImportBatch(IdMixin, TimestampMixin, Base):
    __tablename__ = "imports"

    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    import_type: Mapped[str] = mapped_column(String(40), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="completed")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    successful_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class Member(IdMixin, TimestampMixin, Base):
    __tablename__ = "members"

    branch_id: Mapped[UUID] = mapped_column(
        ForeignKey("branches.id"),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))

    # Existing fields — KEEP
    membership_status: Mapped[str] = mapped_column(
        String(40),
        default="active",
    )
    joined_at: Mapped[datetime | None]

    # New profile fields
    address: Mapped[str | None] = mapped_column(String(255))
    area: Mapped[str | None] = mapped_column(String(120))
    gender: Mapped[str | None] = mapped_column(String(40))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    marital_status: Mapped[str | None] = mapped_column(String(40))
    occupation: Mapped[str | None] = mapped_column(String(120))
    preferred_language: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
class Visitor(IdMixin, TimestampMixin, Base):
    __tablename__ = "visitors"

    branch_id: Mapped[UUID] = mapped_column(
        ForeignKey("branches.id"),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))

    # Existing fields — KEEP
    follow_up_status: Mapped[str] = mapped_column(
        String(40),
        default="new",
    )

    converted_member_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("members.id")
    )

    # New profile fields
    address: Mapped[str | None] = mapped_column(String(255))
    area: Mapped[str | None] = mapped_column(String(120))
    gender: Mapped[str | None] = mapped_column(String(40))
    preferred_language: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)

class Household(IdMixin, TimestampMixin, Base):
    __tablename__ = "households"

    branch_id: Mapped[UUID] = mapped_column(
        ForeignKey("branches.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    primary_member_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("members.id")
    )

    primary_phone: Mapped[str | None] = mapped_column(String(40))

    notes: Mapped[str | None] = mapped_column(Text)
class HouseholdPerson(IdMixin, TimestampMixin, Base):
    __tablename__ = "household_people"

    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    member_id: Mapped[UUID | None] = mapped_column(ForeignKey("members.id"))
    visitor_id: Mapped[UUID | None] = mapped_column(ForeignKey("visitors.id"))
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(40))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    preferred_language: Mapped[str | None] = mapped_column(String(10))
    person_type: Mapped[str] = mapped_column(String(40), nullable=False)
    relationship: Mapped[str] = mapped_column(String(60), nullable=False)
    can_self_check_in: Mapped[str] = mapped_column(String(5), default="yes")
    status: Mapped[str] = mapped_column(String(40), default="active")

class CommunityGroup(IdMixin, TimestampMixin, Base):
    __tablename__ = "community_groups"

    branch_id: Mapped[UUID] = mapped_column(
        ForeignKey("branches.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    group_type: Mapped[str] = mapped_column(
        String(80),
        default="local_community",
    )

    leader_member_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("members.id")
    )

    area: Mapped[str | None] = mapped_column(String(120))
    meeting_day: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(40),
        default="active",
    )


class CommunityGroupMembership(IdMixin, TimestampMixin, Base):
    __tablename__ = "community_group_memberships"
    __table_args__=(
        UniqueConstraint(
            "community_group_id","member_id",
            name="uq_community_group_membership_member",
        ),
    )

    community_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("community_groups.id"),
        nullable=False,
    )

    member_id: Mapped[UUID] = mapped_column(
        ForeignKey("members.id"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(40),
        default="member",
    )

    status: Mapped[str] = mapped_column(
        String(40),
        default="active",
    )

    joined_at: Mapped[datetime | None]
class Ministry(IdMixin, TimestampMixin, Base):
    __tablename__ = "ministries"

    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    leader_member_id: Mapped[UUID | None] = mapped_column(ForeignKey("members.id"))

class ServiceTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "service_templates"

    branch_id: Mapped[UUID] = mapped_column(
        ForeignKey("branches.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(80),
        default="service",
        nullable=False,
    )

    day_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[time | None] = mapped_column(
        Time,
    )

    location: Mapped[str | None] = mapped_column(
        String(240),
    )

    qr_open_minutes_before: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    qr_close_minutes_after: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    qr_rotation_seconds: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
class Event(IdMixin, TimestampMixin, Base):
    __tablename__ = "events"

    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    ministry_id: Mapped[UUID | None] = mapped_column(ForeignKey("ministries.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), default="service")
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime | None]
    location: Mapped[str | None] = mapped_column(String(240))
    qr_opens_at: Mapped[datetime | None]
    qr_closes_at: Mapped[datetime | None]
    qr_rotation_seconds: Mapped[int] = mapped_column(default=60)
    attendance_status: Mapped[str] = mapped_column(
    String(20),
    default="scheduled",
    )

    attendance_opened_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    )

    attendance_closed_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    ) 


class AttendanceRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "attendance_records"

    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), nullable=False)
    person_type: Mapped[str] = mapped_column(String(20), nullable=False)
    member_id: Mapped[UUID | None] = mapped_column(ForeignKey("members.id"))
    visitor_id: Mapped[UUID | None] = mapped_column(ForeignKey("visitors.id"))
    household_person_id: Mapped[UUID | None] = mapped_column(ForeignKey("household_people.id"))
    checked_in_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    check_in_method: Mapped[str] = mapped_column(String(40), default="manual")
    checked_in_at: Mapped[datetime] = mapped_column(default=utc_now)
    corrected_at: Mapped[datetime | None]


class Message(IdMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    sender_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience_type: Mapped[str] = mapped_column(String(80), default="all_members")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    scheduled_at: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]


class MessageRecipient(IdMixin, TimestampMixin, Base):
    __tablename__ = "message_recipients"

    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id"), nullable=False)
    member_id: Mapped[UUID | None] = mapped_column(ForeignKey("members.id"))
    visitor_id: Mapped[UUID | None] = mapped_column(ForeignKey("visitors.id"))
    phone: Mapped[str | None] = mapped_column(String(40))
    delivery_status: Mapped[str] = mapped_column(String(40), default="queued")
    provider_reference: Mapped[str | None] = mapped_column(String(120))


class Contribution(IdMixin, TimestampMixin, Base):
    __tablename__ = "contributions"

    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    member_id: Mapped[UUID | None] = mapped_column(ForeignKey("members.id"))
    household_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("households.id")
    )
    
    contributor_scope: Mapped[str] = mapped_column(
        String(20),
        default="individual",
    )
    contribution_type: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    payment_method: Mapped[str] = mapped_column(String(40), default="cash")
    reference_code: Mapped[str | None] = mapped_column(String(120))
    received_at: Mapped[datetime] = mapped_column(default=utc_now)
    recorded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
   
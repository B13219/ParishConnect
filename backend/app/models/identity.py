"""Global accounts and church-local relationships; credentials remain in users."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(40))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))


class ChurchMembership(IdMixin, TimestampMixin, Base):
    __tablename__ = "church_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["legacy_member_id", "church_id"],
            ["members.id", "members.branch_id"],
            name="fk_membership_legacy_church",
        ),
        UniqueConstraint("church_id", "user_id", name="uq_church_membership_user"),
        UniqueConstraint("legacy_member_id", name="uq_church_membership_legacy"),
        UniqueConstraint("church_id", "membership_number", name="uq_church_membership_number"),
        CheckConstraint("user_id IS NOT NULL OR legacy_member_id IS NOT NULL", name="identity"),
        CheckConstraint(
            "status IN ('pending','active','inactive','former','suspended')", name="status"
        ),
        CheckConstraint(
            "NOT is_primary OR (user_id IS NOT NULL AND status = 'active')", name="primary_active"
        ),
        Index(
            "uq_church_membership_primary",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary = 1"),
        ),
        Index("ix_church_memberships_user_id", "user_id"),
        Index("ix_church_memberships_church_status", "church_id", "status"),
    )

    church_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    legacy_member_id: Mapped[UUID | None] = mapped_column(ForeignKey("members.id"))
    membership_number: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    role: Mapped[str] = mapped_column(String(40), default="member")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class MembershipRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "membership_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["matched_member_id", "church_id"],
            ["members.id", "members.branch_id"],
            name="fk_request_matched_church",
        ),
        CheckConstraint(
            "status IN ('pending','approved','rejected','more_info_required','cancelled')",
            name="status",
        ),
        Index(
            "uq_membership_request_open",
            "user_id",
            "church_id",
            unique=True,
            postgresql_where=text("status IN ('pending','more_info_required')"),
            sqlite_where=text("status IN ('pending','more_info_required')"),
        ),
        Index("ix_membership_requests_church_status", "church_id", "status"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    church_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    message: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    matched_member_id: Mapped[UUID | None] = mapped_column(ForeignKey("members.id"))


class ChurchFollow(IdMixin, TimestampMixin, Base):
    __tablename__ = "church_follows"
    __table_args__ = (UniqueConstraint("user_id", "church_id", name="uq_church_follow"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    church_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), index=True)

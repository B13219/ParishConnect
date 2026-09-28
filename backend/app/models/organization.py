"""Organization structure is not a replacement for operational Branch tenancy."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class OrganizationUnit(IdMixin, TimestampMixin, Base):
    __tablename__ = "organization_units"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_self_parent"),
        CheckConstraint("status IN ('active','inactive')", name="status"),
        Index("ix_org_unit_parent", "parent_id"),
        Index("ix_org_unit_match", "match_key"),
        Index("uq_org_unit_owner_match", "owner_branch_id", "match_key", unique=True),
    )

    denomination: Mapped[str] = mapped_column(String(120))
    level_key: Mapped[str] = mapped_column(String(80))
    canonical_name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_units.id"))
    country: Mapped[str | None] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    localized_names: Mapped[dict] = mapped_column(JSON, default=dict)
    labels_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_managed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    # Custody of the record does not assert denomination-wide governance authority.
    owner_branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), index=True)
    match_key: Mapped[str] = mapped_column(String(64))


class ChurchOrganizationConfiguration(TimestampMixin, Base):
    __tablename__ = "church_organization_configurations"
    __table_args__ = (
        CheckConstraint("setup_status IN ('draft','configured','custom_required')", name="status"),
    )
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), primary_key=True)
    denomination: Mapped[str] = mapped_column(String(120))
    template_version: Mapped[int | None] = mapped_column(Integer)
    local_unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("organization_units.id"))
    setup_status: Mapped[str] = mapped_column(String(30), default="draft")
    configured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    configured_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    terminology_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    hierarchy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmation_fingerprint: Mapped[str] = mapped_column(String(64))


class OrganizationOfficeAssignment(IdMixin, TimestampMixin, Base):
    __tablename__ = "organization_office_assignments"
    __table_args__ = (
        CheckConstraint("status IN ('active','inactive')", name="status"),
        Index("ix_org_assignment_user_status", "user_id", "status"),
        Index("uq_org_assignment", "organization_unit_id", "user_id", "position_key", unique=True),
    )
    organization_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_units.id"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    position_key: Mapped[str] = mapped_column(String(120))
    permission_role: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active")
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), index=True)

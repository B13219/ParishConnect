"""create missing recurring service templates table

Revision ID: 20260921_0013
Revises: 20260920_0012
Create Date: 2026-09-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260921_0013"
down_revision: str | None = "20260920_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_templates",
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("location", sa.String(length=240), nullable=True),
        sa.Column("qr_open_minutes_before", sa.Integer(), nullable=False),
        sa.Column("qr_close_minutes_after", sa.Integer(), nullable=False),
        sa.Column("qr_rotation_seconds", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_service_templates_branch_id_branches"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_templates")),
    )


def downgrade() -> None:
    op.drop_table("service_templates")

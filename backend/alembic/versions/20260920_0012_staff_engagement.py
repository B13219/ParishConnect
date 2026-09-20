"""add staff engagement workflow fields

Revision ID: 20260920_0012
Revises: 20260920_0011
Create Date: 2026-09-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260920_0012"
down_revision: str | None = "20260920_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prayer_requests",
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "prayer_requests",
        sa.Column("pastoral_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "prayer_requests",
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "prayer_requests",
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_prayer_requests_assigned_user_id_users"),
        "prayer_requests",
        "users",
        ["assigned_user_id"],
        ["id"],
    )

    op.add_column(
        "events",
        sa.Column("sermon_title", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("sermon_speaker", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("sermon_scripture", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("sermon_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "events",
        sa.Column("sermon_published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("events", "sermon_published_at")
    op.drop_column("events", "sermon_summary")
    op.drop_column("events", "sermon_scripture")
    op.drop_column("events", "sermon_speaker")
    op.drop_column("events", "sermon_title")

    op.drop_constraint(
        op.f("fk_prayer_requests_assigned_user_id_users"),
        "prayer_requests",
        type_="foreignkey",
    )
    op.drop_column("prayer_requests", "answered_at")
    op.drop_column("prayer_requests", "contacted_at")
    op.drop_column("prayer_requests", "pastoral_notes")
    op.drop_column("prayer_requests", "assigned_user_id")

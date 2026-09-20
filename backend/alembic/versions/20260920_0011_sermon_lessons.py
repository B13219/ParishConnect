"""add private sermon lessons

Revision ID: 20260920_0011
Revises: 20260920_0010
Create Date: 2026-09-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260920_0011"
down_revision: str | None = "20260920_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sermon_lessons",
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("sermon_title", sa.String(length=160), nullable=False),
        sa.Column("speaker_name", sa.String(length=160), nullable=True),
        sa.Column("scripture_reference", sa.String(length=160), nullable=True),
        sa.Column("key_lesson", sa.Text(), nullable=False),
        sa.Column("action_point", sa.Text(), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_sermon_lessons_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_sermon_lessons_member_id_members"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_sermon_lessons_event_id_events"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sermon_lessons")),
    )


def downgrade() -> None:
    op.drop_table("sermon_lessons")

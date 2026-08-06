"""add message recipients

Revision ID: 20260711_0007
Revises: 20260711_0006
Create Date: 2026-07-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260711_0007"
down_revision: str | None = "20260711_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_recipients",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("visitor_id", sa.Uuid(), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("delivery_status", sa.String(length=40), nullable=False),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_message_recipients_member_id_members"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_recipients_message_id_messages"),
        ),
        sa.ForeignKeyConstraint(
            ["visitor_id"],
            ["visitors.id"],
            name=op.f("fk_message_recipients_visitor_id_visitors"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_recipients")),
    )


def downgrade() -> None:
    op.drop_table("message_recipients")

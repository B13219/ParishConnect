"""add member prayer requests

Revision ID: 20260920_0010
Revises: 20260920_0009
Create Date: 2026-09-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260920_0010"
down_revision: str | None = "20260920_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prayer_requests",
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=40), nullable=False),
        sa.Column("allow_contact", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_prayer_requests_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_prayer_requests_member_id_members"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prayer_requests")),
    )


def downgrade() -> None:
    op.drop_table("prayer_requests")

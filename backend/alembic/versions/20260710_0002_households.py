"""add household registry

Revision ID: 20260710_0002
Revises: 20260710_0001
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260710_0002"
down_revision: str | None = "20260710_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("primary_member_id", sa.Uuid(), nullable=True),
        sa.Column("primary_phone", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_households_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["primary_member_id"],
            ["members.id"],
            name=op.f("fk_households_primary_member_id_members"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_households")),
    )
    op.create_table(
        "household_people",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("visitor_id", sa.Uuid(), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("person_type", sa.String(length=40), nullable=False),
        sa.Column("relationship", sa.String(length=60), nullable=False),
        sa.Column("can_self_check_in", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_household_people_household_id_households"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_household_people_member_id_members"),
        ),
        sa.ForeignKeyConstraint(
            ["visitor_id"],
            ["visitors.id"],
            name=op.f("fk_household_people_visitor_id_visitors"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_household_people")),
    )


def downgrade() -> None:
    op.drop_table("household_people")
    op.drop_table("households")


"""link users to member profiles

Revision ID: 20260920_0009
Revises: d685ae3baed4
Create Date: 2026-09-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260920_0009"
down_revision: str | None = "d685ae3baed4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("member_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_users_member_id_members"),
        "users",
        "members",
        ["member_id"],
        ["id"],
    )
    op.create_unique_constraint("uq_users_member_id", "users", ["member_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_member_id", "users", type_="unique")
    op.drop_constraint(
        op.f("fk_users_member_id_members"),
        "users",
        type_="foreignkey",
    )
    op.drop_column("users", "member_id")

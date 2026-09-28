"""Persistent organization setup; no legacy backfill or new access grants."""

import sqlalchemy as sa

from alembic import op

revision = "20260927_0019"
down_revision = "20260927_0018"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(name, sa.DateTime(timezone=True), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade():
    op.create_table(
        "organization_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("denomination", sa.String(120), nullable=False),
        sa.Column("level_key", sa.String(80), nullable=False),
        sa.Column("canonical_name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("organization_units.id")),
        sa.Column("country", sa.String(2)),
        sa.Column("region", sa.String(100)),
        sa.Column("city", sa.String(100)),
        sa.Column("localized_names", sa.JSON(), nullable=False),
        sa.Column("labels_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_managed", sa.Boolean(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("owner_branch_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("match_key", sa.String(64), nullable=False),
        *timestamps(),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_self_parent"),
        sa.CheckConstraint("status IN ('active','inactive')", name="status"),
    )
    for name, columns, unique in (
        ("ix_org_unit_parent", ["parent_id"], False),
        ("ix_org_unit_match", ["match_key"], False),
        ("ix_organization_units_owner_branch_id", ["owner_branch_id"], False),
        ("uq_org_unit_owner_match", ["owner_branch_id", "match_key"], True),
    ):
        op.create_index(name, "organization_units", columns, unique=unique)
    op.add_column("branches", sa.Column("organization_unit_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_branches_organization_unit_id_organization_units",
        "branches",
        "organization_units",
        ["organization_unit_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_branches_organization_unit_id", "branches", ["organization_unit_id"]
    )
    op.create_table(
        "church_organization_configurations",
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("denomination", sa.String(120), nullable=False),
        sa.Column("template_version", sa.Integer()),
        sa.Column("local_unit_id", sa.Uuid(), sa.ForeignKey("organization_units.id")),
        sa.Column("setup_status", sa.String(30), nullable=False),
        sa.Column("configured_at", sa.DateTime(timezone=True)),
        sa.Column("configured_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("terminology_snapshot", sa.JSON(), nullable=False),
        sa.Column("hierarchy_snapshot", sa.JSON(), nullable=False),
        sa.Column("confirmation_fingerprint", sa.String(64), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "setup_status IN ('draft','configured','custom_required')", name="status"
        ),
    )
    op.create_table(
        "organization_office_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_unit_id",
            sa.Uuid(),
            sa.ForeignKey("organization_units.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("position_key", sa.String(120), nullable=False),
        sa.Column("permission_role", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=False),
        *timestamps(),
        sa.CheckConstraint("status IN ('active','inactive')", name="status"),
    )
    for name, columns, unique in (
        (
            "ix_organization_office_assignments_organization_unit_id",
            ["organization_unit_id"],
            False,
        ),
        ("ix_organization_office_assignments_branch_id", ["branch_id"], False),
        ("ix_org_assignment_user_status", ["user_id", "status"], False),
        ("uq_org_assignment", ["organization_unit_id", "user_id", "position_key"], True),
    ):
        op.create_index(name, "organization_office_assignments", columns, unique=unique)

    def admin(branch):
        return f"""EXISTS (SELECT 1 FROM users u JOIN user_roles ur ON ur.user_id=u.id
        JOIN roles r ON r.id=ur.role_id
        WHERE u.id=nullif(current_setting('vinyrd.user_id',true),'')::uuid
        AND u.status='active' AND u.branch_id={branch} AND r.name='Administrator')"""

    for table in (
        "organization_units",
        "church_organization_configurations",
        "organization_office_assignments",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
    unit_admin = admin("organization_units.owner_branch_id")
    op.execute(f"""CREATE POLICY read_unit ON organization_units FOR SELECT
        USING ((is_published AND status='active') OR {unit_admin})""")
    op.execute(
        f"CREATE POLICY create_unit ON organization_units FOR INSERT WITH CHECK ({unit_admin})"
    )
    # Units are immutable in this phase. No UPDATE/DELETE policies, including for custodians.
    config_admin = admin("church_organization_configurations.branch_id")
    op.execute(
        f"CREATE POLICY read_configuration ON church_organization_configurations FOR SELECT USING ({config_admin})"
    )
    op.execute(
        f"CREATE POLICY create_configuration ON church_organization_configurations FOR INSERT WITH CHECK ({config_admin})"
    )
    op.execute(f"""CREATE POLICY edit_configuration ON church_organization_configurations FOR UPDATE
        USING ({config_admin}) WITH CHECK ({config_admin})""")
    assignment_admin = admin("organization_office_assignments.branch_id")
    assignment_check = f"""{assignment_admin} AND EXISTS (
        SELECT 1 FROM branches b JOIN users target ON target.branch_id=b.id
        WHERE b.id=organization_office_assignments.branch_id
        AND b.organization_unit_id=organization_office_assignments.organization_unit_id
        AND target.id=organization_office_assignments.user_id AND target.status='active')"""
    op.execute(f"""CREATE POLICY read_assignment ON organization_office_assignments FOR SELECT
        USING ({assignment_admin} OR user_id=nullif(current_setting('vinyrd.user_id',true),'')::uuid)""")
    op.execute(
        f"CREATE POLICY create_assignment ON organization_office_assignments FOR INSERT WITH CHECK ({assignment_check})"
    )
    op.execute(f"""CREATE POLICY edit_assignment ON organization_office_assignments FOR UPDATE
        USING ({assignment_admin}) WITH CHECK ({assignment_check})""")


def downgrade():
    raise RuntimeError("Keep additive organization data when rolling back application code.")

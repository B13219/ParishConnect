"""Add global identity relationships without replacing legacy records.

Revision ID: 20260925_0015
Revises: 20260921_0014
"""

import sqlalchemy as sa

from alembic import op

revision = "20260925_0015"
down_revision = "20260921_0014"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    # Fail safely rather than silently merging distinct legacy logins.
    op.create_index("uq_users_email_normalized", "users", [sa.text("lower(email)")], unique=True)
    op.add_column(
        "users",
        sa.Column("identity_self_managed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(40)),
        sa.Column("avatar_url", sa.String(2048)),
        sa.Column("country", sa.String(100)),
        sa.Column("region", sa.String(100)),
        sa.Column("city", sa.String(100)),
        *timestamps(),
    )
    op.create_unique_constraint("uq_members_id_branch", "members", ["id", "branch_id"])
    op.create_table(
        "church_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("church_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("legacy_member_id", sa.Uuid(), sa.ForeignKey("members.id")),
        sa.Column("membership_number", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id")),
        *timestamps(),
        sa.UniqueConstraint("church_id", "user_id", name="uq_church_membership_user"),
        sa.UniqueConstraint("legacy_member_id", name="uq_church_membership_legacy"),
        sa.UniqueConstraint("church_id", "membership_number", name="uq_church_membership_number"),
        sa.CheckConstraint("user_id IS NOT NULL OR legacy_member_id IS NOT NULL", name="identity"),
        sa.CheckConstraint(
            "status IN ('pending','active','inactive','former','suspended')", name="status"
        ),
        sa.CheckConstraint(
            "NOT is_primary OR (user_id IS NOT NULL AND status = 'active')", name="primary_active"
        ),
        sa.ForeignKeyConstraint(
            ["legacy_member_id", "church_id"],
            ["members.id", "members.branch_id"],
            name="fk_membership_legacy_church",
        ),
    )
    op.create_index(
        "uq_church_membership_primary",
        "church_memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_index("ix_church_memberships_user_id", "church_memberships", ["user_id"])
    op.create_index(
        "ix_church_memberships_church_status", "church_memberships", ["church_id", "status"]
    )
    op.create_table(
        "membership_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("church_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("matched_member_id", sa.Uuid(), sa.ForeignKey("members.id")),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','more_info_required','cancelled')",
            name="status",
        ),
        sa.ForeignKeyConstraint(
            ["matched_member_id", "church_id"],
            ["members.id", "members.branch_id"],
            name="fk_request_matched_church",
        ),
    )
    op.create_index(
        "uq_membership_request_open",
        "membership_requests",
        ["user_id", "church_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending','more_info_required')"),
    )
    op.create_index(
        "ix_membership_requests_church_status", "membership_requests", ["church_id", "status"]
    )
    op.create_table(
        "church_follows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("church_id", sa.Uuid(), sa.ForeignKey("branches.id"), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("user_id", "church_id", name="uq_church_follow"),
    )
    op.create_index("ix_church_follows_church_id", "church_follows", ["church_id"])
    op.execute("""
        INSERT INTO profiles (user_id, first_name, last_name, phone, created_at, updated_at)
        SELECT id, left(split_part(name, ' ', 1), 100),
               left(CASE WHEN strpos(name, ' ') > 0 THEN substr(name, strpos(name, ' ')+1)
                         ELSE '' END, 100), phone, created_at, updated_at FROM users
    """)
    op.execute("""
        INSERT INTO church_memberships
          (id, church_id, user_id, legacy_member_id, status, role, is_primary,
           joined_at, created_at, updated_at)
        SELECT m.id, m.branch_id, u.id, m.id,
          CASE WHEN m.membership_status IN ('pending','active','inactive','former','suspended')
               THEN m.membership_status
               WHEN m.membership_status IN ('transferred','deceased','discontinued') THEN 'former'
               ELSE 'inactive' END,
          'member', u.id IS NOT NULL AND m.membership_status = 'active',
          m.joined_at, m.created_at, m.updated_at
        FROM members m LEFT JOIN users u ON u.member_id = m.id
          AND (u.branch_id IS NULL OR u.branch_id = m.branch_id)
    """)
    install_policies()


def install_policies():
    # Context is set transaction-locally ONLY by the trusted FastAPI server.
    actor = "nullif(current_setting('vinyrd.user_id', true), '')::uuid"
    staff = f"""EXISTS (SELECT 1 FROM users u JOIN user_roles ur ON ur.user_id=u.id
        JOIN roles r ON r.id=ur.role_id WHERE u.id={actor} AND u.status='active'
        AND u.branch_id=church_id AND r.name IN ('Administrator','Receptionist','Pastor / Leader'))"""
    admin = staff.replace("('Administrator','Receptionist','Pastor / Leader')", "('Administrator')")
    own = f"user_id={actor}"
    for table in ("profiles", "church_memberships", "membership_requests", "church_follows"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
    for table in ("profiles", "church_follows"):
        op.execute(f"CREATE POLICY identity_owner ON {table} USING ({own}) WITH CHECK ({own})")
    # Staff provisioning can create a profile, but cannot read or edit it.
    op.execute(f"""CREATE POLICY profile_provision ON profiles FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM users target JOIN users actor ON actor.branch_id=target.branch_id
          JOIN user_roles ur ON ur.user_id=actor.id JOIN roles r ON r.id=ur.role_id
          WHERE target.id=profiles.user_id AND actor.id={actor} AND actor.status='active'
          AND r.name IN ('Administrator','Receptionist')))
    """)
    op.execute(
        f"CREATE POLICY membership_read ON church_memberships FOR SELECT USING ({own} OR {staff})"
    )
    op.execute(
        f"CREATE POLICY membership_insert ON church_memberships FOR INSERT WITH CHECK ({staff})"
    )
    op.execute(f"""CREATE POLICY membership_update ON church_memberships FOR UPDATE
        USING ({own} OR {staff}) WITH CHECK ({own} OR {staff})""")
    op.execute(
        f"CREATE POLICY request_read ON membership_requests FOR SELECT USING ({own} OR {admin})"
    )
    op.execute(f"""CREATE POLICY request_insert ON membership_requests FOR INSERT WITH CHECK (
        {own} AND status='pending' AND reviewed_by IS NULL AND reviewed_at IS NULL
        AND matched_member_id IS NULL AND rejection_reason IS NULL)""")
    op.execute(f"""CREATE POLICY request_update ON membership_requests FOR UPDATE
        USING ({own} OR {admin}) WITH CHECK ({own} OR {admin})""")
    # RLS handles rows; this invoker trigger protects columns and state transitions
    # when an owner updates their primary flag or cancels a request.
    op.execute(f"""
        CREATE FUNCTION vinyrd_guard_identity_update() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public AS $$
        BEGIN
          IF {actor} IS NULL AND EXISTS (SELECT 1 FROM pg_tables
              WHERE schemaname='public' AND tablename=TG_TABLE_NAME AND tableowner=current_user) THEN
            RETURN NEW; -- Trusted offline migrations/seed tools, never an HTTP identity.
          END IF;
          IF EXISTS (SELECT 1 FROM public.users u JOIN public.user_roles ur ON ur.user_id=u.id
              JOIN public.roles r ON r.id=ur.role_id WHERE u.id={actor}
              AND u.status='active' AND u.branch_id=OLD.church_id
              AND (r.name='Administrator' OR (TG_TABLE_NAME='church_memberships'
                   AND r.name IN ('Receptionist','Pastor / Leader')))) THEN
            RETURN NEW;
          END IF;
          IF OLD.user_id IS DISTINCT FROM {actor} THEN
            RAISE EXCEPTION 'Identity owner required' USING ERRCODE='42501';
          END IF;
          IF TG_TABLE_NAME='church_memberships' THEN
            IF (to_jsonb(NEW)-'is_primary'-'updated_at') IS DISTINCT FROM
               (to_jsonb(OLD)-'is_primary'-'updated_at') THEN
              RAISE EXCEPTION 'Only the home flag may be changed' USING ERRCODE='42501';
            END IF;
          ELSE
            IF OLD.status NOT IN ('pending','more_info_required') OR NEW.status <> 'cancelled'
               OR (to_jsonb(NEW)-'status'-'updated_at') IS DISTINCT FROM
                  (to_jsonb(OLD)-'status'-'updated_at') THEN
              RAISE EXCEPTION 'Only cancellation is allowed' USING ERRCODE='42501';
            END IF;
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("REVOKE ALL ON FUNCTION vinyrd_guard_identity_update() FROM PUBLIC")
    for table in ("church_memberships", "membership_requests"):
        op.execute(f"""CREATE TRIGGER guard_identity_update BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION vinyrd_guard_identity_update()""")


def downgrade():
    raise RuntimeError(
        "Identity migration is additive. Restore application code without dropping identity data."
    )

"""Explicit public church profiles and consent-scoped applicant snapshots."""

import sqlalchemy as sa

from alembic import op

revision = "20260925_0016"
down_revision = "20260925_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "membership_requests",
        sa.Column("applicant_snapshot", sa.JSON(), nullable=False, server_default="{}"),
    )
    # No retrospective sharing of private contact/profile information.
    op.execute("""UPDATE membership_requests r SET applicant_snapshot = json_build_object('name', u.name)
               FROM users u WHERE r.user_id=u.id""")
    op.create_table(
        "church_public_profiles",
        sa.Column("church_id", sa.Uuid(), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("region", sa.String(100)),
        sa.Column("city", sa.String(100)),
        sa.Column("denomination", sa.String(120)),
        sa.Column("location", sa.String(240)),
        sa.Column("logo_url", sa.String(2048)),
        sa.Column("about", sa.Text()),
        sa.Column("service_times", sa.Text()),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("contact_phone", sa.String(40)),
        sa.Column("website", sa.String(2048)),
        sa.Column("public_events", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("public_announcements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("public_ministries", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(country) = 2", name="country_code"),
    )
    op.create_index(
        "ix_church_public_geography", "church_public_profiles", ["country", "region", "city"]
    )
    op.execute("ALTER TABLE church_public_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON church_public_profiles FROM PUBLIC")
    admin = """EXISTS (SELECT 1 FROM users u JOIN user_roles ur ON ur.user_id=u.id
        JOIN roles r ON r.id=ur.role_id
        WHERE u.id=nullif(current_setting('vinyrd.user_id',true),'')::uuid
        AND u.status='active' AND u.branch_id=church_id AND r.name='Administrator')"""
    op.execute(
        f"CREATE POLICY published_profile ON church_public_profiles FOR SELECT USING (is_published OR {admin})"
    )
    op.execute(
        f"CREATE POLICY publish_profile ON church_public_profiles FOR INSERT WITH CHECK ({admin})"
    )
    op.execute(
        f"CREATE POLICY edit_profile ON church_public_profiles FOR UPDATE USING ({admin}) WITH CHECK ({admin})"
    )
    op.execute("""CREATE FUNCTION vinyrd_no_self_review() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
        BEGIN
          IF OLD.user_id=nullif(current_setting('vinyrd.user_id',true),'')::uuid
             AND NEW.status IN ('approved','rejected','more_info_required') THEN
            RAISE EXCEPTION 'Another administrator must review this request' USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute("REVOKE ALL ON FUNCTION vinyrd_no_self_review() FROM PUBLIC")
    op.execute("""CREATE TRIGGER no_self_review BEFORE UPDATE ON membership_requests
        FOR EACH ROW EXECUTE FUNCTION vinyrd_no_self_review()""")


def downgrade():
    raise RuntimeError("Keep additive network data when rolling back application code.")

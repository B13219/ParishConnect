"""Explicit organization authority, separate from office and local staff roles."""

import sqlalchemy as sa

from alembic import op

revision = "20260928_0020"
down_revision = "20260927_0019"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("members", "attendance_records", "contributions"):
        op.create_index(f"ix_{table}_branch_id", table, ["branch_id"])
    op.create_table(
        "organization_access_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "organization_unit_id",
            sa.Uuid(),
            sa.ForeignKey("organization_units.id"),
            nullable=False,
        ),
        sa.Column("permission_role", sa.String(80), nullable=False),
        sa.Column("scope_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("granted_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("scope_mode IN ('unit_only','descendants')", name="scope_mode"),
        sa.CheckConstraint("status IN ('active','inactive','revoked')", name="status"),
        sa.CheckConstraint(
            "permission_role IN ('administrator','pastor_leader','accountant','receptionist','usher')",
            name="permission_role",
        ),
    )
    op.create_index("ix_org_grant_user_status", "organization_access_grants", ["user_id", "status"])
    op.create_index(
        "ix_org_grant_unit_status", "organization_access_grants", ["organization_unit_id", "status"]
    )
    op.create_index(
        "uq_org_grant_equivalent",
        "organization_access_grants",
        ["user_id", "organization_unit_id", "permission_role", "scope_mode"],
        unique=True,
    )
    # Definer helpers read immutable topology without policy recursion. Fixed search path,
    # no dynamic SQL, no caller-supplied actor. Only booleans/authorized IDs are exposed.
    op.execute("""CREATE FUNCTION vinyrd_org_covers(root uuid, target uuid, mode text)
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      WITH RECURSIVE chain AS (
        SELECT id,parent_id,denomination,status,ARRAY[id] path,false cycle
          FROM public.organization_units WHERE id=target
        UNION ALL
        SELECT p.id,p.parent_id,p.denomination,p.status,c.path||p.id,p.id=ANY(c.path)
          FROM public.organization_units p JOIN chain c ON p.id=c.parent_id WHERE NOT c.cycle
      ) SELECT COALESCE(
        EXISTS(SELECT 1 FROM chain WHERE id=root)
        AND (mode='descendants' OR (mode='unit_only' AND root=target))
        AND EXISTS(SELECT 1 FROM chain WHERE parent_id IS NULL)
        AND NOT EXISTS(SELECT 1 FROM chain WHERE cycle OR status<>'active')
        AND (SELECT count(DISTINCT denomination) FROM chain)=1,false)
    $$""")
    op.execute("REVOKE ALL ON FUNCTION vinyrd_org_covers(uuid,uuid,text) FROM PUBLIC")
    op.execute("""CREATE FUNCTION vinyrd_org_has(target uuid, permitted text[])
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT EXISTS(SELECT 1 FROM public.organization_access_grants g JOIN public.users u ON u.id=g.user_id
        WHERE u.id=nullif(current_setting('vinyrd.user_id',true),'')::uuid AND u.status='active'
        AND g.status='active' AND g.permission_role=ANY(permitted)
        AND public.vinyrd_org_covers(g.organization_unit_id,target,g.scope_mode))
    $$""")
    op.execute("""CREATE FUNCTION vinyrd_org_manage(target uuid, mode text)
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT EXISTS(SELECT 1 FROM public.organization_access_grants g JOIN public.users u ON u.id=g.user_id
        WHERE u.id=nullif(current_setting('vinyrd.user_id',true),'')::uuid AND u.status='active'
        AND g.status='active' AND g.permission_role='administrator'
        AND (mode='unit_only' OR g.scope_mode='descendants')
        AND public.vinyrd_org_covers(g.organization_unit_id,target,g.scope_mode))
      OR (mode='unit_only' AND EXISTS(SELECT 1 FROM public.users u
        JOIN public.user_roles ur ON ur.user_id=u.id JOIN public.roles r ON r.id=ur.role_id
        JOIN public.branches b ON b.id=u.branch_id
        WHERE u.id=nullif(current_setting('vinyrd.user_id',true),'')::uuid AND u.status='active'
        AND r.name='Administrator' AND b.organization_unit_id=target))
    $$""")
    op.execute("""CREATE FUNCTION vinyrd_org_scope() RETURNS TABLE(grant_id uuid,unit_id uuid)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT g.id,n.id FROM public.organization_access_grants g
        JOIN public.users u ON u.id=g.user_id
        JOIN public.organization_units n ON public.vinyrd_org_covers(g.organization_unit_id,n.id,g.scope_mode)
        WHERE u.id=nullif(current_setting('vinyrd.user_id',true),'')::uuid
        AND u.status='active' AND g.status='active'
    $$""")
    op.execute("ALTER TABLE organization_access_grants ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON organization_access_grants FROM PUBLIC")
    actor = "nullif(current_setting('vinyrd.user_id',true),'')::uuid"
    manage = "vinyrd_org_manage(organization_unit_id,scope_mode)"
    op.execute(
        f"CREATE POLICY grant_read ON organization_access_grants FOR SELECT USING (user_id={actor} OR {manage})"
    )
    op.execute(
        f"CREATE POLICY grant_create ON organization_access_grants FOR INSERT WITH CHECK ({manage} AND user_id<>{actor} AND granted_by={actor})"
    )
    op.execute(
        f"CREATE POLICY grant_edit ON organization_access_grants FOR UPDATE USING ({manage} AND user_id<>{actor}) WITH CHECK ({manage} AND user_id<>{actor})"
    )
    op.execute("""CREATE FUNCTION vinyrd_guard_grant() RETURNS trigger LANGUAGE plpgsql
      SECURITY INVOKER SET search_path=pg_catalog,public AS $$ BEGIN
      IF NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.organization_unit_id IS DISTINCT FROM OLD.organization_unit_id
        OR NEW.granted_by IS DISTINCT FROM OLD.granted_by THEN
        RAISE EXCEPTION 'Grant identity is immutable' USING ERRCODE='42501'; END IF;
      RETURN NEW; END $$""")
    op.execute(
        "CREATE TRIGGER guard_org_grant BEFORE UPDATE ON organization_access_grants FOR EACH ROW EXECUTE FUNCTION vinyrd_guard_grant()"
    )
    op.execute("""CREATE POLICY organization_scope_read ON organization_units FOR SELECT
      USING (vinyrd_org_has(id,ARRAY['administrator','pastor_leader','accountant','receptionist','usher']))""")
    op.execute("""CREATE POLICY organization_office_scope_read ON organization_office_assignments FOR SELECT
      USING (vinyrd_org_manage(organization_unit_id,'unit_only'))""")

    op.execute("""CREATE FUNCTION vinyrd_org_branch(target uuid, permitted text[])
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT target=nullif(current_setting('vinyrd.branch_id',true),'')::uuid AND EXISTS(
        SELECT 1 FROM public.branches b WHERE b.id=target
        AND public.vinyrd_org_has(b.organization_unit_id,permitted))
    $$""")
    op.execute("""CREATE FUNCTION vinyrd_org_account_protected(target uuid)
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT EXISTS(SELECT 1 FROM public.organization_access_grants WHERE user_id=target)
    $$""")
    op.execute("""CREATE POLICY organization_configuration_read ON church_organization_configurations
      FOR SELECT USING (vinyrd_org_branch(branch_id,ARRAY['administrator']))""")
    staff = "vinyrd_org_branch(church_id,ARRAY['administrator','pastor_leader','receptionist'])"
    admin = "vinyrd_org_branch(church_id,ARRAY['administrator'])"
    for table, check in (
        ("church_memberships", staff),
        ("membership_requests", admin),
        ("church_public_profiles", admin),
    ):
        op.execute(f"CREATE POLICY organization_read ON {table} FOR SELECT USING ({check})")
        if table != "membership_requests":
            op.execute(
                f"CREATE POLICY organization_insert ON {table} FOR INSERT WITH CHECK ({check})"
            )
        op.execute(
            f"CREATE POLICY organization_update ON {table} FOR UPDATE USING ({check}) WITH CHECK ({check})"
        )
    op.execute("""CREATE POLICY organization_profile_provision ON profiles FOR INSERT WITH CHECK (
      EXISTS(SELECT 1 FROM users target WHERE target.id=profiles.user_id
      AND vinyrd_org_branch(target.branch_id,ARRAY['administrator','receptionist'])))""")
    op.execute(f"""
        CREATE OR REPLACE FUNCTION vinyrd_guard_identity_update() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public AS $$
        BEGIN
          IF {actor} IS NULL AND EXISTS (SELECT 1 FROM pg_tables
              WHERE schemaname='public' AND tablename=TG_TABLE_NAME AND tableowner=current_user) THEN
            RETURN NEW; -- Trusted offline migrations/seed tools, never an HTTP identity.
          END IF;
          IF public.vinyrd_org_branch(OLD.church_id, CASE WHEN TG_TABLE_NAME='church_memberships'
              THEN ARRAY['administrator','receptionist','pastor_leader'] ELSE ARRAY['administrator'] END)
              OR EXISTS (SELECT 1 FROM public.users u JOIN public.user_roles ur ON ur.user_id=u.id
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

    office = """vinyrd_org_has(organization_unit_id,ARRAY['administrator'])
      AND EXISTS(SELECT 1 FROM organization_units n WHERE n.id=organization_unit_id AND n.owner_branch_id=branch_id)
      AND EXISTS(SELECT 1 FROM users u WHERE u.id=user_id AND u.status='active')"""
    op.execute(
        f"CREATE POLICY organization_office_insert ON organization_office_assignments FOR INSERT WITH CHECK ({office})"
    )
    op.execute(
        f"CREATE POLICY organization_office_update ON organization_office_assignments FOR UPDATE USING (vinyrd_org_manage(organization_unit_id,'unit_only')) WITH CHECK ({office})"
    )


def downgrade():
    raise RuntimeError(
        "Retain additive access grants on application rollback; revoke grants explicitly."
    )

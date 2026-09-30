"""Allow approved local leaf label publication; preserve topology and shared units."""

from alembic import op

revision = "20260930_0021"
down_revision = "20260928_0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_church_organization_configurations_local_unit_id",
        "church_organization_configurations",
        ["local_unit_id"],
    )
    # Boolean only, actor bound, fixed search path. Definer visibility is necessary
    # to detect private children/references hidden from the local administrator.
    op.execute("""CREATE FUNCTION vinyrd_org_labels_local(target uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT EXISTS(SELECT 1 FROM public.organization_units n
        JOIN public.branches b ON b.id=n.owner_branch_id AND b.organization_unit_id=n.id
        JOIN public.users u ON u.branch_id=b.id
        JOIN public.user_roles ur ON ur.user_id=u.id JOIN public.roles r ON r.id=ur.role_id
        WHERE n.id=target AND n.status='active' AND u.status='active'
        AND u.id=nullif(current_setting('vinyrd.user_id',true),'')::uuid
        AND r.name='Administrator'
        AND NOT EXISTS(SELECT 1 FROM public.organization_units child WHERE child.parent_id=n.id)
        AND NOT EXISTS(SELECT 1 FROM public.branches other
          WHERE other.organization_unit_id=n.id AND other.id<>b.id)
        AND NOT EXISTS(SELECT 1 FROM public.church_organization_configurations c
          WHERE c.local_unit_id=n.id AND c.branch_id<>b.id))
    $$""")
    op.execute("""CREATE POLICY local_leaf_labels ON organization_units FOR UPDATE
      USING (vinyrd_org_labels_local(id)) WITH CHECK (vinyrd_org_labels_local(id))""")
    op.execute("""CREATE FUNCTION vinyrd_guard_unit_labels() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$ BEGIN
      IF (to_jsonb(NEW)-'labels_snapshot'-'updated_at') IS DISTINCT FROM
         (to_jsonb(OLD)-'labels_snapshot'-'updated_at') THEN
        RAISE EXCEPTION 'Only approved local labels may change' USING ERRCODE='42501';
      END IF;
      RETURN NEW; END $$""")
    op.execute("""CREATE TRIGGER guard_org_unit_labels BEFORE UPDATE ON organization_units
      FOR EACH ROW EXECUTE FUNCTION vinyrd_guard_unit_labels()""")
    op.create_index(
        "ix_audit_governance_history", "audit_logs", ["branch_id", "action", "created_at"]
    )


def downgrade():
    op.drop_index(
        "ix_church_organization_configurations_local_unit_id",
        table_name="church_organization_configurations",
    )
    op.drop_index("ix_audit_governance_history", table_name="audit_logs")
    op.execute("DROP TRIGGER guard_org_unit_labels ON organization_units")
    op.execute("DROP FUNCTION vinyrd_guard_unit_labels()")
    op.execute("DROP POLICY local_leaf_labels ON organization_units")
    op.execute("DROP FUNCTION vinyrd_org_labels_local(uuid)")

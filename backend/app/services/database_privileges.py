"""Explicit PostgreSQL operational privileges. Does not create database roles."""

from sqlalchemy import inspect, text

from app.db.base import Base
from app.models import *

LIMITED = {
    "roles": "SELECT",
    "users": "SELECT, INSERT, UPDATE",
    "user_roles": "SELECT, INSERT, DELETE",
    "audit_logs": "SELECT, INSERT",
    "branches": "SELECT, UPDATE",
    "organization_units": "SELECT, INSERT",
    "organization_access_grants": "SELECT, INSERT, UPDATE",
    "church_organization_configurations": "SELECT, INSERT, UPDATE",
    "organization_office_assignments": "SELECT, INSERT, UPDATE",
    "profiles": "SELECT, INSERT, UPDATE",
    "church_memberships": "SELECT, INSERT, UPDATE",
    "membership_requests": "SELECT, INSERT, UPDATE",
    "church_public_profiles": "SELECT, INSERT, UPDATE",
    "church_follows": "SELECT, INSERT, DELETE",
}


def runtime_permissions():
    return {
        name: LIMITED.get(name, "SELECT, INSERT, UPDATE, DELETE") for name in Base.metadata.tables
    }


def provision(connection, runtime_role, backup_role=None):
    """Run as schema owner against the intended database only; role creation is a DBA task."""
    quote = connection.dialect.identifier_preparer.quote
    existing = set(inspect(connection).get_table_names())
    if not set(Base.metadata.tables) <= existing:
        raise ValueError(
            "Migrate the complete application schema before provisioning runtime access."
        )
    for role in filter(None, [runtime_role, backup_role]):
        if not connection.scalar(
            text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
        ):
            raise ValueError(
                "Create the named least-privilege login with the database operator first."
            )
    # Reapply this after --no-privileges restore; never rely on restored ACL defaults.
    connection.execute(
        text("REVOKE ALL ON FUNCTION public.vinyrd_org_covers(uuid,uuid,text) FROM PUBLIC")
    )
    connection.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
    database = connection.scalar(text("SELECT current_database()"))
    role = quote(runtime_role)
    connection.execute(text(f"GRANT CONNECT ON DATABASE {quote(database)} TO {role}"))
    connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {role}"))
    connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    connection.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}"))
    connection.execute(text(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}"))
    for table, permissions in runtime_permissions().items():
        connection.execute(text(f"GRANT {permissions} ON TABLE public.{quote(table)} TO {role}"))
    connection.execute(text(f"GRANT SELECT ON TABLE public.alembic_version TO {role}"))
    if backup_role:
        flags = connection.execute(
            text(
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=:role"
            ),
            {"role": backup_role},
        ).one()
        if flags != (False, False, False, True):
            raise ValueError(
                "Dedicated backup login requires BYPASSRLS but no superuser, CREATEDB or CREATEROLE."
            )
        backup = quote(backup_role)
        connection.execute(text(f"GRANT CONNECT ON DATABASE {quote(database)} TO {backup}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {backup}"))
        connection.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {backup}"))
        connection.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {backup}"))


def runtime_issues(connection):
    if connection.dialect.name != "postgresql":
        return ["Runtime validation requires PostgreSQL."]
    issues = []
    flags = connection.execute(
        text(
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolreplication FROM pg_roles WHERE rolname=current_user"
        )
    ).one()
    if any(flags):
        issues.append(
            "Runtime must not have superuser, CREATEDB, CREATEROLE, BYPASSRLS or replication privileges."
        )
    if connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname<>current_user AND pg_has_role(current_user,oid,'MEMBER'))"
        )
    ):
        issues.append("Runtime must not inherit or SET ROLE to other database roles.")
    if connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user))"
        )
    ):
        issues.append("Runtime must not own a database.")
    if connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM pg_class WHERE relnamespace='public'::regnamespace AND relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))"
        )
    ):
        issues.append("Runtime must not own application schema objects.")
    if connection.scalar(
        text(
            "SELECT has_database_privilege(current_database(),'CREATE') OR has_schema_privilege('public','CREATE')"
        )
    ):
        issues.append("Runtime must not create schemas or persistent application objects.")
    if connection.scalar(
        text("SELECT has_function_privilege('public.vinyrd_org_covers(uuid,uuid,text)','EXECUTE')")
    ):
        issues.append("Internal unrestricted hierarchy helper must not be executable by runtime.")
    if connection.scalar(text("SHOW timezone")) != "UTC":
        issues.append("Runtime session timezone must be UTC.")
    for table, privileges in runtime_permissions().items():
        for permission in privileges.split(", "):
            if not connection.scalar(
                text("SELECT has_table_privilege(:table,:permission)"),
                {"table": "public." + table, "permission": permission},
            ):
                issues.append(f"Missing runtime {permission} on {table}.")
        if connection.scalar(
            text(
                "SELECT has_table_privilege(:table,'TRUNCATE') OR has_table_privilege(:table,'TRIGGER') OR has_table_privilege(:table,'REFERENCES')"
            ),
            {"table": "public." + table},
        ):
            issues.append(f"Excess schema/destructive privileges on {table}.")
    return issues

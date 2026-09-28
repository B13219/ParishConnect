"""Canonical WHERE/WHAT resolution. Offices are deliberately never consulted."""

from fastapi import HTTPException
from sqlalchemy import select, text

from app.models import Branch, OrganizationAccessGrant, OrganizationUnit, Role, UserRole

PERMISSION_ROLES = frozenset(
    {"administrator", "pastor_leader", "accountant", "receptionist", "usher"}
)


def local_roles(db, user):
    from app.core.security import role_slug

    return {
        role_slug(name)
        for name in db.scalars(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
    } & PERMISSION_ROLES


class OrganizationScope:
    """One batched graph/grant/branch read per resolution; no process-global cache."""

    def __init__(self, db, user):
        self.user = user
        self.units = {u.id: u for u in db.scalars(select(OrganizationUnit))}
        self.children = {}
        for unit in self.units.values():
            self.children.setdefault(unit.parent_id, []).append(unit.id)
        self.branches = list(db.scalars(select(Branch)))
        self.branch_by_id = {b.id: b for b in self.branches}
        self.local_roles = local_roles(db, user) if user.status == "active" else set()
        self.grants = (
            list(
                db.scalars(
                    select(OrganizationAccessGrant).where(
                        OrganizationAccessGrant.user_id == user.id,
                        OrganizationAccessGrant.status == "active",
                    )
                )
            )
            if user.status == "active"
            else []
        )
        self.coverage = {g.id: set() for g in self.grants}
        if db.bind.dialect.name == "postgresql" and self.grants:
            rows = db.execute(text("SELECT grant_id,unit_id FROM vinyrd_org_scope()"))
            for grant_id, unit_id in rows:
                self.coverage[grant_id].add(unit_id)
        else:
            for unit_id in self.units:
                path = self.ancestors(unit_id)
                for grant in self.grants:
                    if grant.organization_unit_id in path and (
                        grant.scope_mode == "descendants" or grant.organization_unit_id == unit_id
                    ):
                        self.coverage[grant.id].add(unit_id)

        self.branch_roles = {b.id: self._roles_for_branch(b.id) for b in self.branches}
        self.accessible_branch_ids = {key for key, roles in self.branch_roles.items() if roles}
        self.linked_branches = {
            b.organization_unit_id: b.id
            for b in self.branches
            if b.organization_unit_id and b.id in self.accessible_branch_ids
        }

    def ancestors(self, unit_id):
        """Fail closed on cycles, missing parents, inactive nodes or mixed trees."""
        path, seen, denomination = [], set(), None
        while unit_id is not None:
            unit = self.units.get(unit_id)
            if unit is None or unit_id in seen or unit.status != "active":
                return []
            if denomination is not None and unit.denomination != denomination:
                return []
            denomination = unit.denomination
            seen.add(unit_id)
            path.append(unit_id)
            unit_id = unit.parent_id
        return path

    def descendants(self, unit_id, permitted=None):
        permitted = self.unit_ids() if permitted is None else permitted
        result, pending = set(), [unit_id]
        while pending:
            node = pending.pop()
            if node in permitted and node not in result:
                result.add(node)
                pending.extend(self.children.get(node, []))
        return result

    def visible_path(self, unit_id):
        path, seen, visible = [], set(), self.unit_ids()
        while unit_id in visible and unit_id not in seen:
            seen.add(unit_id)
            unit = self.units[unit_id]
            path.append(unit)
            unit_id = unit.parent_id
        return list(reversed(path))

    def unit_ids(self, roles=None):
        result = set()
        for grant in self.grants:
            if roles is None or grant.permission_role in roles:
                result.update(self.coverage[grant.id])
        if self.local_roles and (roles is None or self.local_roles & set(roles)):
            result.update(
                b.organization_unit_id
                for b in self.branches
                if b.id == self.user.branch_id and b.organization_unit_id in self.units
            )
        return result

    def _roles_for_branch(self, branch_id):
        branch = self.branch_by_id.get(branch_id)
        result = set(self.local_roles) if branch_id == self.user.branch_id else set()
        if branch:
            result.update(
                g.permission_role
                for g in self.grants
                if branch.organization_unit_id in self.coverage[g.id]
            )
        return result

    def roles_for_branch(self, branch_id):
        return set(self.branch_roles.get(branch_id, set()))

    def branch_ids(self, roles=None):
        if roles is None:
            return set(self.accessible_branch_ids)
        return {key for key, granted in self.branch_roles.items() if granted & set(roles)}

    def can_manage(self, unit_id, mode="unit_only"):
        # Containment is structural, not just today's set of mapped churches.
        # A unit-only administrator cannot delegate future descendants.
        return any(
            g.permission_role == "administrator"
            and unit_id in self.coverage[g.id]
            and (mode == "unit_only" or g.scope_mode == "descendants")
            for g in self.grants
        ) or (
            mode == "unit_only"
            and "administrator" in self.local_roles
            and any(
                b.id == self.user.branch_id and b.organization_unit_id == unit_id
                for b in self.branches
            )
        )


def requested_branch(db, user):
    return db.info.get("requested_staff_branch") or user.branch_id


def enter_branch(db, user, branch_id, allowed_roles, *, path=""):
    scope = OrganizationScope(db, user)
    roles = scope.roles_for_branch(branch_id)
    local = scope.local_roles if user.branch_id == branch_id else set()
    allowed = set(allowed_roles) | {"administrator"}
    authorized = bool(roles & allowed)
    if not (local & allowed):
        # Legacy composite finance routes must not widen new pastoral grants.
        if "/stewardship" in path or "/reports" in path:
            authorized = bool(roles & {"administrator", "accountant"})
        if "/reports" in path and "administrator" not in roles:
            authorized = False  # Composite legacy reports; use capability-filtered summary.
        # Pastoral notes, prayers, private lessons and account credentials stay local.
        if "/staff/" in path or "/backup-manifest" in path:
            authorized = False
    if not authorized or branch_id not in scope.branch_ids():
        raise HTTPException(403, "Permission denied for this church context.")
    db.info["staff_church"] = branch_id
    db.info["effective_staff_roles"] = roles
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('vinyrd.branch_id', :branch, true)"), {"branch": str(branch_id)}
        )
    return roles


def effective_branch(db, user):
    return db.info.get("staff_church") or requested_branch(db, user)


def require_branch_admin(db, user, branch_id):
    if branch_id is None or "administrator" not in OrganizationScope(db, user).roles_for_branch(
        branch_id
    ):
        raise HTTPException(403, "Church administrator permission required.")
    # Identity services must still lock global accounts, so do not install legacy ORM filters.
    db.info["authorized_identity_branch"] = branch_id
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('vinyrd.branch_id', :branch, true)"), {"branch": str(branch_id)}
        )


def account_has_organization_grants(db, user_id):
    # An unrelated local administrator cannot see a higher grant through RLS,
    # but must still be prevented from taking over its holder's credentials.
    if db.bind.dialect.name == "postgresql":
        return db.scalar(text("SELECT vinyrd_org_account_protected(:id)"), {"id": user_id})
    return bool(
        db.scalar(
            select(OrganizationAccessGrant.id)
            .where(OrganizationAccessGrant.user_id == user_id)
            .limit(1)
        )
    )

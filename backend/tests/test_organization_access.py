"""Capability-specific scope matrix, also reused by non-owner PostgreSQL tests."""

from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.core.security import password_hash
from app.models import (
    Branch,
    ChurchMembership,
    Contribution,
    Member,
    OrganizationAccessGrant,
    OrganizationOfficeAssignment,
    OrganizationUnit,
    User,
)

pytest_plugins = ["tests.test_global_identity"]
API = "/api/v1/organization-access"


def seed_scope(db, a, b):
    branches = {"a": db.get(Branch, UUID(str(a))), "b": db.get(Branch, UUID(str(b)))}
    for key in ("c", "d", "e"):
        branches[key] = Branch(name="Church " + key)
        db.add(branches[key])
    db.flush()
    units = {}
    for key, parent, denomination, level in (
        ("national", None, "TAG", "national"),
        ("district", "national", "TAG", "district"),
        ("section", "district", "TAG", "section"),
        ("a", "section", "TAG", "local_church"),
        ("b", "section", "TAG", "local_church"),
        ("section2", "district", "TAG", "section"),
        ("c", "section2", "TAG", "local_church"),
        ("district2", "national", "TAG", "district"),
        ("d", "district2", "TAG", "local_church"),
        ("diocese", None, "Catholic", "diocese"),
        ("e", "diocese", "Catholic", "parish"),
    ):
        unit = OrganizationUnit(
            denomination="Assemblies of God" if denomination == "TAG" else denomination,
            level_key=level,
            canonical_name=key,
            normalized_name=key,
            parent_id=units[parent].id if parent else None,
            owner_branch_id=branches["a"].id,
            match_key=key,
            labels_snapshot={"en": level, "sw": "Jimbo" if level == "district" else level},
        )
        db.add(unit)
        db.flush()
        units[key] = unit
        if key in branches:
            branches[key].organization_unit_id = unit.id
    users = {}
    for key in (
        "national",
        "district",
        "section",
        "unit",
        "pastor",
        "accountant",
        "mixed",
        "office",
        "target",
        "catholic",
    ):
        u = User(name=key, email=key + "@scope.test", password_hash=password_hash("test-password"))
        db.add(u)
        db.flush()
        users[key] = u
    for user, unit, role, mode in (
        ("national", "national", "administrator", "descendants"),
        ("district", "district", "administrator", "descendants"),
        ("section", "section", "administrator", "descendants"),
        ("unit", "section", "administrator", "unit_only"),
        ("pastor", "district", "pastor_leader", "descendants"),
        ("accountant", "district", "accountant", "descendants"),
        ("mixed", "section", "administrator", "descendants"),
        ("mixed", "district", "accountant", "descendants"),
        ("catholic", "diocese", "administrator", "descendants"),
    ):
        db.add(
            OrganizationAccessGrant(
                user_id=users[user].id,
                organization_unit_id=units[unit].id,
                permission_role=role,
                scope_mode=mode,
            )
        )
    db.add(
        OrganizationOfficeAssignment(
            user_id=users["office"].id,
            organization_unit_id=units["district"].id,
            position_key="district_bishop",
            permission_role="administrator",
            branch_id=branches["a"].id,
        )
    )
    for key, branch in branches.items():
        db.add(Member(branch_id=branch.id, first_name="Scope", last_name=key))
        db.add(Contribution(branch_id=branch.id, amount=10, contribution_type="tithe"))
    db.commit()
    return {
        "branches": {k: str(v.id) for k, v in branches.items()},
        "units": {k: str(v.id) for k, v in units.items()},
        "users": {k: str(v.id) for k, v in users.items()},
    }


def login(c, name):
    r = c.post(
        "/api/v1/auth/login", json={"email": name + "@scope.test", "password": "test-password"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def hierarchy(identity):
    c, sessions, old = identity
    with sessions() as db:
        ids = seed_scope(db, old["a"], old["b"])
    ids["legacy"] = old["admin_a"]
    return c, sessions, ids


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("national", {"a", "b", "c", "d"}),
        ("district", {"a", "b", "c"}),
        ("section", {"a", "b"}),
        ("unit", set()),
        ("office", set()),
        ("catholic", {"e"}),
        ("pastor", {"a", "b", "c"}),
        ("accountant", {"a", "b", "c"}),
    ],
)
def test_scope_matrix(hierarchy, actor, expected):
    c, _, ids = hierarchy
    headers = login(c, actor)
    r = c.get(API + "/tree", headers=headers)
    assert r.status_code == 200, r.text
    assert {b["id"] for b in r.json()["branches"]} == {ids["branches"][k] for k in expected}
    for key, branch in ids["branches"].items():
        r = c.post(API + "/context", headers=headers, json={"branch_id": branch})
        assert r.status_code == (200 if key in expected else 403), r.text


@pytest.mark.parametrize(
    "actor,branch,module,expected",
    [
        ("district", "a", "members/", 200),
        ("district", "d", "members/", 403),
        ("section", "c", "members/", 403),
        ("pastor", "a", "members/", 200),
        ("pastor", "a", "stewardship/", 403),
        ("accountant", "a", "members/", 403),
        ("accountant", "a", "stewardship/", 200),
        ("accountant", "a", "staff/prayers", 403),
        ("mixed", "a", "admin/users", 200),
        ("mixed", "c", "admin/users", 403),
        ("mixed", "c", "stewardship/", 200),
        ("catholic", "a", "members/", 403),
        ("office", "a", "members/", 403),
    ],
)
def test_module_boundaries(hierarchy, actor, branch, module, expected):
    c, _, ids = hierarchy
    headers = {**login(c, actor), "X-Vinyrd-Branch-ID": ids["branches"][branch]}
    r = c.get("/api/v1/" + module, headers=headers)
    assert r.status_code == expected, r.text


@pytest.mark.parametrize(
    "actor,unit,mode,expected",
    [
        ("district", "national", "descendants", 403),
        ("section", "section2", "unit_only", 403),
        ("section", "district", "unit_only", 403),
        ("district", "section", "descendants", 201),
        ("unit", "section", "descendants", 403),
        ("unit", "section", "unit_only", 201),
        ("district", "diocese", "unit_only", 403),
        ("accountant", "a", "unit_only", 403),
    ],
)
def test_grant_containment(hierarchy, actor, unit, mode, expected):
    c, _, ids = hierarchy
    r = c.post(
        API + "/grants",
        headers=login(c, actor),
        json={
            "user_id": ids["users"]["target"],
            "organization_unit_id": ids["units"][unit],
            "permission_role": "administrator",
            "scope_mode": mode,
        },
    )
    assert r.status_code == expected, r.text


def test_local_compatibility_self_escalation_and_revocation(hierarchy):
    c, sessions, ids = hierarchy
    local = ids["legacy"]
    assert {b["id"] for b in c.get(API + "/tree", headers=local).json()["branches"]} == {
        ids["branches"]["a"]
    }
    payload = {
        "user_id": ids["users"]["target"],
        "organization_unit_id": ids["units"]["district"],
        "permission_role": "administrator",
        "scope_mode": "descendants",
    }
    assert c.post(API + "/grants", headers=local, json=payload).status_code == 403
    national = login(c, "national")
    assert (
        c.post(
            API + "/grants", headers=national, json={**payload, "user_id": ids["users"]["national"]}
        ).status_code
        == 403
    )
    with sessions() as db:
        before = db.scalar(select(func.count()).select_from(ChurchMembership))
    r = c.post(API + "/grants", headers=national, json=payload)
    assert r.status_code == 201, r.text
    grant = r.json()["id"]
    target = login(c, "target")
    assert len(c.get(API + "/tree", headers=target).json()["branches"]) == 3
    for status in ("inactive", "active", "revoked"):
        r = c.put(
            API + "/grants/" + grant,
            headers=national,
            json={
                "permission_role": "administrator",
                "scope_mode": "descendants",
                "status": status,
            },
        )
        assert r.status_code == 200, r.text
        assert len(c.get(API + "/tree", headers=target).json()["branches"]) == (
            3 if status == "active" else 0
        )
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(ChurchMembership)) == before
    summary = c.get(API + "/summary", headers=login(c, "mixed")).json()
    assert summary["members"]["church_count"] == 2
    assert summary["finance"]["church_count"] == 3
    assert c.get(API + "/summary", headers=login(c, "pastor")).json()["finance"] is None
    assert (
        c.get(API + "/summary", headers=login(c, "accountant")).json()["members"]["count"] is None
    )


def test_malformed_cycle_denies_hierarchy(hierarchy):
    c, sessions, ids = hierarchy
    with sessions() as db:
        db.get(OrganizationUnit, UUID(ids["units"]["national"])).parent_id = UUID(
            ids["units"]["section"]
        )
        db.commit()
    assert c.get(API + "/tree", headers=login(c, "national")).json()["branches"] == []


def test_custom_tree_office_independence_and_query_budget(hierarchy):
    from sqlalchemy import event

    from app.core.tenancy import set_actor
    from app.services.organization_access import OrganizationScope

    c, sessions, ids = hierarchy
    # Same engine supports a custom denomination without text-based authorization.
    with sessions() as db:
        for unit in db.scalars(
            select(OrganizationUnit).where(OrganizationUnit.denomination == "Assemblies of God")
        ):
            unit.denomination = "Custom Network"
        db.commit()
    assert len(c.get(API + "/tree", headers=login(c, "national")).json()["branches"]) == 4
    # One batched query per entity category, rather than one per node.
    statements = []
    engine = sessions.kw["bind"]

    def capture(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with sessions() as db:
            actor = db.get(User, UUID(ids["users"]["national"]))
            set_actor(db, actor)
            scope = OrganizationScope(db, actor)
            assert len(scope.unit_ids()) == 9
        assert len(statements) <= 6
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert c.get(API + "/tree", headers=login(c, "office")).json()["branches"] == []


def test_local_staff_cannot_take_over_grant_holder(hierarchy):
    c, sessions, ids = hierarchy
    with sessions() as db:
        target = db.get(User, UUID(ids["users"]["target"]))
        target.branch_id = UUID(ids["branches"]["a"])
        member = Member(branch_id=target.branch_id, first_name="Granted", last_name="Account")
        db.add(member)
        db.flush()
        target.member_id = member.id
        db.add(
            OrganizationAccessGrant(
                user_id=target.id,
                organization_unit_id=UUID(ids["units"]["national"]),
                permission_role="administrator",
                scope_mode="descendants",
            )
        )
        db.commit()
        member_id = str(member.id)
    assert (
        c.patch(
            "/api/v1/admin/users/" + ids["users"]["target"],
            headers=ids["legacy"],
            json={"password": "changed-password"},
        ).status_code
        == 403
    )
    assert (
        c.post(
            "/api/v1/staff/member-access/" + member_id + "/reset-password", headers=ids["legacy"]
        ).status_code
        == 403
    )
    assert (
        c.patch(
            "/api/v1/staff/member-access/" + member_id,
            headers=ids["legacy"],
            json={"status": "inactive"},
        ).status_code
        == 403
    )


def test_office_edit_never_creates_permission(hierarchy):
    from app.services.denominations import denomination_catalog

    c, sessions, ids = hierarchy
    template = next(t for t in denomination_catalog() if t["value"] == "Assemblies of God")
    position = next(l for l in template["levels"] if l["key"] == "district")["positions"][0]
    payload = {
        "organization_unit_id": ids["units"]["district"],
        "user_id": ids["users"]["target"],
        "position_key": position["key"],
    }
    r = c.put(API + "/offices", headers=login(c, "district"), json=payload)
    assert r.status_code == 200, r.text
    assert c.get(API + "/tree", headers=login(c, "target")).json()["branches"] == []
    r = c.put(
        API + "/offices", headers=login(c, "district"), json={**payload, "status": "inactive"}
    )
    assert r.status_code == 200, r.text
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(OrganizationAccessGrant)
                .where(OrganizationAccessGrant.user_id == UUID(ids["users"]["target"]))
            )
            == 0
        )

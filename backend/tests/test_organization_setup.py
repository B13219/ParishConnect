"""Organization installation is explicit, tenant scoped, and does not grant access."""

from copy import deepcopy
from itertools import pairwise
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.models import (
    AuditLog,
    Branch,
    ChurchMembership,
    ChurchOrganizationConfiguration,
    OrganizationOfficeAssignment,
    OrganizationUnit,
    User,
    UserRole,
)
from app.services.organizations import (
    ancestry,
    is_unit_descendant_of,
    organization_scope_ids,
    user_organization_assignments,
)
from tests.test_church_network import publish
from tests.test_global_identity import approve, register, request

pytest_plugins = ["tests.test_global_identity"]
API = "/api/v1/network/admin/organization"
KEYS = ["national_church", "zone", "district", "section", "local_church"]


def tag_payload(public=False, district="Dar es Salaam", church="TAG Mikocheni"):
    return {
        "denomination": "TAG",
        "template_version": 1,
        "organization_level": "local_church",
        "units": [
            {"level_key": key, "canonical_name": name, "country": "TZ", "is_published": public}
            for key, name in zip(
                KEYS,
                ["Tanzania Assemblies of God", "Eastern", district, "Kinondoni", church],
                strict=True,
            )
        ],
    }


def confirm(client, ids, payload=None, church="a"):
    response = client.post(
        API + "/confirm", headers=ids["admin_" + church], json=payload or tag_payload()
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_is_readonly_and_legacy_branch_works(identity):
    client, sessions, ids = identity
    assert client.get(API + "/setup", headers=ids["admin_a"]).json()["setup_status"] == "draft"
    for _ in range(2):
        response = client.post(
            API + "/preview",
            headers=ids["admin_a"],
            json={"denomination": "TAG", "organization_level": "local_church"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["denomination"] == "Assemblies of God"
        assert data["template_version"] == 1
        assert [level["key"] for level in data["levels"]] == KEYS
        assert data["levels"][2]["labels"]["sw"] == "Jimbo"
    with sessions() as db:
        for model in (
            OrganizationUnit,
            ChurchOrganizationConfiguration,
            OrganizationOfficeAssignment,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert db.get(Branch, UUID(ids["a"])).organization_unit_id is None
    assert client.get("/api/v1/admin/branch", headers=ids["admin_a"]).status_code == 200


def test_confirmation_chain_snapshot_idempotence_and_audit(identity, monkeypatch):
    client, sessions, ids = identity
    payload = tag_payload()
    payload["units"][2]["localized_names"] = {"en": None, "sw": "Jimbo la Dar es Salaam"}
    data = confirm(client, ids, payload)
    assert data["setup_status"] == "configured"
    assert data["template_version"] == 1
    assert [unit["level_key"] for unit in data["organization_path"]] == KEYS
    assert data["organization_path"][2]["canonical_name"] == "Dar es Salaam"
    assert data["organization_path"][2]["localized_names"]["en"] is None
    assert confirm(client, ids, payload) == data
    with sessions() as db:
        units = ancestry(db, UUID(data["local_unit_id"]))
        assert len(units) == 5
        assert units[0].parent_id is None
        assert all(child.parent_id == parent.id for parent, child in pairwise(units))
        assert db.get(Branch, UUID(ids["a"])).organization_unit_id == units[-1].id
        assert [unit.is_managed for unit in units] == [False, False, False, False, True]
        assert is_unit_descendant_of(db, units[-1].id, units[0].id)
        assert not is_unit_descendant_of(db, units[0].id, units[0].id)
        assert not is_unit_descendant_of(db, units[0].id, units[-1].id)
        assert set(organization_scope_ids(db, units[0].id)) == {unit.id for unit in units}
        actions = list(
            db.scalars(select(AuditLog.action).where(AuditLog.action.like("organization.%")))
        )
        assert actions.count("organization.unit_created") == 5
        assert actions.count("organization.setup_confirmed") == 1
        assert actions.count("organization.branch_linked") == 1
    monkeypatch.setattr("app.services.organizations.denomination_catalog", list)
    assert confirm(client, ids, payload) == data  # replay does not reinterpret updated templates
    assert client.get(API + "/setup", headers=ids["admin_a"]).json() == data
    changed = deepcopy(payload)
    changed["units"][-1]["canonical_name"] = "Changed"
    assert client.post(API + "/confirm", headers=ids["admin_a"], json=changed).status_code == 409


@pytest.mark.parametrize("district, expected", [("Dar es Salaam", 6), ("Arusha", 8)])
def test_reuses_exact_public_ancestors_but_not_sections_under_different_parents(
    identity, district, expected
):
    client, sessions, ids = identity
    a = confirm(client, ids, tag_payload(public=True))
    b = confirm(client, ids, tag_payload(public=True, district=district, church="TAG Second"), "b")
    assert a["organization_path"][0]["id"] == b["organization_path"][0]["id"]
    assert (a["organization_path"][3]["id"] == b["organization_path"][3]["id"]) == (
        district == "Dar es Salaam"
    )
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(OrganizationUnit)) == expected


def test_unpublished_other_tenant_units_are_not_reused(identity):
    client, sessions, ids = identity
    a = confirm(client, ids)
    b = confirm(client, ids, church="b")
    assert a["organization_path"][0]["id"] != b["organization_path"][0]["id"]
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(OrganizationUnit)) == 10


def test_catholic_optional_parents_and_custom_denomination(identity):
    client, sessions, ids = identity
    payload = {
        "denomination": "Roman Catholic",
        "template_version": 1,
        "organization_level": "parish",
        "units": [
            {"level_key": "diocese", "canonical_name": "Arusha Diocese"},
            {"level_key": "parish", "canonical_name": "St. Joseph"},
        ],
    }
    data = confirm(client, ids, payload)
    assert [u["level_key"] for u in data["organization_path"]] == ["diocese", "parish"]
    custom = confirm(client, ids, {"denomination": "Independent Fellowship"}, "b")
    assert custom["setup_status"] == "custom_required"
    assert custom["local_unit_id"] is None
    assert custom["hierarchy_snapshot"] == {"levels": [], "path": []}
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(OrganizationUnit)) == 2
        assert db.get(Branch, UUID(ids["b"])).denomination == "Independent Fellowship"


@pytest.mark.parametrize(
    "mutation, code",
    [
        ("localized_key", 422),
        ("missing_parent", 422),
        ("duplicate", 422),
        ("out_of_order", 422),
        ("wrong_version", 409),
        ("no_version", 422),
        ("unknown_level", 422),
    ],
)
def test_invalid_hierarchy_rolls_back(identity, mutation, code):
    client, sessions, ids = identity
    payload = tag_payload()
    if mutation == "localized_key":
        payload["units"][2]["level_key"] = "jimbo"
    elif mutation == "missing_parent":
        payload["units"].pop(2)
    elif mutation == "duplicate":
        payload["units"].insert(1, payload["units"][0])
    elif mutation == "out_of_order":
        payload["units"][1:3] = list(reversed(payload["units"][1:3]))
    elif mutation == "wrong_version":
        payload["template_version"] = 2
    elif mutation == "no_version":
        payload.pop("template_version")
    elif mutation == "unknown_level":
        payload["organization_level"] = "jimbo"
    response = client.post(API + "/confirm", headers=ids["admin_a"], json=payload)
    assert response.status_code == code, response.text
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(OrganizationUnit)) == 0
        assert db.scalar(select(func.count()).select_from(ChurchOrganizationConfiguration)) == 0
        assert db.get(Branch, UUID(ids["a"])).organization_unit_id is None


def test_membership_stays_at_branch_and_public_output_is_allowlisted(identity):
    client, sessions, ids = identity
    config = confirm(client, ids, tag_payload(public=True))
    publish(client, ids["admin_a"], denomination="TAG")
    user, user_id = register(client)
    rid = request(client, user, ids["a"])
    assert approve(client, ids, rid, member=ids["offline"]).status_code == 200
    with sessions() as db:
        memberships = db.scalars(
            select(ChurchMembership).where(ChurchMembership.user_id == UUID(user_id))
        ).all()
        assert len(memberships) == 1 and str(memberships[0].church_id) == ids["a"]
    public = client.get("/api/v1/network/churches/" + ids["a"]).json()
    assert [u["level_key"] for u in public["organization_path"]] == KEYS
    assert all(
        set(u) == {"level_key", "name", "labels", "presentation"}
        for u in public["organization_path"]
    )
    assert (
        client.get("/api/v1/network/churches").json()["items"][0]["organization_path"]
        == public["organization_path"]
    )
    assert client.get(API + "/setup", headers=user).status_code == 403
    assert client.post(API + "/confirm", headers=user, json=tag_payload()).status_code == 403
    assert client.get(API + "/setup", headers=ids["admin_b"]).json()["local_unit_id"] is None
    assert (
        client.post(
            API + "/confirm", headers=ids["admin_b"], json={**tag_payload(), "branch_id": ids["a"]}
        ).status_code
        == 422
    )
    # Private parent suppresses the entire public path, including for an authenticated owner.
    with sessions() as db:
        db.get(OrganizationUnit, UUID(config["organization_path"][0]["id"])).is_published = False
        db.commit()
    assert (
        client.get("/api/v1/network/churches/" + ids["a"], headers=ids["admin_a"]).json()[
            "organization_path"
        ]
        == []
    )


def test_office_and_permission_are_independent_and_do_not_grant_access(identity):
    client, sessions, ids = identity
    config = confirm(client, ids)
    with sessions() as db:
        actor = db.scalar(select(User).where(User.email == "a@test.local"))
        other = db.scalar(select(User).where(User.email == "b@test.local"))
        actor_id, other_id = str(actor.id), str(other.id)
        role_count = db.scalar(select(func.count()).select_from(UserRole))
        legacy_title = actor.position_title
    position = config["hierarchy_snapshot"]["levels"][-1]["positions"][0]["key"]
    payload = {
        "user_id": actor_id,
        "organization_unit_id": config["local_unit_id"],
        "position_key": position,
        "permission_role": "administrator",
    }
    response = client.put(API + "/assignments", headers=ids["admin_a"], json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["position_key"] == position
    assert response.json()["permission_role"] == "administrator"
    assert client.put(API + "/assignments", headers=ids["admin_b"], json=payload).status_code == 403
    assert (
        client.put(
            API + "/assignments", headers=ids["admin_a"], json={**payload, "user_id": other_id}
        ).status_code
        == 404
    )
    assert (
        client.put(
            API + "/assignments",
            headers=ids["admin_a"],
            json={**payload, "organization_unit_id": config["organization_path"][0]["id"]},
        ).status_code
        == 403
    )
    assert (
        client.put(
            API + "/assignments", headers=ids["admin_a"], json={**payload, "position_key": "Askofu"}
        ).status_code
        == 422
    )
    assert (
        client.put(
            API + "/assignments",
            headers=ids["admin_a"],
            json={**payload, "permission_role": "god_mode"},
        ).status_code
        == 422
    )
    assert (
        client.put(
            API + "/assignments", headers=ids["admin_a"], json={**payload, "status": "inactive"}
        ).status_code
        == 200
    )
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(UserRole)) == role_count
        assert db.get(User, UUID(actor_id)).position_title == legacy_title
        assert user_organization_assignments(db, UUID(actor_id)) == []
        assert db.scalar(select(func.count()).select_from(OrganizationOfficeAssignment)) == 1
    assert client.get(API + "/assignments", headers=ids["admin_b"]).json()["items"] == []
    assert (
        client.patch(
            "/api/v1/admin/branch", headers=ids["admin_a"], json={"denomination": "Catholic"}
        ).status_code
        == 409
    )


def test_failure_mid_confirmation_rolls_back_everything(identity, monkeypatch):
    client, sessions, ids = identity

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated transaction failure after unit insert")

    monkeypatch.setattr("app.services.organizations.write_audit_log", fail_audit)
    with pytest.raises(RuntimeError, match="Simulated transaction failure"):
        client.post(API + "/confirm", headers=ids["admin_a"], json=tag_payload())
    with sessions() as db:
        for model in (OrganizationUnit, ChurchOrganizationConfiguration, AuditLog):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert db.get(Branch, UUID(ids["a"])).organization_unit_id is None


def test_recording_administrator_profile_does_not_elevate_an_unprivileged_user(identity):
    client, sessions, ids = identity
    headers, user_id = register(client)
    with sessions() as db:
        db.get(User, UUID(user_id)).branch_id = UUID(ids["a"])
        db.commit()
    config = confirm(client, ids)
    payload = {
        "user_id": user_id,
        "organization_unit_id": config["local_unit_id"],
        "position_key": config["hierarchy_snapshot"]["levels"][-1]["positions"][0]["key"],
        "permission_role": "administrator",
    }
    assert client.put(API + "/assignments", headers=ids["admin_a"], json=payload).status_code == 200
    assert client.get(API + "/setup", headers=headers).status_code == 403
    assert client.put(API + "/assignments", headers=headers, json=payload).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    with sessions() as db:
        assert len(user_organization_assignments(db, UUID(user_id))) == 1
        assert (
            db.scalar(
                select(func.count()).select_from(UserRole).where(UserRole.user_id == UUID(user_id))
            )
            == 0
        )


def test_public_ancestry_does_not_contradict_a_legacy_public_denomination(identity):
    client, _, ids = identity
    publish(client, ids["admin_a"], denomination="Catholic")
    confirm(client, ids, tag_payload(public=True))
    assert client.get("/api/v1/network/churches/" + ids["a"]).json()["organization_path"] == []
    assert client.get("/api/v1/network/churches").json()["items"][0]["organization_path"] == []


def test_localized_names_remain_names_not_organization_keys(identity):
    client, _, ids = identity
    payload = tag_payload()
    payload["units"][2]["canonical_name"] = "Jimbo la Dar es Salaam"
    payload["units"][2]["localized_names"] = {"en": "Dar es Salaam District"}
    result = confirm(client, ids, payload)
    district = result["organization_path"][2]
    assert district["level_key"] == "district"
    assert district["canonical_name"] == "Jimbo la Dar es Salaam"
    assert district["localized_names"]["en"] == "Dar es Salaam District"

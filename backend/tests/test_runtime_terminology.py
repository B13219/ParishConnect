"""Runtime presentation policy and security invariance, without new identifiers."""

from copy import deepcopy
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import (
    Branch,
    OrganizationUnit,
    Profile,
    User,
)
from app.services.denominations import DENOMINATION_CATALOG, denomination_catalog
from app.services.terminology import Terminology, effective_locale, resolve_organization_name
from tests.test_church_network import publish
from tests.test_organization_setup import confirm, tag_payload

pytest_plugins = ["tests.test_global_identity", "tests.test_organization_access"]


def installed(name):
    template = next(t for t in denomination_catalog() if t["value"] == name)
    return {
        "denomination": name,
        "setup_status": "configured",
        "template_version": 1,
        "hierarchy_snapshot": {"levels": template["levels"]},
        "terminology_snapshot": {},
    }


@pytest.mark.parametrize("item", denomination_catalog(), ids=lambda t: t["value"])
def test_every_denomination_uses_one_resolver(item):
    resolver = Terminology(installed(item["value"]))
    for level in item["levels"]:
        for locale in ("en", "sw"):
            assert resolver.level(level["key"])[locale]["label"] == level["labels"].get(
                locale, level["label"]
            )
        for position in level["positions"]:
            assert resolver.position(position["key"], "sw") == position["labels"].get(
                "sw", position["title"]
            )


def test_snapshot_and_bilingual_no_catalogue_drift(monkeypatch):
    config = installed("Assemblies of God")
    resolver = Terminology(config)
    assert resolver.level("district")["en"]["bilingual_label"] == "District / Jimbo"
    assert resolver.level("district")["sw"]["bilingual_label"] == "Jimbo / District"
    assert resolver.position("district_bishop", "sw") == "Askofu wa Jimbo"
    template = next(t for t in DENOMINATION_CATALOG if t["value"] == config["denomination"])
    changed = deepcopy(template["levels"])
    changed[2]["labels"] = {"en": "Future District"}
    monkeypatch.setitem(template, "levels", changed)
    monkeypatch.setitem(template, "template_version", 2)
    assert Terminology(config).level("district")["en"]["label"] == "District"
    assert Terminology(denomination="TAG").level("district")["en"]["label"] == "Future District"
    config["terminology_snapshot"] = {
        "district": {"en": "Approved District", "sw": "Approved Jimbo"}
    }
    assert Terminology(config).level("district")["sw"]["label"] == "Approved Jimbo"


def test_proper_names_custom_and_locale_fallback():
    unit = {
        "canonical_name": "Jimbo la Dar es Salaam",
        "localized_names": {"sw": "Jimbo la Dar es Salaam"},
    }
    assert resolve_organization_name(unit, "en") == unit["canonical_name"]
    unit["localized_names"]["en"] = "Dar es Salaam District"
    assert resolve_organization_name(unit, "en") == "Dar es Salaam District"
    custom = Terminology(
        {
            "denomination": "Custom",
            "setup_status": "custom_required",
            "terminology_snapshot": {"network": {"en": "Our Fellowship"}},
        }
    )
    assert custom.level("network")["sw"]["label"] == "Our Fellowship"
    assert custom.level(None)["sw"]["label"] == "Local Church"
    assert (
        custom.position("old", "sw", position_title="Official legacy title")
        == "Official legacy title"
    )
    assert effective_locale(None, "sw") == "sw"
    assert effective_locale("en", "sw") == "en"
    assert effective_locale("unsupported", "unknown") == "en"


def test_public_snapshot_search_and_allowlist(identity, monkeypatch):
    c, sessions, ids = identity
    config = confirm(c, ids, tag_payload(public=True, district="Jimbo la Dar es Salaam"))
    publish(c, ids["admin_a"], name="TAG Mikocheni", denomination="TAG")
    unit_id = UUID(config["organization_path"][2]["id"])
    with sessions() as db:
        unit = db.get(OrganizationUnit, unit_id)
        unit.localized_names = {"en": "Dar es Salaam District", "sw": "Jimbo la Dar es Salaam"}
        db.commit()
    template = next(t for t in DENOMINATION_CATALOG if t["value"] == "Assemblies of God")
    monkeypatch.setitem(template, "levels", [])
    for q in (
        "Jimbo la Dar es Salaam",
        "Dar es Salaam District",
        "Kanda",
        "Zone",
        "Sehemu",
        "Section",
    ):
        data = c.get("/api/v1/network/churches", params={"q": q}).json()
        assert [r["church_id"] for r in data["items"]] == [ids["a"]]
    public = c.get("/api/v1/network/churches/" + ids["a"]).json()
    assert public["organization_path"][2]["presentation"]["sw"]["label"] == "Jimbo"
    assert not {
        "hierarchy_snapshot",
        "configured_by",
        "owner_branch_id",
        "confirmation_fingerprint",
    } & set(public)
    assert all(
        set(u) == {"name", "level_key", "labels", "presentation"}
        for u in public["organization_path"]
    )
    with sessions() as db:
        db.get(OrganizationUnit, unit_id).is_published = False
        db.commit()
    assert c.get("/api/v1/network/churches", params={"q": "Jimbo"}).json()["items"] == []


def test_locale_labels_do_not_change_access_and_branch_context(hierarchy):
    from tests.test_organization_access import login

    c, sessions, ids = hierarchy
    headers = login(c, "district")
    before = c.get("/api/v1/organization-access/tree", headers=headers).json()
    with sessions() as db:
        user = db.get(User, UUID(ids["users"]["district"]))
        db.get(Profile, user.id).ui_language = "sw"
        db.get(OrganizationUnit, UUID(ids["units"]["district"])).labels_snapshot = {
            "en": "District",
            "sw": "Jimbo",
        }
        db.commit()
    after = c.get("/api/v1/organization-access/tree", headers=headers).json()
    assert [(u["id"], u["can_manage"], u["can_manage_descendants"]) for u in before["units"]] == [
        (u["id"], u["can_manage"], u["can_manage_descendants"]) for u in after["units"]
    ]
    assert [b["id"] for b in before["branches"]] == [b["id"] for b in after["branches"]]
    assert all(b["locale"] == "sw" for b in after["branches"])
    assert (
        c.get(
            "/api/v1/members/", headers={**headers, "X-Vinyrd-Branch-ID": ids["branches"]["d"]}
        ).status_code
        == 403
    )


def test_branch_default_locale_and_snapshot_staff_contract(identity):
    c, sessions, ids = identity
    confirm(c, ids)
    with sessions() as db:
        db.get(Branch, UUID(ids["a"])).default_language = "sw"
        admin = db.scalar(select(User).where(User.email == "a@test.local"))
        db.delete(db.get(Profile, admin.id))
        db.commit()
    setup = c.get("/api/v1/network/admin/organization/setup", headers=ids["admin_a"]).json()
    assert setup["locale"] == "sw"
    assert setup["runtime_levels"][2]["presentation"]["sw"]["bilingual_label"] == "Jimbo / District"
    branch = c.get("/api/v1/admin/branch", headers=ids["admin_a"]).json()["branch"]
    assert branch["locale"] == "sw"
    assert branch["runtime_template"]["levels"][2]["presentation"]["sw"]["label"] == "Jimbo"


def test_office_display_changes_never_change_permissions(identity):
    c, sessions, ids = identity
    config = confirm(c, ids)
    actor = c.get("/api/v1/auth/me", headers=ids["admin_a"]).json()["user"]
    position = config["runtime_levels"][-1]["positions"][0]
    response = c.put(
        "/api/v1/network/admin/organization/assignments",
        headers=ids["admin_a"],
        json={
            "user_id": actor["id"],
            "organization_unit_id": config["local_unit_id"],
            "position_key": position["key"],
            "permission_role": "administrator",
        },
    )
    assert response.status_code == 200
    with sessions() as db:
        from app.models import ChurchOrganizationConfiguration

        installed_config = db.get(ChurchOrganizationConfiguration, UUID(ids["a"]))
        snapshot = deepcopy(installed_config.hierarchy_snapshot)
        snapshot["levels"][-1]["positions"][0]["labels"] = {
            "en": "Approved Official Title",
            "sw": "Approved Swahili Title",
        }
        installed_config.hierarchy_snapshot = snapshot
        db.get(Profile, UUID(actor["id"])).ui_language = "sw"
        db.commit()
    row = c.get("/api/v1/admin/users", headers=ids["admin_a"]).json()["users"][0]
    assert row["display_position_title"] == "Approved Swahili Title"
    assert row["roles"] == actor["roles"]
    context = c.get("/api/v1/organization-access/tree", headers=ids["admin_a"]).json()["branches"][
        0
    ]
    assert context["display_position_title"] == "Approved Swahili Title"
    assert (
        c.get(
            "/api/v1/members/", headers={**ids["admin_a"], "X-Vinyrd-Branch-ID": ids["b"]}
        ).status_code
        == 403
    )

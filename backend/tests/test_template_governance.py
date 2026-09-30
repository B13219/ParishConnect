"""Approved local presentation changes never become institutional authority."""

import hashlib
import json
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import Branch, ChurchOrganizationConfiguration, OrganizationUnit
from app.services import template_registry as registry
from app.services.template_governance import snapshot
from tests.test_church_network import publish
from tests.test_global_identity import register
from tests.test_organization_setup import API, confirm, tag_payload

pytest_plugins = ["tests.test_global_identity"]
GOV = API + "/governance"


def release(monkeypatch, denomination="Assemblies of God", mutate=None):
    item = registry.template(denomination, 1)
    item["template_version"] = 2
    if mutate:
        mutate(item)
    else:
        item["levels"][-1]["labels"]["en"] += " v2 fixture"
    monkeypatch.setattr(
        registry, "RELEASES", {**registry.RELEASES, (denomination, 2): json.dumps(item)}
    )
    return item


def review(client, headers, **payload):
    r = client.post(GOV + "/preview", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def approval(data, **payload):
    return {
        **payload,
        "expected_revision": data["revision"],
        "preview_token": data["preview_token"],
        "request_id": str(uuid4()),
    }


def saved(sessions, branch):
    with sessions() as db:
        return snapshot(db.get(ChurchOrganizationConfiguration, UUID(branch)))


@pytest.mark.parametrize("name", list(registry.RELEASES))
def test_registry_versions_are_detached_and_historical(name, monkeypatch):
    denomination, version = name
    old = registry.template(denomination, version)
    copied = registry.template(denomination, version)
    copied["levels"].clear()
    release(monkeypatch, denomination)
    assert registry.template(denomination, version) == old
    assert registry.versions(denomination) == [1, 2]


@pytest.mark.parametrize(
    "name", ["Assemblies of God", "Catholic", "Lutheran", "Seventh-day Adventist"]
)
def test_detection_preview_approval_history_and_member_presentation(identity, monkeypatch, name):
    c, sessions, ids = identity
    template = registry.template(name, 1)
    levels = template["levels"]
    config = confirm(
        c,
        ids,
        {
            "denomination": name,
            "template_version": 1,
            "organization_level": levels[-1]["key"],
            "units": [
                {
                    "level_key": l["key"],
                    "canonical_name": "Institution " + l["key"],
                    "is_published": True,
                }
                for l in levels
            ],
        },
    )
    before = saved(sessions, ids["a"])
    assert publish(c, ids["admin_a"], denomination=name).status_code == 200
    public_before = c.get("/api/v1/network/churches/" + ids["a"]).json()
    release(monkeypatch, name)
    state = c.get(GOV, headers=ids["admin_a"]).json()
    assert state["upgrade_available"] and state["compatibility_status"] == "compatible"
    data = review(c, ids["admin_a"], target_version=2)
    assert saved(sessions, ids["a"]) == before
    assert c.get("/api/v1/network/churches/" + ids["a"]).json() == public_before
    assert data["levels"][-1]["status"] == "renamed"
    payload = approval(data, target_version=2)
    result = c.post(GOV + "/approve", headers=ids["admin_a"], json=payload)
    assert result.status_code == 200, result.text
    assert c.post(GOV + "/approve", headers=ids["admin_a"], json=payload).json()["idempotent"]
    stale = {**payload, "request_id": str(uuid4())}
    assert c.post(GOV + "/approve", headers=ids["admin_a"], json=stale).status_code == 409
    history = c.get(GOV + "/history", headers=ids["admin_a"]).json()["items"]
    assert len(history) == 1 and history[0]["before"] == before
    assert history[0]["after"]["template_version"] == 2
    public_after = c.get("/api/v1/network/churches/" + ids["a"]).json()
    assert public_after["organization_path"][-1]["presentation"]["en"]["label"].endswith(
        "v2 fixture"
    )
    assert (
        not {"proposed_snapshot", "governance", "overrides", "configured_by"} & public_after.keys()
    )
    with sessions() as db:
        unit = db.get(OrganizationUnit, UUID(config["local_unit_id"]))
        assert unit.labels_snapshot["en"].endswith("v2 fixture")
        assert db.get(Branch, UUID(ids["a"])).organization_unit_id == unit.id
    assert c.get(GOV + "/history", headers=ids["admin_b"]).json()["items"] == []


def test_overrides_precedence_reset_fallback_and_strict_schema(identity):
    c, sessions, ids = identity
    confirm(c, ids)
    patch = [{"level_key": "local_church", "labels": {"sw": "Kanisa lililoidhinishwa"}}]
    data = review(c, ids["admin_a"], overrides=patch)
    assert data["provenance"]["overrides"] == "church_approved"
    assert (
        c.post(
            GOV + "/approve", headers=ids["admin_a"], json=approval(data, overrides=patch)
        ).status_code
        == 200
    )
    config = c.get(API + "/setup", headers=ids["admin_a"]).json()
    assert config["terminology"]["local_church"]["sw"]["label"] == patch[0]["labels"]["sw"]
    assert config["terminology"]["local_church"]["en"]["label"] == "Local Church"
    assert registry.template("TAG", 1)["levels"][-1]["labels"]["sw"] != patch[0]["labels"]["sw"]
    patch[0]["labels"] = {"sw": None}
    data = review(c, ids["admin_a"], overrides=patch)
    assert (
        c.post(
            GOV + "/approve", headers=ids["admin_a"], json=approval(data, overrides=patch)
        ).status_code
        == 200
    )
    assert (
        saved(sessions, ids["a"])["terminology_snapshot"]["local_church"]["sw"]
        == "Kanisa la Mahali Pamoja"
    )
    for payload in [
        {"permission_role": "administrator"},
        {"target_version": 999},
        {"overrides": [{"level_key": "missing", "labels": {"en": "No"}}]},
        {"overrides": [{"level_key": "local_church", "labels": {"en": " "}}]},
        {
            "overrides": [
                {
                    "level_key": "local_church",
                    "labels": {"en": "X"},
                    "provenance": "denomination_official",
                }
            ]
        },
    ]:
        assert c.post(GOV + "/preview", headers=ids["admin_a"], json=payload).status_code == 422


@pytest.mark.parametrize("change", ["shared", "remove_office", "optional", "reorder", "duplicate"])
def test_incompatible_releases_never_partially_apply(identity, monkeypatch, change):
    c, sessions, ids = identity
    confirm(c, ids, tag_payload(public=True))
    confirm(c, ids, tag_payload(public=True, church="Other Church"), church="b")
    before = saved(sessions, ids["a"])

    def mutate(t):
        if change == "shared":
            t["levels"][0]["labels"]["sw"] = "Unapproved national title"
        elif change == "remove_office":
            t["levels"][-1]["positions"].pop()
        elif change == "optional":
            t["levels"][1]["optional"] = not t["levels"][1]["optional"]
        elif change == "reorder":
            t["levels"].reverse()
        else:
            t["levels"][-1]["positions"].append(deepcopy(t["levels"][-1]["positions"][0]))

    release(monkeypatch, mutate=mutate)
    if change == "duplicate":
        assert (
            c.post(GOV + "/preview", headers=ids["admin_a"], json={"target_version": 2}).status_code
            == 422
        )
    else:
        data = review(c, ids["admin_a"], target_version=2)
        assert data["compatibility_status"] == "requires_review"
        assert (
            c.post(
                GOV + "/approve", headers=ids["admin_a"], json=approval(data, target_version=2)
            ).status_code
            == 409
        )
    assert saved(sessions, ids["a"]) == before
    assert c.get(GOV + "/history", headers=ids["admin_a"]).json()["items"] == []


def test_local_tenant_isolation_custom_and_tampered_review(identity, monkeypatch):
    c, _sessions, ids = identity
    confirm(c, ids)
    confirm(c, ids, {"denomination": "Independent Custom"}, church="b")
    assert (
        c.get(GOV, headers=ids["admin_b"]).json()["compatibility_status"]
        == "requires_configuration"
    )
    assert c.post(GOV + "/preview", headers=ids["admin_b"], json={}).status_code == 409
    member, _ = register(c)
    for suffix in ["", "/history", "/versions/1"]:
        assert c.get(GOV + suffix, headers=member).status_code == 403
        assert (
            c.get(
                GOV + suffix, headers={**ids["admin_a"], "X-Vinyrd-Branch-ID": ids["b"]}
            ).status_code
            == 403
        )
    release(monkeypatch)
    data = review(c, ids["admin_a"], target_version=2)
    payload = approval(data, target_version=2)
    assert c.post(GOV + "/approve", headers=member, json=payload).status_code == 403
    payload["preview_token"] = "0" * 64
    assert c.post(GOV + "/approve", headers=ids["admin_a"], json=payload).status_code == 409


def test_v1_release_content_is_pinned():
    from app.services.denominations_v1 import DENOMINATION_CATALOG

    digest = hashlib.sha256(
        json.dumps(DENOMINATION_CATALOG, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert digest == "50081fdc10026cff8a7122764e51b1ad1b8b797aaf9abb131a4ac1d28a979d3b"


def test_office_override_survives_upgrade_and_suggestions_do_not_grant(identity, monkeypatch):
    c, sessions, ids = identity
    config = confirm(c, ids)
    position = config["hierarchy_snapshot"]["levels"][-1]["positions"][0]["key"]
    patch = [
        {
            "level_key": "local_church",
            "position_key": position,
            "labels": {"en": "Our approved pastor"},
        }
    ]
    data = review(c, ids["admin_a"], overrides=patch)
    assert (
        c.post(
            GOV + "/approve", headers=ids["admin_a"], json=approval(data, overrides=patch)
        ).status_code
        == 200
    )

    def mutate(t):
        t["levels"][-1]["positions"][0]["labels"]["en"] = "Future template pastor"
        t["levels"][-1]["positions"][0]["permission_role"] = "accountant"
        t["levels"][-1]["positions"].append(
            {
                "key": "fixture_office",
                "title": "Fixture Office",
                "labels": {"en": "Fixture Office"},
                "permission_role": "usher",
            }
        )

    release(monkeypatch, mutate=mutate)
    data = review(c, ids["admin_a"], target_version=2)
    assert any(p["status"] == "added" for p in data["positions"])
    assert (
        c.post(
            GOV + "/approve", headers=ids["admin_a"], json=approval(data, target_version=2)
        ).status_code
        == 200
    )
    config = c.get(API + "/setup", headers=ids["admin_a"]).json()
    assert config["terminology"]["positions"][position]["en"]["label"] == "Our approved pastor"
    assert (
        saved(sessions, ids["a"])["hierarchy_snapshot"]["governance"]["base_levels"][-1][
            "positions"
        ][0]["labels"]["en"]
        == "Future template pastor"
    )


def test_existing_institution_supplied_custom_snapshot_can_approve_local_labels(identity):
    c, sessions, ids = identity
    confirm(c, ids, {"denomination": "Custom Fellowship"})
    with sessions() as db:
        config = db.get(ChurchOrganizationConfiguration, UUID(ids["a"]))
        unit = OrganizationUnit(
            denomination="Custom Fellowship",
            level_key="fellowship",
            canonical_name="Official proper name",
            normalized_name="official proper name",
            owner_branch_id=UUID(ids["a"]),
            match_key=uuid4().hex,
            labels_snapshot={"en": "Fellowship"},
        )
        db.add(unit)
        db.flush()
        config.local_unit_id = unit.id
        config.setup_status = "configured"
        config.hierarchy_snapshot = {
            "levels": [
                {
                    "key": "fellowship",
                    "label": "Fellowship",
                    "labels": {"en": "Fellowship"},
                    "positions": [],
                    "optional": False,
                }
            ],
            "path": [{"unit_id": str(unit.id), "level_key": "fellowship"}],
        }
        config.terminology_snapshot = {"fellowship": {"en": "Fellowship"}}
        db.get(Branch, UUID(ids["a"])).organization_unit_id = unit.id
        db.commit()
    patch = [{"level_key": "fellowship", "labels": {"en": "Our Fellowship"}}]
    data = review(c, ids["admin_a"], overrides=patch)
    assert data["compatibility_status"] == "compatible" and data["target_version"] is None
    assert (
        c.post(
            GOV + "/approve", headers=ids["admin_a"], json=approval(data, overrides=patch)
        ).status_code
        == 200
    )
    config = c.get(API + "/setup", headers=ids["admin_a"]).json()
    assert config["denomination"] == "Custom Fellowship"
    assert config["terminology"]["local_church"]["sw"]["label"] == "Our Fellowship"
    assert config["organization_path"][0]["canonical_name"] == "Official proper name"


@pytest.mark.parametrize(
    "malformed", ["official_without_evidence", "wrong_identity", "missing_english"]
)
def test_malformed_registry_entry_is_rejected(identity, monkeypatch, malformed):
    c, _sessions, ids = identity
    confirm(c, ids)

    def mutate(t):
        if malformed == "official_without_evidence":
            t["provenance"] = "denomination_official"
        elif malformed == "wrong_identity":
            t["value"] = "Catholic"
        else:
            t["levels"][-1]["labels"] = {"sw": "Kanisa"}

    release(monkeypatch, mutate=mutate)
    assert (
        c.post(GOV + "/preview", headers=ids["admin_a"], json={"target_version": 2}).status_code
        == 422
    )


def test_setup_does_not_clone_shared_ancestor_to_resolve_label_conflict(identity):
    c, sessions, ids = identity
    config = confirm(c, ids, tag_payload(public=True))
    with sessions() as db:
        root = db.get(OrganizationUnit, UUID(config["organization_path"][0]["id"]))
        root.labels_snapshot = {"en": "Previously published institution label"}
        db.commit()
        before = list(db.scalars(select(OrganizationUnit.id)))
    rejected = c.post(
        API + "/confirm", headers=ids["admin_b"], json=tag_payload(public=True, church="Church B")
    )
    assert rejected.status_code == 409 and "independent review" in rejected.text
    with sessions() as db:
        assert list(db.scalars(select(OrganizationUnit.id))) == before
        assert db.get(ChurchOrganizationConfiguration, UUID(ids["b"])) is None


def test_reused_position_key_is_resolved_in_assigned_level(identity):
    c, _sessions, ids = identity
    confirm(
        c,
        ids,
        {
            "denomination": "Catholic",
            "template_version": 1,
            "organization_level": "diocese",
            "units": [
                {"level_key": "ecclesiastical_province", "canonical_name": "Province"},
                {"level_key": "diocese", "canonical_name": "Diocese"},
            ],
        },
    )
    config = c.get(API + "/setup", headers=ids["admin_a"]).json()
    actor = c.get("/api/v1/auth/me", headers=ids["admin_a"]).json()["user"]["id"]
    assert (
        c.put(
            API + "/assignments",
            headers=ids["admin_a"],
            json={
                "user_id": actor,
                "organization_unit_id": config["local_unit_id"],
                "position_key": "vicar_general",
                "permission_role": "administrator",
            },
        ).status_code
        == 200
    )
    patch = [
        {
            "level_key": "diocese",
            "position_key": "vicar_general",
            "labels": {"en": "Approved diocesan vicar"},
        }
    ]
    data = review(c, ids["admin_a"], overrides=patch)
    assert (
        c.post(
            GOV + "/approve", headers=ids["admin_a"], json=approval(data, overrides=patch)
        ).status_code
        == 200
    )
    context = c.get("/api/v1/organization-access/tree", headers=ids["admin_a"]).json()["branches"][
        0
    ]
    assert context["display_position_title"] == "Approved diocesan vicar"
    staff = c.get("/api/v1/admin/users", headers=ids["admin_a"]).json()["users"][0]
    assert staff["display_position_title"] == "Approved diocesan vicar"
    terms = c.get(API + "/setup", headers=ids["admin_a"]).json()["terminology"][
        "positions_by_level"
    ]
    assert terms["diocese"]["vicar_general"]["en"]["label"] == "Approved diocesan vicar"
    assert terms["ecclesiastical_province"]["vicar_general"]["en"]["label"] == "Vicar General"

from uuid import UUID

import pytest

from app.models import Member
from app.services.denominations import denomination_catalog, normalize_denomination
from app.services.localization import bilingual_label, localized_label, normalize_locale
from tests.test_global_identity import approve, register, request

pytest_plugins = ["tests.test_global_identity"]


@pytest.mark.parametrize(
    "locale,expected", [("sw", "Jimbo"), ("en", "District"), ("fr", "District"), (None, "District")]
)
def test_localized_label(locale, expected):
    assert localized_label({"en": "District", "sw": "Jimbo"}, locale) == expected


def test_fallback_and_bilingual_labels():
    assert normalize_locale("sw-TZ") == "sw"
    assert normalize_locale("unknown", "sw") == "sw"
    assert normalize_locale(None, "unsupported") == "en"
    assert localized_label({"en": "District"}, "sw") == "District"
    assert localized_label({}, "sw") == ""
    assert bilingual_label({"en": "District", "sw": "Jimbo"}) == "Jimbo (District)"
    assert bilingual_label({"en": "District"}) == "District"


def test_tag_canonical_contract_and_detached_labels(identity):
    client, _, _ = identity
    catalogue = client.get("/api/v1/network/denominations").json()["items"]
    tag = next(item for item in catalogue if item["value"] == "Assemblies of God")
    assert normalize_denomination(" TAG ") == tag["value"]
    assert tag["aliases"] == ["TAG", "Tanzania Assemblies of God"]
    assert [level["key"] for level in tag["levels"]] == [
        "national_church",
        "zone",
        "district",
        "section",
        "local_church",
    ]
    levels = {level["key"]: level for level in tag["levels"]}
    assert levels["district"]["labels"] == {"en": "District", "sw": "Jimbo"}
    assert levels["district"]["label"] == "District"
    assert levels["section"]["labels"]["sw"] == "Sehemu"
    assert levels["local_church"]["labels"]["sw"] == "Kanisa la Mahali Pamoja"
    bishop = levels["district"]["positions"][0]
    assert {key: value for key, value in bishop.items() if key != "presentation"} == {
        "key": "district_bishop",
        "title": "District Bishop",
        "labels": {"en": "District Bishop", "sw": "Askofu wa Jimbo"},
        "permission_role": "administrator",
    }
    assert [p["labels"]["sw"] for p in levels["zone"]["positions"]] == [
        "Mwenyekiti wa Ushirika wa Kanda",
        "Katibu / Mtunza Hazina wa Kanda",
    ]
    for denomination in catalogue:
        for level in denomination["levels"]:
            assert level["label"] == level["labels"]["en"]
            assert len({p["key"] for p in level["positions"]}) == len(level["positions"])
            for position in level["positions"]:
                assert position["title"] == position["labels"]["en"]
                if denomination is tag:
                    assert position["labels"]["sw"]
    copied = denomination_catalog()
    copied[0]["levels"][0]["labels"]["en"] = "Changed"
    copied[0]["levels"][0]["positions"][0]["labels"]["en"] = "Changed"
    assert "Changed" not in str(denomination_catalog())


def test_global_language_preserves_legacy_preferences_and_old_clients(identity):
    client, sessions, ids = identity
    headers, _ = register(client)
    assert client.get("/api/v1/auth/me", headers=headers).json()["user"]["ui_language"] == "en"
    with sessions() as db:
        db.get(Member, UUID(ids["offline"])).preferred_language = "sw"
        db.commit()
    rid = request(client, headers, ids["a"])
    assert approve(client, ids, rid, member=ids["offline"]).status_code == 200
    data = {"first_name": "Ada", "last_name": "Person", "ui_language": "sw"}
    assert (
        client.put("/api/v1/identity/me", headers=headers, json=data).json()["ui_language"] == "sw"
    )
    assert client.get("/api/v1/auth/me", headers=headers).json()["user"]["ui_language"] == "sw"
    login = client.post(
        "/api/v1/auth/login", json={"email": "ada@test.local", "password": "long-test-password"}
    )
    assert login.json()["user"]["ui_language"] == "sw"
    del data["ui_language"]
    assert (
        client.put("/api/v1/identity/me", headers=headers, json=data).json()["ui_language"] == "sw"
    )
    data["ui_language"] = "en"
    assert (
        client.put("/api/v1/identity/me", headers=headers, json=data).json()["ui_language"] == "en"
    )
    with sessions() as db:
        assert db.get(Member, UUID(ids["offline"])).preferred_language == "sw"
    for invalid in ("fr", "sw-TZ", "", None):
        data["ui_language"] = invalid
        assert client.put("/api/v1/identity/me", headers=headers, json=data).status_code == 422
    other, _ = register(client, "other@test.local")
    assert client.get("/api/v1/identity/me", headers=other).json()["ui_language"] == "en"

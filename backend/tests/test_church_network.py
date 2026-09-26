from tests.test_global_identity import approve, register, request

pytest_plugins = ["tests.test_global_identity"]


def publish(client, admin, **changes):
    payload = {
        "name": "Church public",
        "country": "TZ",
        "region": "Arusha",
        "city": "Arusha",
        "is_published": True,
    }
    payload.update(changes)
    return client.put("/api/v1/network/admin/profile", headers=admin, json=payload)



def test_denomination_catalog_exposes_architecture_templates(identity):
    c, _, _ = identity
    response = c.get("/api/v1/network/denominations")
    assert response.status_code == 200
    data = response.json()
    assert data["custom_allowed"] is True
    by_value = {item["value"]: item for item in data["items"]}
    assert [level["label"] for level in by_value["Assemblies of God"]["levels"]] == [
        "National Church / General Council",
        "Zone (Kanda)",
        "District (Jimbo)",
        "Section (Sehemu)",
        "Local Church",
    ]
    assert [level["label"] for level in by_value["Africa Inland Church"]["levels"]] == [
        "National Church",
        "Diocese",
        "Pastorate",
        "Local Congregation",
    ]
    assert by_value["Catholic"]["governance_model"] == "episcopal"
    assert by_value["Non-denominational"]["levels"][-1]["label"] == "Local Church"

def test_publication_is_explicit_and_scoped(identity):
    c, _, ids = identity
    assert c.get("/api/v1/network/churches").json()["items"] == []
    assert publish(c, ids["admin_a"], is_published=False).status_code == 200
    assert c.get("/api/v1/network/churches/" + ids["a"]).status_code == 404
    assert publish(c, ids["admin_a"], church_id=ids["b"]).status_code == 422
    assert (
        publish(c, ids["admin_a"], public_events=[{"title": "Welcome service"}]).status_code == 200
    )
    data = c.get("/api/v1/network/churches/" + ids["a"]).json()
    assert data["public_events"][0]["title"] == "Welcome service"
    assert not {"is_published", "sms_provider", "users", "members", "branch_id"} & data.keys()
    assert c.get("/api/v1/network/churches/" + ids["b"]).status_code == 404
    user, _ = register(c)
    assert [row["id"] for row in c.get("/api/v1/identity/churches", headers=user).json()] == [
        ids["a"]
    ]
    assert publish(c, user).status_code == 403
    assert c.get("/api/v1/network/admin/requests", headers=user).status_code == 403


def test_discovery_geography_and_pagination(identity):
    c, _, ids = identity
    publish(c, ids["admin_a"], name="Arusha Chapel", denomination="Lutheran")
    publish(
        c, ids["admin_b"], name="Nairobi Chapel", country="KE", region="Nairobi", city="Nairobi"
    )
    for query in [
        "view=tanzania",
        "country=tz",
        "region=arusha",
        "city=Arusha",
        "denomination=lutheran",
        "q=Arusha",
        "view=local&city=Arusha",
    ]:
        rows = c.get("/api/v1/network/churches?" + query).json()["items"]
        assert [r["church_id"] for r in rows] == [ids["a"]]
    assert c.get("/api/v1/network/churches?view=local").status_code == 422
    assert c.get("/api/v1/network/churches?limit=1").json()["has_more"]
    assert len(c.get("/api/v1/network/churches?limit=1&offset=1").json()["items"]) == 1
    assert c.get("/api/v1/network/churches?q=%25").json()["items"] == []


def test_consent_queue_matching_and_more_information(identity):
    c, _, ids = identity
    user, _ = register(c)
    rid = request(c, user, ids["a"])
    row = c.get("/api/v1/network/admin/requests", headers=ids["admin_a"]).json()["items"][0]
    assert "email" not in row["applicant_snapshot"]
    assert [m["id"] for m in row["possible_matches"]] == [ids["offline"]]
    assert c.get("/api/v1/network/admin/requests", headers=ids["admin_b"]).json()["items"] == []
    assert approve(c, ids, rid, church="b", member=ids["offline"]).status_code == 404
    review = "/api/v1/identity/requests/" + rid + "/review"
    assert (
        c.post(
            review,
            headers=ids["admin_a"],
            json={"status": "more_info_required", "reason": "Please verify your member number."},
        ).status_code
        == 200
    )
    assert (
        c.get("/api/v1/network/me", headers=user).json()["requests"][0]["status"]
        == "more_info_required"
    )
    assert approve(c, ids, rid, member=ids["offline"]).status_code == 200
    assert (
        c.get("/api/v1/network/admin/requests?status=approved", headers=ids["admin_a"]).json()[
            "items"
        ][0]["possible_matches"]
        == []
    )


def test_follow_reject_and_private_access(identity):
    c, _, ids = identity
    user, _ = register(c)
    follow = "/api/v1/identity/churches/" + ids["a"] + "/follow"
    assert c.put(follow, headers=user).status_code == 200
    response = c.post(
        "/api/v1/identity/churches/" + ids["a"] + "/requests",
        headers=user,
        json={"share_contact": True},
    )
    rid = response.json()["id"]
    row = c.get("/api/v1/network/admin/requests", headers=ids["admin_a"]).json()["items"][0]
    assert row["applicant_snapshot"]["email"] == "ada@test.local"
    for endpoint in ["me", "events", "groups", "messages"]:
        assert c.get("/api/v1/member-portal/" + endpoint, headers=user).status_code == 403
    assert (
        c.post(
            "/api/v1/identity/requests/" + rid + "/review",
            headers=ids["admin_a"],
            json={"status": "rejected", "reason": "Please contact the office."},
        ).status_code
        == 200
    )
    assert c.get("/api/v1/auth/me", headers=user).status_code == 200
    assert ids["a"] in c.get("/api/v1/network/me", headers=user).json()["follows"]
    assert c.delete(follow, headers=user).status_code == 200
    assert c.get("/api/v1/network/me", headers=user).json()["follows"] == []
    assert request(c, user, ids["b"])


def test_context_does_not_change_home_or_membership(identity):
    c, _, ids = identity
    user, _ = register(c)
    assert approve(c, ids, request(c, user, ids["a"]), member=ids["offline"]).status_code == 200
    assert (
        c.post("/api/v1/network/me/initialize-home", headers=user).json()["home_church_id"]
        == ids["a"]
    )
    assert approve(c, ids, request(c, user, ids["b"]), church="b").status_code == 200
    assert (
        c.get("/api/v1/member-portal/me", headers={**user, "X-Church-ID": ids["b"]}).status_code
        == 200
    )
    assert (
        c.post("/api/v1/network/me/initialize-home", headers=user).json()["home_church_id"]
        == ids["a"]
    )
    memberships = c.get("/api/v1/network/me", headers=user).json()["memberships"]
    b = next(m for m in memberships if m["church_id"] == ids["b"])
    assert (
        c.put("/api/v1/identity/memberships/" + b["id"] + "/primary", headers=user).status_code
        == 200
    )
    assert (
        c.post("/api/v1/network/me/initialize-home", headers=user).json()["home_church_id"]
        == ids["b"]
    )
    assert len(c.get("/api/v1/network/me", headers=user).json()["memberships"]) == 2


def test_admin_cannot_review_self(identity):
    c, _, ids = identity
    rid = request(c, ids["admin_a"], ids["a"])
    for status in ["approved", "rejected", "more_info_required"]:
        assert (
            c.post(
                "/api/v1/identity/requests/" + rid + "/review",
                headers=ids["admin_a"],
                json={"status": status},
            ).status_code
            == 403
        )


def test_approval_does_not_copy_unshared_contact(identity):
    c, _, ids = identity
    user, _ = register(c)
    assert approve(c, ids, request(c, user, ids["b"]), church="b").status_code == 200
    church_members = c.get("/api/v1/members/", headers=ids["admin_b"]).json()["members"]
    created = next(m for m in church_members if m["first_name"] == "Ada")
    assert created["email"] is None and created["phone"] is None


def test_attendance_tenant_separation(identity):
    c, _, ids = identity
    event = c.post(
        "/api/v1/attendance/events", headers=ids["admin_b"], json={"name": "Private B service"}
    )
    assert event.status_code == 201, event.text
    eid = event.json()["id"]
    checkin = c.post(
        "/api/v1/attendance/check-ins",
        headers=ids["admin_b"],
        json={"event_id": eid, "person_type": "member", "person_id": ids["other"]},
    )
    assert checkin.status_code == 201, checkin.text
    a = c.get("/api/v1/attendance/", headers=ids["admin_a"])
    assert a.status_code == 200
    assert "Private B" not in a.text and ids["other"] not in a.text and eid not in a.text
    assert c.get("/api/v1/attendance/events", headers=ids["admin_a"]).json() == []
    assert (
        c.get("/api/v1/attendance/events/" + eid + "/qr-token", headers=ids["admin_a"]).status_code
        == 404
    )

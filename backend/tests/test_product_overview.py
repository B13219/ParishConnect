from fastapi.testclient import TestClient

from app.main import create_app


def test_product_overview_is_pilot_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Vinyrd"
    assert body["status"] == "pilot-ready"
    assert body["version"] == "1.0.0"
    assert "member_portal" in body["modules"]
    assert "pastoral_care" in body["modules"]
    assert body["links"]["staff"] == "/staff/"
    assert body["links"]["member"] == "/member/"


def test_same_origin_frontends_are_served() -> None:
    client = TestClient(create_app())

    landing = client.get("/", follow_redirects=False)
    assert landing.status_code == 307
    assert landing.headers["location"] == "/staff/"

    staff = client.get("/staff/")
    assert staff.status_code == 200
    assert "Vinyrd Staff Console" in staff.text
    assert 'rel="icon"' in staff.text
    assert "vinyrd-crest-v2.webp" in staff.text
    assert "vinyrd-full-logo.webp" in staff.text

    favicon = client.get("/favicon.ico", follow_redirects=False)
    assert favicon.status_code == 307
    assert favicon.headers["location"] == "/staff/assets/vinyrd-crest-v2.webp"

    landing = client.get("/member/")
    assert landing.status_code == 200
    assert "Belong deeper" in landing.text
    assert "vinyrd-crest-v2.webp" in landing.text
    assert "landing-nav-crest" in landing.text
    assert "landing-hero-crest" in landing.text

    member = client.get("/member/login.html")
    assert member.status_code == 200
    assert "Member Sign In - Vinyrd" in member.text
    assert "vinyrd-crest-v2.webp" in member.text
    assert "vinyrd-full-logo.webp" in member.text

    home = client.get("/member/home.html")
    assert home.status_code == 200
    assert "Member Space" in home.text
    assert "vinyrd-crest-v2.webp" in home.text


def test_master_brand_assets_are_served() -> None:
    client = TestClient(create_app())

    for path in (
        "/staff/assets/vinyrd-full-logo.webp",
        "/staff/assets/vinyrd-crest-v2.webp",
        "/member/assets/vinyrd-full-logo.webp",
        "/member/assets/vinyrd-crest-v2.webp",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/webp")

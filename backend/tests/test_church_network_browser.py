"""Opt-in real Chromium journey: VINYRD_TEST_BROWSER=1 pytest tests/test_church_network_browser.py.

Uses only the existing disposable SQLite fixture and a loopback HTTP server.
Install the dev browser extra and run `python -m playwright install chromium` first.
"""

import os
import sqlite3
import threading
import time
from pathlib import Path
from uuid import UUID

import pytest
import uvicorn
from sqlalchemy import create_engine

from app.core.security import password_hash
from app.models import User

pytest_plugins = ["tests.test_global_identity"]
pytestmark = pytest.mark.skipif(
    os.getenv("VINYRD_TEST_BROWSER") != "1", reason="Opt-in Chromium journey"
)


def test_member_and_admin_network_journey(identity, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    c, sessions, ids = identity
    # Browser dashboard issues concurrent requests: use independent SQLite connections.
    database_path = tmp_path / "browser.sqlite"
    with sessions.kw["bind"].connect() as source, sqlite3.connect(database_path) as target:
        source.connection.driver_connection.backup(target)
    browser_db = create_engine(
        "sqlite:///" + database_path.as_posix(),
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    sessions.configure(bind=browser_db)
    with sessions() as db:
        db.add(
            User(
                branch_id=UUID(ids["b"]),
                member_id=UUID(ids["other"]),
                name="Legacy Person",
                email="legacy@test.local",
                password_hash=password_hash("test-password"),
            )
        )
        db.commit()
    server = uvicorn.Server(uvicorn.Config(c.app, host="127.0.0.1", port=8003, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        assert server.started
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            member_context = browser.new_context(viewport={"width": 390, "height": 844})
            staff_context = browser.new_context(viewport={"width": 1440, "height": 1000})
            member, staff = member_context.new_page(), staff_context.new_page()
            errors = []
            member.on("pageerror", lambda e: errors.append(str(e)))
            staff.on("pageerror", lambda e: errors.append(str(e)))
            base = "http://127.0.0.1:8003"
            legacy_context = browser.new_context(viewport={"width": 390, "height": 844})
            legacy = legacy_context.new_page()
            legacy.goto(base + "/member/login.html")
            legacy.locator('[name="email"]').fill("legacy@test.local")
            legacy.locator('[name="password"]').fill("test-password")
            legacy.locator("#loginButton").click()
            playwright.expect(legacy.get_by_label("Currently viewing")).to_have_value(ids["b"])
            old_token = legacy.evaluate("VinyrdClient.token()")
            old_data = c.get(
                "/api/v1/member-portal/me", headers={"Authorization": "Bearer " + old_token}
            ).json()
            assert old_data["giving"]["total_amount"] == "99.00"
            legacy_context.close()
            staff.goto(base + "/staff/")
            staff.locator("#loginEmail").fill("a@test.local")
            staff.locator("#loginPassword").fill("test-password")
            staff.get_by_role("button", name="Enter Vinyrd").click()
            staff.locator('[data-section-link="registration-requests"]').click()
            form = staff.locator("#publicChurchForm")
            form.locator('[name="name"]').fill("Arusha Community Church")
            form.locator('[name="country"]').fill("TZ")
            form.locator('[name="region"]').fill("Arusha")
            form.locator('[name="city"]').fill("Arusha")
            form.get_by_label("About", exact=True).fill("Welcome to our public church community.")
            form.get_by_label("Publish this profile").check()
            form.get_by_role("button", name="Save public profile").click()
            playwright.expect(staff.locator("#networkAdminStatus")).to_contain_text("published")
            result = c.put(
                "/api/v1/network/admin/profile",
                headers=ids["admin_b"],
                json={
                    "name": "Nairobi Community Church",
                    "country": "KE",
                    "city": "Nairobi",
                    "is_published": True,
                },
            )
            assert result.status_code == 200
            member.goto(base + "/member/account.html")
            member.get_by_label("First name").fill("Ada")
            member.get_by_label("Last name").fill("Person")
            member.get_by_label("Email", exact=True).fill("ada@test.local")
            member.get_by_label("Password", exact=True).fill("long-test-password")
            member.get_by_role("button", name="Create VINYRD account").click()
            playwright.expect(member.locator("#accountStatus")).to_contain_text(
                "Your account is ready"
            )
            member.get_by_role("link", name="Find a church").click()
            playwright.expect(member.locator("#networkContent")).to_contain_text(
                "Arusha Community Church"
            )
            member.get_by_label("City", exact=True).fill("Arusha")
            member.get_by_role("button", name="Search churches").click()
            playwright.expect(member.locator("#networkContent .network-card")).to_have_count(1)
            member.get_by_role("link", name="View church", exact=True).click()
            member.get_by_role("button", name="Follow", exact=True).click()
            playwright.expect(
                member.get_by_role("button", name="Unfollow", exact=True)
            ).to_be_visible()
            token = member.evaluate("VinyrdClient.token()")
            headers = {"Authorization": "Bearer " + token}
            assert c.get("/api/v1/member-portal/me", headers=headers).status_code == 403
            member.get_by_label("Membership request message").fill(
                "I already attend this church. Please link my record."
            )
            member.get_by_role("button", name="Request to join", exact=True).click()
            playwright.expect(member.locator("#networkContent")).to_contain_text("pending review")
            staff.get_by_role("button", name="Refresh requests", exact=True).click()
            card = staff.locator(".request-card").filter(has_text="Ada Person")
            playwright.expect(card).to_be_visible()
            card.get_by_label("Reviewer note or rejection reason").fill(
                "Please confirm your existing church record."
            )
            card.get_by_role("button", name="Request more information", exact=True).click()
            staff.locator("#networkRequestStatus").select_option("more_info_required")
            card = staff.locator(".request-card").filter(has_text="Ada Person")
            playwright.expect(card).to_contain_text("Please confirm")
            member.reload()
            playwright.expect(member.locator("#networkContent")).to_contain_text(
                "More information requested"
            )
            card.get_by_label("Link existing member").select_option(ids["offline"])
            card.get_by_label("I verified").check()
            card.get_by_role("button", name="Approve / link selected member").click()
            playwright.expect(staff.locator("#networkRequests")).to_contain_text("No requests")
            member.goto(base + "/member/my-church.html")
            playwright.expect(member.locator("#networkContent")).to_contain_text("Home Church")
            memberships = c.get("/api/v1/network/me", headers=headers).json()["memberships"]
            assert memberships[0]["legacy_member_id"] == ids["offline"]
            member.goto(base + "/member/church.html?id=" + ids["b"])
            member.get_by_role("button", name="Request to join", exact=True).click()
            playwright.expect(member.locator("#networkContent")).to_contain_text("pending review")
            rid = c.get("/api/v1/network/admin/requests", headers=ids["admin_b"]).json()["items"][
                0
            ]["id"]
            assert (
                c.post(
                    "/api/v1/identity/requests/" + rid + "/review",
                    headers=ids["admin_a"],
                    json={"status": "approved"},
                ).status_code
                == 404
            )
            assert (
                c.post(
                    "/api/v1/identity/requests/" + rid + "/review",
                    headers=ids["admin_b"],
                    json={"status": "rejected", "reason": "Please introduce yourself."},
                ).status_code
                == 200
            )
            member.reload()
            playwright.expect(member.locator("#networkContent")).to_contain_text(
                "Previous request rejected"
            )
            member.get_by_label("Membership request message").fill("I worship in both churches.")
            member.get_by_role("button", name="Request to join", exact=True).click()
            playwright.expect(member.locator("#networkContent")).to_contain_text("pending review")
            rid = c.get("/api/v1/network/admin/requests", headers=ids["admin_b"]).json()["items"][
                0
            ]["id"]
            assert (
                c.post(
                    "/api/v1/identity/requests/" + rid + "/review",
                    headers=ids["admin_b"],
                    json={"status": "approved"},
                ).status_code
                == 200
            )
            member.goto(base + "/member/my-church.html")
            member.locator(".network-card").filter(
                has=member.get_by_role("heading", name="Church B", exact=True)
            ).get_by_role("button", name="Make Home Church").click()
            playwright.expect(member.locator("#networkStatus")).to_have_text("Saved.")
            member.goto(base + "/member/home.html")
            member.get_by_label("Currently viewing").select_option(ids["a"])
            playwright.expect(member.get_by_label("Currently viewing")).to_have_value(ids["a"])
            data = c.get("/api/v1/network/me", headers=headers).json()
            assert len(data["memberships"]) == 2
            assert next(m for m in data["memberships"] if m["is_primary"])["church_id"] == ids["b"]
            member.goto(base + "/member/following.html")
            playwright.expect(member.locator("#networkContent")).to_contain_text(
                "Arusha Community Church"
            )
            member.get_by_role("button", name="Unfollow", exact=True).click()
            playwright.expect(member.locator("#networkContent")).to_contain_text("aren't following")
            member.goto(base + "/member/discover.html")
            playwright.expect(member.locator("#networkContent .network-card")).to_have_count(2)
            assert member.evaluate("document.documentElement.scrollWidth <= innerWidth")
            if os.getenv("VINYRD_BROWSER_ARTIFACTS"):
                out = Path(os.environ["VINYRD_BROWSER_ARTIFACTS"])
                out.mkdir(parents=True, exist_ok=True)
                member.screenshot(path=str(out / "discover-mobile.png"), full_page=True)
                staff.screenshot(
                    path=str(out / "registration-requests-desktop.png"), full_page=True
                )
            member.goto(base + "/member/account.html?mode=profile")
            playwright.expect(member.get_by_label("First name")).to_have_value("Ada")
            member.get_by_label("First name").fill("Adanna")
            member.get_by_role("button", name="Save profile").click()
            playwright.expect(member.locator("#accountStatus")).to_have_text("Profile saved.")
            member.goto(base + "/member/profile.html")
            playwright.expect(member.locator("#profileName")).to_have_text("Adanna Person")
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        browser_db.dispose()

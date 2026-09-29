"""Real Chromium scope selection and grant lifecycle, without mocked HTTP."""

import os
import sqlite3
import threading
import time

import pytest
import uvicorn
from sqlalchemy import create_engine

from tests.test_organization_access import API, login

pytest_plugins = ["tests.test_organization_access"]
pytestmark = pytest.mark.skipif(os.getenv("VINYRD_TEST_BROWSER") != "1", reason="Opt-in Chromium")


def test_scope_console_browser(hierarchy, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    c, sessions, ids = hierarchy
    path = tmp_path / "hierarchy.sqlite"
    with sessions.kw["bind"].connect() as source, sqlite3.connect(path) as target:
        source.connection.driver_connection.backup(target)
    engine = create_engine(
        "sqlite:///" + path.as_posix(), connect_args={"check_same_thread": False, "timeout": 30}
    )
    sessions.configure(bind=engine)
    server = uvicorn.Server(uvicorn.Config(c.app, host="127.0.0.1", port=8003, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        assert server.started
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("http://127.0.0.1:8003/staff/")
            page.locator("#loginEmail").fill("district@scope.test")
            page.locator("#loginPassword").fill("test-password")
            page.get_by_role("button", name="Enter Vinyrd").click()
            panel = page.locator("#organization-access")
            tree = panel.get_by_role("list", name="Authorized organization tree")
            playwright.expect(tree).to_contain_text("district")
            assert "district2" not in tree.inner_text()
            assert "diocese" not in tree.inner_text()
            branch = panel.get_by_label("Current church context")
            assert branch.locator("option").count() == 4
            with page.expect_navigation():
                branch.select_option(ids["branches"]["b"])
            page.wait_for_function("state.staffContext?.id === " + repr(ids["branches"]["b"]))
            playwright.expect(branch).to_have_value(ids["branches"]["b"])
            assert page.evaluate("state.staffContext.id") == ids["branches"]["b"]
            assert (
                page.evaluate(
                    "async () => (await fetch(API_BASE+'/members/',{headers:authHeaders()})).status"
                )
                == 200
            )
            assert (
                page.evaluate(
                    "async (b) => (await fetch(API_BASE+'/members/',{headers:{...authHeaders(),'X-Vinyrd-Branch-ID':b}})).status",
                    ids["branches"]["d"],
                )
                == 403
            )
            panel.get_by_label("Organization context", exact=True).select_option(
                ids["units"]["district"]
            )
            playwright.expect(
                panel.get_by_role("heading", name="Church offices — no application permissions")
            ).to_be_visible()
            playwright.expect(
                panel.get_by_role("heading", name="VINYRD access grants", exact=True)
            ).to_be_visible()
            playwright.expect(
                panel.get_by_label("Scope for district / Jimbo", exact=True)
            ).to_be_visible()
            panel.get_by_label("Grant recipient VINYRD account ID").fill(ids["users"]["target"])
            panel.get_by_label("Scope for district / Jimbo", exact=True).select_option(
                "descendants"
            )
            panel.get_by_role("button", name="Create access grant", exact=True).click()
            target_row = panel.locator('[data-grant-user="' + ids["users"]["target"] + '"]')
            playwright.expect(target_row.get_by_label("Grant status", exact=True)).to_be_visible()
            target_headers = login(c, "target")
            assert len(c.get(API + "/tree", headers=target_headers).json()["branches"]) == 3
            target_row.get_by_label("Grant status", exact=True).select_option("revoked")
            target_row.get_by_role("button", name="Save access grant", exact=True).click()
            playwright.expect(target_row.get_by_label("Grant status", exact=True)).to_have_value(
                "revoked"
            )
            assert c.get(API + "/tree", headers=target_headers).json()["branches"] == []
            # Existing token after revocation gets an empty selector on a fresh console load.
            target = browser.new_page()
            target.goto("http://127.0.0.1:8003/staff/")
            target.locator("#loginEmail").fill("target@scope.test")
            target.locator("#loginPassword").fill("test-password")
            target.get_by_role("button", name="Enter Vinyrd").click()
            playwright.expect(target.get_by_label("Current church context")).to_be_visible()
            assert target.get_by_label("Current church context").locator("option").count() == 1
            assert not errors, errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        engine.dispose()

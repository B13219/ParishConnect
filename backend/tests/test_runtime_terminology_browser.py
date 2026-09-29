import os
import sqlite3
import threading
import time
from uuid import UUID

import pytest
import uvicorn
from sqlalchemy import create_engine, select

from app.models import OrganizationAccessGrant, Profile, User
from tests.test_organization_setup import confirm

pytest_plugins = ["tests.test_global_identity"]
pytestmark = pytest.mark.skipif(os.getenv("VINYRD_TEST_BROWSER") != "1", reason="Opt-in Chromium")


@pytest.mark.parametrize("locale", ["en", "sw"])
def test_runtime_terminology_console_and_context_switch(identity, tmp_path, locale):
    playwright = pytest.importorskip("playwright.sync_api")
    c, sessions, ids = identity
    config = confirm(c, ids)
    catholic = confirm(
        c,
        ids,
        {
            "denomination": "Catholic",
            "template_version": 1,
            "organization_level": "parish",
            "units": [
                {"level_key": "diocese", "canonical_name": "Dar Diocese"},
                {"level_key": "parish", "canonical_name": "St Mary"},
            ],
        },
        church="b",
    )
    with sessions() as db:
        admin = db.scalar(select(User).where(User.email == "a@test.local"))
        db.get(Profile, admin.id).ui_language = locale
        db.add(
            OrganizationAccessGrant(
                user_id=admin.id,
                organization_unit_id=UUID(catholic["organization_path"][0]["id"]),
                permission_role="administrator",
                scope_mode="descendants",
            )
        )
        db.commit()
    path = tmp_path / "presentation.sqlite"
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
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://127.0.0.1:8003/staff/")
            page.locator("#loginEmail").fill("a@test.local")
            page.locator("#loginPassword").fill("test-password")
            page.get_by_role("button", name="Enter Vinyrd").click()
            header = page.locator("#staffOrganizationContext")
            local = (
                "Local Church / Kanisa la Mahali Pamoja"
                if locale == "en"
                else "Kanisa la Mahali Pamoja / Local Church"
            )
            playwright.expect(header).to_contain_text(local)
            page.locator('[data-section-link="registration-requests"]').click()
            setup = page.locator("#organizationSetup")
            bilingual = "District / Jimbo" if locale == "en" else "Jimbo / District"
            playwright.expect(setup).to_contain_text(bilingual)
            title = config["runtime_levels"][-1]["positions"][0]["presentation"][locale][
                "bilingual_label"
            ]
            playwright.expect(setup.get_by_label("Office title", exact=True)).to_contain_text(title)
            playwright.expect(
                setup.get_by_label("Intended permission profile (does not grant access)")
            ).to_be_visible()
            page.locator('[data-section-link="organization-access"]').click()
            selector = page.get_by_label("Current church context", exact=True)
            with page.expect_navigation():
                selector.select_option(ids["b"])
            playwright.expect(header).to_contain_text("Parish")
            playwright.expect(header).to_contain_text("Diocese")
            assert "Jimbo" not in header.inner_text()
            assert "Sehemu" not in header.inner_text()
            panel = page.locator("#organization-access")
            panel.get_by_label("Organization context", exact=True).select_option(
                catholic["local_unit_id"]
            )
            playwright.expect(panel.get_by_label("Church office", exact=True)).to_contain_text(
                "Parish Priest"
            )
            playwright.expect(panel).to_contain_text("Parish Summary")
            playwright.expect(
                panel.get_by_role("heading", name="VINYRD access grants", exact=True)
            ).to_be_visible()
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        engine.dispose()

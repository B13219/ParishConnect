import json
import os
import sqlite3
import threading
import time
from uuid import UUID

import pytest
import uvicorn
from sqlalchemy import create_engine, select

from app.models import OrganizationAccessGrant, User
from app.services import template_registry as registry
from tests.test_global_identity import register
from tests.test_organization_setup import confirm, tag_payload
from tests.test_template_governance import GOV, approval, release, review

pytest_plugins = ["tests.test_global_identity"]
pytestmark = pytest.mark.skipif(os.getenv("VINYRD_TEST_BROWSER") != "1", reason="Opt-in Chromium")


def test_governance_review_approval_history_rejection_and_context(identity, tmp_path, monkeypatch):
    playwright = pytest.importorskip("playwright.sync_api")
    c, sessions, ids = identity
    confirm(c, ids, tag_payload(public=True))
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
    member, _ = register(c)
    with sessions() as db:
        actor = db.scalar(select(User).where(User.email == "a@test.local"))
        db.add(
            OrganizationAccessGrant(
                user_id=actor.id,
                organization_unit_id=UUID(catholic["local_unit_id"]),
                permission_role="administrator",
                scope_mode="unit_only",
            )
        )
        db.commit()
    release(monkeypatch)
    path = tmp_path / "governance.sqlite"
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
            page.locator("#loginEmail").fill("a@test.local")
            page.locator("#loginPassword").fill("test-password")
            page.get_by_role("button", name="Enter Vinyrd").click()
            page.locator('[data-section-link="organization-access"]').click()
            panel = page.locator("#templateGovernance")
            playwright.expect(panel).to_contain_text("Installed: 1 · Available: 2")
            panel.get_by_role("button", name="Review upgrade", exact=True).click()
            playwright.expect(panel).to_contain_text(
                "en: Local Church v2 fixture / sw: Kanisa la Mahali Pamoja"
            )
            data = review(c, ids["admin_a"], target_version=2)
            denied = page.request.post(
                "http://127.0.0.1:8003" + GOV + "/approve",
                headers=member,
                data=approval(data, target_version=2),
            )
            assert denied.status == 403
            panel.get_by_role("button", name="Approve reviewed changes", exact=True).click()
            playwright.expect(panel).to_contain_text("Installed: 2")
            playwright.expect(panel).to_contain_text("Approved by")
            incompatible = registry.template("TAG", 2)
            incompatible["template_version"] = 3
            incompatible["levels"][0]["labels"]["en"] = "Fixture shared national change"
            monkeypatch.setattr(
                registry,
                "RELEASES",
                {**registry.RELEASES, ("Assemblies of God", 3): json.dumps(incompatible)},
            )
            page.get_by_role("button", name="Refresh organization access").click()
            playwright.expect(panel).to_contain_text("Available: 3")
            panel.get_by_role("button", name="Review upgrade", exact=True).click()
            playwright.expect(panel).to_contain_text("no partial publication")
            playwright.expect(
                panel.get_by_role("button", name="Approve reviewed changes")
            ).to_be_hidden()
            playwright.expect(panel).to_contain_text("Installed: 2")
            with page.expect_navigation():
                page.get_by_label("Current church context", exact=True).select_option(ids["b"])
            playwright.expect(page.locator("#staffOrganizationContext")).to_contain_text("Parish")
            playwright.expect(panel).to_contain_text("Only this church's local administrator")
            assert "Local Church v2 fixture" not in panel.inner_text()
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        engine.dispose()

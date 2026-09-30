"""Exercise real approval via restricted runtime HTTP on disposable staging fixtures."""

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.settings import settings


def main():
    base = os.environ["VINYRD_PILOT_BASE_URL"].rstrip("/")
    if os.getenv("VINYRD_SMOKE_DISPOSABLE_DATABASE") != "1" or urlparse(base).hostname not in (
        "127.0.0.1",
        "localhost",
    ):
        raise RuntimeError("Governance smoke requires explicit disposable loopback HTTP.")
    token = None

    def request(path, method="GET", payload=None, expected=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = Request(
            base + "/api/v1" + path,
            headers=headers,
            method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        try:
            with urlopen(req, timeout=20) as r:
                code, body = r.status, r.read()
        except HTTPError as e:
            code, body = e.code, e.read()
        assert code == expected, (path, code, body.decode()[:500])
        return json.loads(body)

    token = request(
        "/auth/login",
        "POST",
        {"email": settings.bootstrap_admin_email, "password": settings.bootstrap_admin_password},
    )["access_token"]
    api = "/network/admin/organization"
    before = request(api + "/setup")
    path_ids = [u["id"] for u in before["organization_path"]]
    override = {
        "overrides": [
            {"level_key": "local_church", "labels": {"en": "Smoke approved local church"}}
        ]
    }
    preview = request(api + "/governance/preview", "POST", override)
    assert preview["compatibility_status"] == "compatible"
    assert request(api + "/setup") == before
    payload = {
        **override,
        "expected_revision": preview["revision"],
        "preview_token": preview["preview_token"],
        "request_id": str(uuid4()),
    }
    applied = request(api + "/governance/approve", "POST", payload)
    assert not applied["idempotent"]
    assert request(api + "/governance/approve", "POST", payload)["idempotent"]
    request(
        api + "/governance/approve", "POST", {**payload, "request_id": str(uuid4())}, expected=409
    )
    after = request(api + "/setup")
    assert [u["id"] for u in after["organization_path"]] == path_ids
    assert after["terminology"]["local_church"]["en"]["label"] == "Smoke approved local church"
    assert (
        request(api + "/governance/history")["items"][0]["before"]["terminology_snapshot"]
        == before["terminology_snapshot"]
    )
    blocked = request(
        api + "/governance/preview",
        "POST",
        {"overrides": [{"level_key": "district", "labels": {"en": "Unapproved shared change"}}]},
    )
    assert blocked["compatibility_status"] == "requires_review"
    church = request("/admin/branch")["branch"]["id"]
    public = request("/network/churches/" + church)
    assert (
        public["organization_path"][-1]["presentation"]["en"]["label"]
        == "Smoke approved local church"
    )
    print(
        "Governance runtime HTTP: preview, explicit approval, repeat/stale checks, public labels, history and shared-ancestor blocking passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

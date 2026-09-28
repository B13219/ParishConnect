"""Hierarchy smoke against real production HTTP with disposable owner-created fixtures."""

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.security import password_hash
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models import Branch, ChurchMembership, OrganizationAccessGrant, OrganizationUnit, User


def main():
    base = os.environ["VINYRD_PILOT_BASE_URL"].rstrip("/")
    url = make_url(settings.database_url)
    if (
        os.getenv("VINYRD_SMOKE_DISPOSABLE_DATABASE") != "1"
        or url.get_backend_name() != "postgresql"
        or url.host not in ("127.0.0.1", "localhost")
        or urlparse(base).hostname not in ("127.0.0.1", "localhost")
    ):
        raise RuntimeError("Requires explicitly disposable loopback PostgreSQL and HTTP.")
    password = uuid4().hex
    suffix = uuid4().hex[:10]
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).where(Branch.organization_unit_id.is_not(None)))
        unit = db.get(OrganizationUnit, branch.organization_unit_id)
        parent = db.get(OrganizationUnit, unit.parent_id)
        outsider = db.scalar(select(Branch).where(Branch.organization_unit_id.is_(None)))
        assert branch and parent and outsider
        users = {}
        for name in ("administrator", "pastor_leader", "accountant", "target"):
            user = User(
                name="Hierarchy smoke " + name,
                email=f"hierarchy-{name}-{suffix}@vinyrd.test",
                password_hash=password_hash(password),
            )
            db.add(user)
            db.flush()
            users[name] = user
            if name != "target":
                db.add(
                    OrganizationAccessGrant(
                        user_id=user.id,
                        organization_unit_id=parent.id,
                        permission_role=name,
                        scope_mode="descendants",
                    )
                )
        db.commit()
        emails = {key: u.email for key, u in users.items()}
        target = str(users["target"].id)
        church, other, node = str(branch.id), str(outsider.id), str(unit.id)
        memberships = db.scalar(select(func.count()).select_from(ChurchMembership))

    def request(path, token=None, *, method="GET", payload=None, branch_id=None, expected=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if branch_id:
            headers["X-Vinyrd-Branch-ID"] = branch_id
        req = Request(
            base + "/api/v1" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=20) as r:
                status, raw = r.status, r.read()
        except HTTPError as e:
            status, raw = e.code, e.read()
        assert status == expected, (path, status, raw.decode()[:300])
        return json.loads(raw) if raw else None

    tokens = {
        key: request("/auth/login", method="POST", payload={"email": email, "password": password})[
            "access_token"
        ]
        for key, email in emails.items()
    }
    admin = tokens["administrator"]
    tree = request("/organization-access/tree", admin)
    assert {b["id"] for b in tree["branches"]} == {church}
    request("/organization-access/context", admin, method="POST", payload={"branch_id": church})
    request("/members/", admin, branch_id=church)
    request("/members/", admin, branch_id=other, expected=403)
    request("/stewardship/", tokens["pastor_leader"], branch_id=church, expected=403)
    request("/members/", tokens["accountant"], branch_id=church, expected=403)
    request("/stewardship/", tokens["accountant"], branch_id=church)
    request("/staff/prayers", admin, branch_id=church, expected=403)
    grant = request(
        "/organization-access/grants",
        admin,
        method="POST",
        expected=201,
        payload={
            "user_id": target,
            "organization_unit_id": node,
            "permission_role": "administrator",
            "scope_mode": "unit_only",
        },
    )
    request("/members/", tokens["target"], branch_id=church)
    request(
        "/organization-access/grants/" + grant["id"],
        admin,
        method="PUT",
        payload={
            "permission_role": "administrator",
            "scope_mode": "unit_only",
            "status": "revoked",
        },
    )
    request("/members/", tokens["target"], branch_id=church, expected=403)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ChurchMembership)) == memberships
    print(
        json.dumps(
            {
                "status": "ok",
                "checks": [
                    "hierarchy-context",
                    "tenant-denial",
                    "pastor-no-finance",
                    "accountant-no-profiles",
                    "no-private-pastoral-expansion",
                    "grant-revocation",
                    "unchanged-memberships",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

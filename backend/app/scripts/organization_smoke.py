"""HTTP organization smoke for an explicitly disposable loopback PostgreSQL deployment.

Run after bootstrap and pilot_smoke, with database-owner credentials for fixture
creation. The HTTP server must separately run as the non-owner runtime role.
"""

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.security import password_hash
from app.core.settings import settings
from app.db.session import database_connect_args
from app.models import Branch, Role, User, UserRole


def main():
    base = os.environ["VINYRD_PILOT_BASE_URL"].rstrip("/")
    url = make_url(settings.database_url)
    if (
        os.getenv("VINYRD_SMOKE_DISPOSABLE_DATABASE") != "1"
        or url.get_backend_name() != "postgresql"
        or url.host not in ("localhost", "127.0.0.1")
        or urlparse(base).hostname not in ("localhost", "127.0.0.1")
    ):
        raise RuntimeError("Organization smoke requires explicit disposable loopback PostgreSQL.")
    owner = create_engine(
        settings.database_url, connect_args=database_connect_args(settings.database_url)
    )
    password = settings.bootstrap_admin_password
    suffix = uuid4().hex[:10]
    api = "/api/v1/network/admin/organization"
    checks = []

    def request(path, method="GET", token=None, payload=None, expected=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = Request(
            base + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=20) as response:
                status, raw = response.status, response.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        assert status == expected, (method, path, status, raw.decode()[:500])
        return json.loads(raw) if raw else None

    def login(email, secret=password):
        return request("/api/v1/auth/login", "POST", payload={"email": email, "password": secret})[
            "access_token"
        ]

    try:
        with Session(owner) as db:
            assert db.scalar(text("SHOW timezone")) == "UTC"
            other = Branch(name="Organization smoke B " + suffix)
            db.add(other)
            db.flush()
            other_admin = User(
                branch_id=other.id,
                name="Admin B",
                email=f"org-b-{suffix}@vinyrd.test",
                password_hash=password_hash(password),
            )
            db.add(other_admin)
            db.flush()
            role = db.scalar(select(Role).where(Role.name == "Administrator"))
            db.add(UserRole(user_id=other_admin.id, role_id=role.id))
            db.commit()
            other_email = other_admin.email
        admin = login(settings.bootstrap_admin_email)
        admin_b = login(other_email)
        assert request(api + "/setup", token=admin)["setup_status"] == "draft"
        church = request("/api/v1/admin/branch", token=admin)["branch"]["id"]
        checks.append("existing-unconfigured-church")
        preview = request(
            api + "/preview",
            "POST",
            admin,
            {"denomination": "TAG", "organization_level": "local_church"},
        )
        with owner.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM organization_units")) == 0
        checks.append("preview-no-writes")
        request(
            "/api/v1/network/admin/profile",
            "PUT",
            admin,
            {"name": "TAG Mikocheni", "country": "TZ", "denomination": "TAG", "is_published": True},
        )
        member_email = f"org-member-{suffix}@vinyrd.test"
        registered = request(
            "/api/v1/auth/register",
            "POST",
            payload={
                "first_name": "Organization",
                "last_name": "Member",
                "email": member_email,
                "password": password,
            },
            expected=201,
        )
        member = registered["access_token"]
        join = request(f"/api/v1/identity/churches/{church}/requests", "POST", member, {}, 201)
        request(
            f"/api/v1/identity/requests/{join['id']}/review", "POST", admin, {"status": "approved"}
        )
        request("/api/v1/network/me/initialize-home", "POST", member, {})
        request("/api/v1/member-portal/me", token=member)
        keys = ["national_church", "zone", "district", "section", "local_church"]
        names = [
            "Tanzania Assemblies of God",
            "Eastern",
            "Dar es Salaam",
            "Kinondoni",
            "TAG Mikocheni",
        ]
        payload = {
            "denomination": "TAG",
            "organization_level": "local_church",
            "template_version": preview["template_version"],
            "units": [
                {"level_key": key, "canonical_name": name, "country": "TZ", "is_published": True}
                for key, name in zip(keys, names, strict=True)
            ],
        }
        payload["units"][2]["localized_names"] = {"en": None, "sw": "Jimbo la Dar es Salaam"}
        config = request(api + "/confirm", "POST", admin, payload)
        assert request(api + "/confirm", "POST", admin, payload) == config
        assert [unit["level_key"] for unit in config["organization_path"]] == keys
        checks.extend(["tag-confirmation", "idempotent-confirmation"])
        public = request("/api/v1/network/churches/" + church)
        assert len(public["organization_path"]) == 5
        assert all(
            set(unit) == {"level_key", "name", "labels", "presentation"}
            for unit in public["organization_path"]
        )
        checks.append("public-ancestry-allowlist")
        member = login(member_email)
        request("/api/v1/member-portal/me", token=member)
        memberships = request("/api/v1/identity/memberships", token=member)
        assert len(memberships) == 1 and memberships[0]["church_id"] == church
        request("/api/v1/admin/branch", token=login(settings.bootstrap_admin_email))
        checks.append("member-and-staff-access-no-ancestor-memberships")
        staff = request(api + "/assignments", token=admin)["staff"]
        pastor = next(user for user in staff if user["name"] == "Vinyrd Pilot Pastor")
        with owner.connect() as conn:
            pastor_email = conn.scalar(
                text("SELECT email FROM users WHERE id=:id"), {"id": UUID(pastor["id"])}
            )
            grants = conn.scalar(
                text("SELECT count(*) FROM user_roles WHERE user_id=:id"),
                {"id": UUID(pastor["id"])},
            )
        assignment = {
            "organization_unit_id": config["local_unit_id"],
            "user_id": pastor["id"],
            "position_key": config["hierarchy_snapshot"]["levels"][-1]["positions"][0]["key"],
            "permission_role": "administrator",
        }
        request(api + "/assignments", "PUT", admin, assignment)
        pastor_token = login(pastor_email, os.environ["VINYRD_PILOT_PASTOR_PASSWORD"])
        request(api + "/setup", token=pastor_token, expected=403)
        request("/api/v1/admin/users", token=pastor_token, expected=403)
        with owner.connect() as conn:
            assert (
                conn.scalar(
                    text("SELECT count(*) FROM user_roles WHERE user_id=:id"),
                    {"id": UUID(pastor["id"])},
                )
                == grants
            )
        checks.append("assignment-does-not-elevate-permission")
        assert request(api + "/setup", token=admin_b)["setup_status"] == "draft"
        assert request(api + "/assignments", token=admin_b)["items"] == []
        request(api + "/assignments", "PUT", admin_b, assignment, 403)
        request(api + "/setup", token=member, expected=403)
        request(api + "/confirm", "POST", admin_b, {**payload, "branch_id": church}, 422)
        checks.append("tenant-isolation")
        with owner.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM organization_units")) == 5
            assert conn.scalar(text("SELECT count(*) FROM church_organization_configurations")) == 1
            assert conn.scalar(text("SELECT count(*) FROM organization_office_assignments")) == 1
        print(json.dumps({"status": "ok", "checks": checks}, indent=2))
    finally:
        owner.dispose()


if __name__ == "__main__":
    main()

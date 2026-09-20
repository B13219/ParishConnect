from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


BASE_URL = os.environ.get("VINYRD_PILOT_BASE_URL", "http://127.0.0.1:8003").rstrip("/")
ADMIN_EMAIL = os.environ["PARISHCONNECT_BOOTSTRAP_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD"]
PASTOR_PASSWORD = os.environ.get(
    "VINYRD_PILOT_PASTOR_PASSWORD",
    "Vinyrd-Pilot-Pastor-Change-2026!",
)


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> object:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            content = response.read().decode()
            return json.loads(content) if content else {}
    except HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc


def login(email: str, password: str) -> str:
    response = request(
        "POST",
        "/api/v1/auth/login",
        payload={"email": email, "password": password},
    )
    assert isinstance(response, dict)
    return str(response["access_token"])


def main() -> int:
    run_id = uuid4().hex[:8]
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)

    pastor_email = f"pilot-pastor-{run_id}@vinyrd.test"
    request(
        "POST",
        "/api/v1/admin/users",
        token=admin_token,
        payload={
            "name": "Vinyrd Pilot Pastor",
            "email": pastor_email,
            "password": PASTOR_PASSWORD,
            "role": "pastor_leader",
            "status": "active",
        },
    )
    pastor_token = login(pastor_email, PASTOR_PASSWORD)

    member_email = f"pilot-member-{run_id}@vinyrd.test"
    member = request(
        "POST",
        "/api/v1/members/",
        token=admin_token,
        payload={
            "first_name": "Pilot",
            "last_name": "Member",
            "phone": f"+255700{run_id[:6]}",
            "email": member_email,
            "membership_status": "active",
            "preferred_language": "en",
        },
    )
    assert isinstance(member, dict)
    member_id = str(member["id"])

    request(
        "PUT",
        "/api/v1/admin/branch/geofence",
        token=admin_token,
        payload={
            "geofence_enabled": True,
            "setup_method": "manual",
            "latitude": -6.7924,
            "longitude": 39.2083,
            "attendance_radius_meters": 150,
        },
    )

    now = datetime.now(UTC)
    event = request(
        "POST",
        "/api/v1/attendance/events",
        token=admin_token,
        payload={
            "name": f"Pilot Service {run_id}",
            "event_type": "service",
            "starts_at": (now - timedelta(minutes=5)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "location": "Vinyrd Pilot Sanctuary",
            "qr_opens_at": (now - timedelta(minutes=15)).isoformat(),
            "qr_closes_at": (now + timedelta(hours=1)).isoformat(),
            "qr_rotation_seconds": 60,
        },
    )
    assert isinstance(event, dict)
    event_id = str(event["id"])
    request(
        "POST",
        f"/api/v1/attendance/events/{event_id}/open",
        token=admin_token,
    )

    access = request(
        "POST",
        f"/api/v1/staff/member-access/{member_id}",
        token=admin_token,
        payload={"email": member_email},
    )
    assert isinstance(access, dict)
    temporary_password = str(access["temporary_password"])
    member_token = login(member_email, temporary_password)

    check_in = request(
        "POST",
        f"/api/v1/member-portal/events/{event_id}/check-in/location",
        token=member_token,
        payload={
            "latitude": -6.7924,
            "longitude": 39.2083,
            "accuracy_meters": 10,
        },
    )
    assert isinstance(check_in, dict)
    assert check_in["inside_geofence"] is True

    giving = request(
        "POST",
        "/api/v1/member-portal/giving",
        token=member_token,
        payload={
            "contribution_type": "offering",
            "amount": "10000",
            "currency": "TZS",
            "payment_method": "mobile_money",
            "reference_code": f"PILOT-{run_id}",
            "notes": "Vinyrd pilot end-to-end verification",
        },
    )
    assert isinstance(giving, dict)
    assert Decimal(str(giving["amount"])) == Decimal("10000")

    prayer = request(
        "POST",
        "/api/v1/member-portal/prayers",
        token=member_token,
        payload={
            "category": "guidance",
            "body": "Please pray for wisdom during the Vinyrd pilot.",
            "visibility": "pastoral_team",
            "allow_contact": True,
        },
    )
    assert isinstance(prayer, dict)
    prayer_id = str(prayer["id"])

    followed_up = request(
        "PATCH",
        f"/api/v1/staff/prayers/{prayer_id}",
        token=pastor_token,
        payload={
            "status": "answered",
            "pastoral_notes": "Pilot prayer reviewed and followed up.",
            "assign_to_me": True,
        },
    )
    assert isinstance(followed_up, dict)
    assert followed_up["status"] == "answered"

    sermon_title = f"Remain in the Vine · {run_id}"
    sermon = request(
        "PUT",
        f"/api/v1/staff/sermons/{event_id}",
        token=pastor_token,
        payload={
            "title": sermon_title,
            "speaker": "Vinyrd Pilot Pastor",
            "scripture_reference": "John 15:1-8",
            "summary": "Remain connected to Christ and bear lasting fruit.",
            "published": True,
        },
    )
    assert isinstance(sermon, dict)
    assert sermon["published"] is True

    published = request(
        "GET",
        "/api/v1/member-portal/sermons",
        token=member_token,
    )
    assert isinstance(published, list)
    assert any(item["title"] == sermon_title for item in published)

    home = request("GET", "/api/v1/member-portal/me", token=member_token)
    assert isinstance(home, dict)
    assert home["profile"]["id"] == member_id

    manifest = request(
        "POST",
        "/api/v1/admin/backup-manifest",
        token=admin_token,
    )
    assert isinstance(manifest, dict)
    assert manifest["kind"] == "backup_manifest"

    print(
        json.dumps(
            {
                "status": "ok",
                "member_id": member_id,
                "event_id": event_id,
                "prayer_id": prayer_id,
                "sermon": sermon_title,
                "backup_manifest": "verified",
                "checked_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
    )
    time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

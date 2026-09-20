from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.settings import settings


@dataclass(frozen=True)
class DeploymentIssue:
    code: str
    severity: str
    message: str


SECRET_FIELDS = ("auth_token_secret", "qr_token_secret", "password_salt")
DEMO_MARKERS = ("local-demo", "change-before-production", "change-me")


def _value(config: Mapping[str, Any], key: str) -> str:
    return str(config.get(key, "") or "")


def settings_snapshot() -> dict[str, Any]:
    return {
        "environment": settings.environment,
        "cors_origins": settings.cors_origins,
        "public_base_url": settings.public_base_url,
        "database_url": settings.database_url,
        "auth_token_secret": settings.auth_token_secret,
        "qr_token_secret": settings.qr_token_secret,
        "password_salt": settings.password_salt,
        "access_token_minutes": settings.access_token_minutes,
        "demo_password": settings.demo_password,
    }


def readiness_issues(config: Mapping[str, Any]) -> list[DeploymentIssue]:
    issues: list[DeploymentIssue] = []
    environment = _value(config, "environment").lower()
    database_url = _value(config, "database_url").lower()
    cors_origins = _value(config, "cors_origins").lower()
    public_base_url = _value(config, "public_base_url").lower()

    if environment in {"local", "development", "dev", ""}:
        issues.append(
            DeploymentIssue(
                code="environment-local",
                severity="info",
                message=(
                    "Environment is local/demo; set PARISHCONNECT_ENVIRONMENT=production "
                    "for a live deployment."
                ),
            )
        )

    if database_url.startswith("sqlite"):
        issues.append(
            DeploymentIssue(
                code="database-sqlite",
                severity="high",
                message="SQLite is for presentation demos only; production should use PostgreSQL.",
            )
        )
    if "parishconnect:parishconnect@" in database_url or "@localhost" in database_url:
        issues.append(
            DeploymentIssue(
                code="database-demo-connection",
                severity="warning",
                message="Database URL appears to use local demo credentials or localhost.",
            )
        )

    configured_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    if "*" in configured_origins:
        issues.append(
            DeploymentIssue(
                code="cors-wildcard",
                severity="high",
                message="Wildcard CORS is not appropriate for production.",
            )
        )
    if environment == "production" and (
        "localhost" in cors_origins or "127.0.0.1" in cors_origins
    ):
        issues.append(
            DeploymentIssue(
                code="cors-localhost-production",
                severity="high",
                message="Production CORS origins must not contain localhost.",
            )
        )

    if environment == "production":
        if not public_base_url.startswith("https://"):
            issues.append(
                DeploymentIssue(
                    code="public-base-url-not-https",
                    severity="high",
                    message="Production PARISHCONNECT_PUBLIC_BASE_URL must use HTTPS.",
                )
            )

    for field in SECRET_FIELDS:
        secret = _value(config, field)
        if len(secret) < 32 or any(marker in secret.lower() for marker in DEMO_MARKERS):
            issues.append(
                DeploymentIssue(
                    code=f"{field}-weak",
                    severity="high",
                    message=f"{field} must be replaced with a long, unique production value.",
                )
            )

    if _value(config, "demo_password") == "parishconnect":
        issues.append(
            DeploymentIssue(
                code="demo-password-default",
                severity="warning",
                message="Default demo password is still active; disable it before launch.",
            )
        )

    access_token_minutes = int(config.get("access_token_minutes", 0) or 0)
    if access_token_minutes > 240:
        issues.append(
            DeploymentIssue(
                code="access-token-long",
                severity="warning",
                message="Production access tokens should be 240 minutes or shorter.",
            )
        )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Vinyrd deployment readiness.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when any readiness issue is found.",
    )
    args = parser.parse_args()

    issues = readiness_issues(settings_snapshot())
    if not issues:
        print("Vinyrd deployment readiness: no issues found.")
        return 0

    print("Vinyrd deployment readiness:")
    for issue in issues:
        print(f"- [{issue.severity.upper()}] {issue.code}: {issue.message}")

    if args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from app.scripts.check_deployment_readiness import readiness_issues


def issue_codes(config: dict[str, object]) -> set[str]:
    return {issue.code for issue in readiness_issues(config)}


def test_readiness_flags_demo_defaults() -> None:
    codes = issue_codes(
        {
            "environment": "local",
            "cors_origins": "http://127.0.0.1:5173,http://localhost:5173",
            "database_url": "postgresql+psycopg://parishconnect:parishconnect@localhost:5432/parishconnect",
            "auth_token_secret": "local-demo-auth-secret-change-before-production",
            "qr_token_secret": "local-demo-qr-secret-change-before-production",
            "password_salt": "local-demo-password-salt-change-before-production",
            "access_token_minutes": 720,
            "demo_password": "parishconnect",
        }
    )

    assert "environment-local" in codes
    assert "database-demo-connection" in codes
    assert "auth_token_secret-weak" in codes
    assert "qr_token_secret-weak" in codes
    assert "password_salt-weak" in codes
    assert "demo-password-default" in codes


def test_readiness_accepts_hardened_settings() -> None:
    codes = issue_codes(
        {
            "environment": "production",
            "cors_origins": "https://admin.parishconnect.example",
            "database_url": "postgresql+psycopg://pc_live:strong-password@db.internal:5432/parishconnect",
            "auth_token_secret": "auth-secret-value-with-more-than-thirty-two-characters",
            "qr_token_secret": "qr-secret-value-with-more-than-thirty-two-characters",
            "password_salt": "password-salt-value-with-more-than-thirty-two-characters",
            "access_token_minutes": 120,
            "demo_password": "disabled-after-real-users-are-created",
        }
    )

    assert codes == set()

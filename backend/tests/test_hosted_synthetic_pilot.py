"""Synthetic pilot boot guard and operator credential isolation regression tests."""

import pytest

from app.scripts.hosted_synthetic_pilot import validate_target, worker_env


def environment():
    def conn(role):
        return f"postgresql+psycopg://{role}:test@ep-example.eu-central-1.aws.neon.tech/vinyrd_pilot?sslmode=require"
    return {
        "VINYRD_SYNTHETIC_PILOT": "1",
        "PARISHCONNECT_ENVIRONMENT": "staging",
        "PARISHCONNECT_DATABASE_URL": conn("vinyrd_runtime"),
        "PARISHCONNECT_MIGRATION_DATABASE_URL": conn("vinyrd_owner"),
        "PARISHCONNECT_BACKUP_DATABASE_URL": conn("vinyrd_owner"),
        "PARISHCONNECT_RESTORE_DATABASE_URL": conn("vinyrd_owner"),
        "PARISHCONNECT_SMS_MODE": "simulate",
        "PARISHCONNECT_DEMO_PASSWORD": "disabled",
        "PARISHCONNECT_AUTH_TOKEN_SECRET": "x" * 50,
        "PARISHCONNECT_QR_TOKEN_SECRET": "y" * 50,
        "PARISHCONNECT_PASSWORD_SALT": "z" * 50,
        "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD": "a" * 40,
        "VINYRD_PILOT_PASTOR_PASSWORD": "b" * 40,
        "PARISHCONNECT_BOOTSTRAP_ADMIN_EMAIL": "pilot-admin@vinyrd.test",
        "PARISHCONNECT_PUBLIC_BASE_URL": "https://vinyrd-pilot-synthetic.onrender.com",
    }


def test_synthetic_guard_accepts_only_isolated_staging():
    validate_target(environment())


@pytest.mark.parametrize("key,value", [
    ("VINYRD_SYNTHETIC_PILOT", "0"),
    ("PARISHCONNECT_ENVIRONMENT", "production"),
    ("PARISHCONNECT_SMS_MODE", "live"),
    ("PARISHCONNECT_DEMO_PASSWORD", "parishconnect"),
    ("PARISHCONNECT_AUTH_TOKEN_SECRET", "short"),
    ("PARISHCONNECT_BOOTSTRAP_ADMIN_EMAIL", "real-person@example.com"),
    ("PARISHCONNECT_PUBLIC_BASE_URL", "http://example.com"),
    ("PARISHCONNECT_DATABASE_URL", "postgresql+psycopg://vinyrd_runtime:test@other.invalid/vinyrd_pilot"),
    ("PARISHCONNECT_MIGRATION_DATABASE_URL", "postgresql+psycopg://vinyrd_owner:test@ep-example.eu-central-1.aws.neon.tech/otherdb"),
])
def test_synthetic_guard_rejects_unsafe_configs(key, value):
    env = environment()
    env[key] = value
    with pytest.raises(RuntimeError):
        validate_target(env)


def test_synthetic_worker_drops_operator_and_acceptance_secrets():
    env = environment()
    clean = worker_env(env)
    for key in (
        "PARISHCONNECT_MIGRATION_DATABASE_URL",
        "PARISHCONNECT_BACKUP_DATABASE_URL",
        "PARISHCONNECT_RESTORE_DATABASE_URL",
        "PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD",
        "VINYRD_PILOT_PASTOR_PASSWORD",
        "VINYRD_SYNTHETIC_PILOT",
    ):
        assert key not in clean
    assert clean["PARISHCONNECT_DATABASE_URL"] == env["PARISHCONNECT_DATABASE_URL"]
    assert clean["PGTZ"] == "UTC"



def test_synthetic_guard_reports_missing_credentials_without_values():
    env = environment()
    del env["PARISHCONNECT_DATABASE_URL"]
    with pytest.raises(RuntimeError, match="PARISHCONNECT_DATABASE_URL"):
        validate_target(env)

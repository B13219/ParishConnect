"""One-time guarded staging initialization, acceptance smoke and verified restore.

This entrypoint is ONLY for the empty, synthetic Vinyrd pilot Neon project.
Do not attach it to production or to a database containing real church records.
Operational DB credentials are cleared before the long-running HTTP worker starts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.db.session import database_connect_args
from app.scripts.start_backend import runtime_environment
from app.services.database_privileges import provision

TARGET_DATABASE = "vinyrd_pilot"
TARGET_ENVIRONMENT = "staging"
MIN_SECRET_LENGTH = 32


def validate_target(env: dict[str, str]) -> None:
    if env.get("VINYRD_SYNTHETIC_PILOT") != "1":
        raise RuntimeError("Synthetic-only pilot guard must be explicitly enabled.")
    if env.get("PARISHCONNECT_ENVIRONMENT") != TARGET_ENVIRONMENT:
        raise RuntimeError("Synthetic pilot requires staging, never production.")
    runtime = make_url(env["PARISHCONNECT_DATABASE_URL"])
    owner = make_url(env["PARISHCONNECT_MIGRATION_DATABASE_URL"])
    backup = make_url(env["PARISHCONNECT_BACKUP_DATABASE_URL"])
    restore = make_url(env["PARISHCONNECT_RESTORE_DATABASE_URL"])
    if any(url.get_backend_name() != "postgresql" for url in (runtime, owner, backup, restore)):
        raise RuntimeError("Pilot database URLs must use PostgreSQL.")
    if any(url.database != TARGET_DATABASE for url in (runtime, owner, backup, restore)):
        raise RuntimeError("Pilot is restricted to the dedicated vinyrd_pilot database.")
    if any(not url.host or not url.host.endswith(".neon.tech") for url in (runtime, owner, backup, restore)):
        raise RuntimeError("Pilot requires a dedicated Neon PostgreSQL host.")
    if len({(url.host, url.port) for url in (runtime, owner, backup, restore)}) != 1:
        raise RuntimeError("All pilot connections must use the same Neon direct endpoint.")
    if runtime.username == owner.username:
        raise RuntimeError("Migration owner and runtime must have different role identities.")
    if runtime.username != "vinyrd_runtime" or owner.username != "vinyrd_owner":
        raise RuntimeError("Unexpected database role for isolated pilot.")
    if env.get("PARISHCONNECT_SMS_MODE") != "simulate":
        raise RuntimeError("Synthetic pilot must not send real SMS.")
    if env.get("PARISHCONNECT_DEMO_PASSWORD") == "parishconnect":
        raise RuntimeError("Demo password cannot remain at its default.")
    for secret in ("PARISHCONNECT_AUTH_TOKEN_SECRET", "PARISHCONNECT_QR_TOKEN_SECRET",
                   "PARISHCONNECT_PASSWORD_SALT"):
        if len(env.get(secret, "")) < MIN_SECRET_LENGTH:
            raise RuntimeError(f"Missing or weak secret: {secret}")
    if len(env.get("PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD", "")) < 20:
        raise RuntimeError("A distinct strong synthetic administrator password is required.")
    if len(env.get("VINYRD_PILOT_PASTOR_PASSWORD", "")) < 20:
        raise RuntimeError("A distinct strong synthetic pastor password is required.")
    if not env.get("PARISHCONNECT_PUBLIC_BASE_URL", "").startswith("https://"):
        raise RuntimeError("Public staging URL must use HTTPS.")
    if env.get("PARISHCONNECT_BOOTSTRAP_ADMIN_EMAIL") != "pilot-admin@vinyrd.test":
        raise RuntimeError("Only the synthetic validation administrator is permitted.")


def run_module(module: str, env: dict[str, str], *args: str) -> None:
    subprocess.run([sys.executable, "-m", module, *args], env=env, check=True)


def worker_env(source: dict[str, str]) -> dict[str, str]:
    result = runtime_environment(source)
    for key in ("VINYRD_PILOT_PASTOR_PASSWORD", "VINYRD_SYNTHETIC_PILOT"):
        result.pop(key, None)
    result["PGTZ"] = "UTC"
    return result


def wait_for_health(port: int, proc: subprocess.Popen) -> None:
    for _ in range(180):
        if proc.poll() is not None:
            raise RuntimeError("Staging worker exited before health readiness.")
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise RuntimeError("Staging worker did not become healthy.")


def main() -> None:
    source = dict(os.environ)
    validate_target(source)
    owner_env = dict(source)
    owner_env["PARISHCONNECT_DATABASE_URL"] = source["PARISHCONNECT_MIGRATION_DATABASE_URL"]
    owner_env["PGTZ"] = "UTC"

    # The database starts empty; migrations and bootstrap are idempotent.
    run_module("alembic", owner_env, "upgrade", "head")
    run_module("app.scripts.bootstrap_admin", owner_env)
    engine = create_engine(owner_env["PARISHCONNECT_DATABASE_URL"],
                           connect_args=database_connect_args(owner_env["PARISHCONNECT_DATABASE_URL"]))
    try:
        with engine.begin() as connection:
            provision(connection, "vinyrd_runtime")
    finally:
        engine.dispose()

    clean = worker_env(source)
    run_module("app.scripts.check_deployment_readiness", clean, "--strict", "--check-database")
    port = int(clean.get("PORT", "10000"))
    process = subprocess.Popen([sys.executable, "-m", "app.scripts.start_backend"], env=clean)
    try:
        wait_for_health(port, process)
        acceptance = dict(source)
        acceptance["VINYRD_PILOT_BASE_URL"] = f"http://127.0.0.1:{port}"
        acceptance["PGTZ"] = "UTC"
        run_module("app.scripts.pilot_smoke", acceptance)
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    # Validate *after* synthetic journeys so restored row counts are nonzero.
    run_module("app.scripts.verify_backup_restore", source,
               "--backup-path", "/tmp/vinyrd-synthetic-pilot-verified.dump")
    print("VINYRD_SYNTHETIC_PILOT_ACCEPTANCE_PASS: migrations, RLS runtime, synthetic HTTP flows, and restored startup.", flush=True)
    # Clear all owner, backup, restore and test credentials from the worker process.
    os.execve(sys.executable, [sys.executable, "-m", "app.scripts.start_backend"], clean)


if __name__ == "__main__":
    main()

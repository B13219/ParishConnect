"""Guard the pilot backup/restore toolchain against mismatched PostgreSQL majors."""

import pytest

from app.scripts import verify_backup_restore as verifier


def test_postgres_client_major_parses_packaged_version(monkeypatch):
    monkeypatch.setattr(
        verifier.subprocess,
        "check_output",
        lambda args, **kwargs: "pg_dump (PostgreSQL) 18.1 (Debian 18.1-1.pgdg13+1)\n",
    )
    assert verifier.postgres_client_major("pg_dump") == 18


def test_postgres_client_major_fails_closed_on_unknown_version(monkeypatch):
    monkeypatch.setattr(verifier.subprocess, "check_output", lambda args, **kwargs: "unknown")
    with pytest.raises(RuntimeError, match="Cannot determine"):
        verifier.postgres_client_major("pg_dump")


def test_postgres_toolchain_rejects_different_server_majors(monkeypatch):
    monkeypatch.setattr(
        verifier,
        "postgres_server_major",
        lambda url: 18 if url == "source" else 16,
    )
    with pytest.raises(RuntimeError, match="must match"):
        verifier.verify_postgres_toolchain("source", "restore")


def test_postgres_toolchain_rejects_old_client(monkeypatch):
    monkeypatch.setattr(verifier, "postgres_server_major", lambda url: 18)
    monkeypatch.setattr(
        verifier,
        "postgres_client_major",
        lambda executable: 16 if executable == "pg_dump" else 18,
    )
    with pytest.raises(RuntimeError, match="pg_dump uses PostgreSQL 16"):
        verifier.verify_postgres_toolchain("source", "restore")


def test_postgres_toolchain_accepts_all_matching_tools(monkeypatch):
    observed = []
    monkeypatch.setattr(verifier, "postgres_server_major", lambda url: 18)
    monkeypatch.setattr(
        verifier,
        "postgres_client_major",
        lambda executable: observed.append(executable) or 18,
    )
    verifier.verify_postgres_toolchain("source", "restore")
    assert observed == ["pg_dump", "pg_restore", "createdb", "dropdb"]

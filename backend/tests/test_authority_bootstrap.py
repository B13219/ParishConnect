"""Operator-only initialization/recovery against real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.models import (
    AuditLog,
    Branch,
    ChurchMembership,
    ChurchOrganizationConfiguration,
    OrganizationAccessGrant,
    OrganizationOfficeAssignment,
    OrganizationUnit,
    Role,
    User,
    UserRole,
)
from app.services.authority_bootstrap import bootstrap_authority

pytest_plugins = ["tests.test_identity_postgres"]


@pytest.fixture
def authority(postgres_identity):
    owner, runtime, _ = postgres_identity
    sessions = sessionmaker(bind=owner)
    suffix = uuid4().hex
    with sessions() as db:
        branch = Branch(name="Authority " + suffix)
        db.add(branch)
        db.flush()
        root = OrganizationUnit(
            denomination="Assemblies of God",
            level_key="national",
            canonical_name="Verified tree",
            normalized_name="verified",
            match_key=suffix,
            owner_branch_id=branch.id,
        )
        db.add(root)
        db.flush()
        local = OrganizationUnit(
            denomination=root.denomination,
            level_key="local_church",
            canonical_name="Verified church",
            normalized_name="local",
            match_key=suffix + "l",
            owner_branch_id=branch.id,
            parent_id=root.id,
        )
        db.add(local)
        db.flush()
        branch.organization_unit_id = local.id
        actors = []
        role = db.scalar(select(Role).where(Role.name == "Administrator"))
        for index in range(2):
            user = User(
                branch_id=branch.id,
                name="Verified admin",
                email=f"authority-{suffix}-{index}@test.local",
                password_hash="not-used-for-http",
            )
            db.add(user)
            db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id))
            actors.append(user.id)
        db.add(
            ChurchOrganizationConfiguration(
                branch_id=branch.id,
                denomination=root.denomination,
                local_unit_id=local.id,
                setup_status="configured",
                configured_by=actors[0],
                confirmation_fingerprint=suffix,
                terminology_snapshot={},
                hierarchy_snapshot={},
            )
        )
        db.commit()
        yield_data = {
            "root_id": root.id,
            "actor_id": actors[0],
            "target_id": actors[0],
            "reason": "verified-ticket-" + suffix,
            "enabled": True,
        }
        secondary = actors[1]
    return sessions, runtime, yield_data, secondary


def test_guard_disabled_and_runtime_connection_denied(authority):
    sessions, runtime, args, _ = authority
    with sessions() as db, pytest.raises(ValueError, match="disabled"):
        bootstrap_authority(db, **{**args, "enabled": False})
    with sessionmaker(bind=runtime)() as db, pytest.raises(ValueError, match="migration-owner"):
        bootstrap_authority(db, **args)


def test_initial_authority_idempotency_and_preservation(authority):
    sessions, _, args, other = authority
    with sessions() as db:
        members = db.scalar(select(func.count()).select_from(ChurchMembership))
        offices = db.scalar(select(func.count()).select_from(OrganizationOfficeAssignment))
        grant, created = bootstrap_authority(db, **args)
        assert created
        grant_id = grant.id
        db.commit()
    with sessions() as db:
        grant, created = bootstrap_authority(db, **args)
        assert not created and grant.id == grant_id
        assert db.scalar(select(func.count()).select_from(ChurchMembership)) == members
        assert db.scalar(select(func.count()).select_from(OrganizationOfficeAssignment)) == offices
        assert (
            db.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == grant_id)
            )
            == 1
        )
    with sessions() as db, pytest.raises(ValueError, match="history"):
        bootstrap_authority(
            db, **{**args, "target_id": other, "reason": "different-approved-ticket"}
        )


def test_unrelated_root_and_nonadmin_denied(authority):
    sessions, _, args, _ = authority
    with sessions() as db:
        root = db.get(OrganizationUnit, args["root_id"])
        unrelated = OrganizationUnit(
            denomination=root.denomination,
            level_key="national",
            canonical_name="Other",
            normalized_name="other",
            match_key=uuid4().hex,
            owner_branch_id=root.owner_branch_id,
        )
        db.add(unrelated)
        db.commit()
        unrelated_id = unrelated.id
    with sessions() as db, pytest.raises(ValueError, match="outside"):
        bootstrap_authority(db, **{**args, "root_id": unrelated_id})
    with sessions() as db:
        db.query(UserRole).filter(UserRole.user_id == args["actor_id"]).delete()
        db.commit()
    with sessions() as db, pytest.raises(ValueError, match="Administrator"):
        bootstrap_authority(db, **args)


def test_revocation_requires_explicit_recovery(authority):
    sessions, _, args, other = authority
    with sessions() as db:
        grant, _ = bootstrap_authority(db, **args)
        db.commit()
        grant_id = grant.id
    with sessions() as db:
        db.get(OrganizationAccessGrant, grant_id).status = "revoked"
        db.commit()
    with sessions() as db, pytest.raises(ValueError, match="recovery"):
        bootstrap_authority(db, **args)
    with sessions() as db, pytest.raises(ValueError, match="disabled"):
        bootstrap_authority(db, **{**args, "enabled": False}, recovery=True)
    with sessions() as db:
        grant, created = bootstrap_authority(
            db, **{**args, "target_id": other, "reason": "recovery-ticket"}, recovery=True
        )
        assert created and grant.status == "active"
        db.commit()
    with sessions() as db, pytest.raises(ValueError, match="Active root authority"):
        bootstrap_authority(db, **{**args, "reason": "another-recovery"}, recovery=True)


def test_concurrent_initialization_is_idempotent(authority):
    sessions, _, args, _ = authority

    def run(_):
        with sessions() as db:
            grant, created = bootstrap_authority(db, **args)
            db.commit()
            return grant.id, created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results[0][0] == results[1][0]
    assert sorted(r[1] for r in results) == [False, True]


def test_contained_delegation_after_bootstrap(authority):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.db.session import get_db
    from app.main import create_app

    sessions, runtime, args, other = authority
    with sessions() as db:
        bootstrap_authority(db, **args)
        db.commit()
        actor = db.get(User, args["actor_id"])
        token = create_access_token(actor, db)
        local = db.get(Branch, actor.branch_id).organization_unit_id
    app = create_app()

    def database():
        with sessionmaker(bind=runtime, autoflush=False)() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + token}
        response = client.post(
            "/api/v1/organization-access/grants",
            headers=headers,
            json={
                "user_id": str(other),
                "organization_unit_id": str(local),
                "permission_role": "accountant",
                "scope_mode": "unit_only",
            },
        )
        assert response.status_code == 201, response.text
        response = client.post(
            "/api/v1/organization-access/grants",
            headers=headers,
            json={
                "user_id": str(args["actor_id"]),
                "organization_unit_id": str(args["root_id"]),
                "permission_role": "administrator",
                "scope_mode": "descendants",
            },
        )
        assert response.status_code == 403

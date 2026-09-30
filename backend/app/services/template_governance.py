"""Local, explicit, transactional governance. Never denomination-wide authority."""

import json
from copy import deepcopy
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text

from app.models import AuditLog, Branch, ChurchOrganizationConfiguration, OrganizationUnit
from app.services import template_registry
from app.services.audit import write_audit_log
from app.services.organizations import ancestry, fingerprint
from app.services.terminology import Terminology, runtime_levels

ACTION = "organization.template_approved"


class Override(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    level_key: str = Field(min_length=1, max_length=80)
    position_key: str | None = Field(default=None, min_length=1, max_length=120)
    labels: dict[Literal["en", "sw"], str | None]

    @field_validator("labels")
    @classmethod
    def labels_valid(cls, labels):
        if not labels or any(
            v is not None and (not v.strip() or len(v) > 200 or any(ord(c) < 32 for c in v))
            for v in labels.values()
        ):
            raise ValueError("Supply nonblank labels up to 200 characters, or null to reset.")
        return {k: v.strip() if v is not None else None for k, v in labels.items()}


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_version: int | None = Field(default=None, ge=1, strict=True)
    overrides: list[Override] = Field(default_factory=list, max_length=100)


class ApprovalInput(ReviewInput):
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    preview_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: UUID


def installed(db, branch_id, lock=False):
    query = select(ChurchOrganizationConfiguration).where(
        ChurchOrganizationConfiguration.branch_id == branch_id
    )
    config = db.scalar(query.with_for_update() if lock else query)
    if config is None:
        raise HTTPException(409, "Organization configuration is required.")
    return config


def snapshot(config):
    return deepcopy(
        {
            "template_version": config.template_version,
            "hierarchy_snapshot": config.hierarchy_snapshot,
            "terminology_snapshot": config.terminology_snapshot,
        }
    )


def revision(config):
    return fingerprint(snapshot(config))


def records(db, branch_id):
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.branch_id == branch_id, AuditLog.action == ACTION)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        )
    )


def history(db, branch_id):
    return [
        {
            "id": row.id,
            "approved_by": row.actor_user_id,
            "approved_at": row.created_at,
            **json.loads(row.metadata_json),
        }
        for row in records(db, branch_id)
    ]


def status(db, branch_id):
    config = installed(db, branch_id)
    available = template_registry.versions(config.denomination)
    latest = max(available) if available else None
    result = {
        "denomination": config.denomination,
        "installed_version": config.template_version,
        "available_version": latest,
        "versions": available,
        "revision": revision(config),
        "upgrade_available": bool(
            latest and config.template_version and latest > config.template_version
        ),
        "compatibility_status": "requires_configuration" if not config.local_unit_id else "current",
        "publication_authority": "local_configuration_only",
        "runtime_levels": runtime_levels(Terminology(config)),
        "overrides": deepcopy(config.hierarchy_snapshot.get("governance", {}).get("overrides", {})),
    }
    if result["upgrade_available"]:
        result["compatibility_status"] = preview(db, config, ReviewInput(target_version=latest))[
            "compatibility_status"
        ]
    return result


def local_leaf(db, unit, branch_id):
    branch = db.get(Branch, branch_id)
    if (
        unit.owner_branch_id != branch_id
        or unit.status != "active"
        or branch is None
        or branch.organization_unit_id != unit.id
    ):
        return False
    if db.bind.dialect.name == "postgresql":
        return db.scalar(text("SELECT vinyrd_org_labels_local(:id)"), {"id": unit.id})
    return (
        db.scalar(select(OrganizationUnit.id).where(OrganizationUnit.parent_id == unit.id).limit(1))
        is None
        and db.scalar(
            select(Branch.id)
            .where(Branch.organization_unit_id == unit.id, Branch.id != branch_id)
            .limit(1)
        )
        is None
        and db.scalar(
            select(ChurchOrganizationConfiguration.branch_id)
            .where(
                ChurchOrganizationConfiguration.local_unit_id == unit.id,
                ChurchOrganizationConfiguration.branch_id != branch_id,
            )
            .limit(1)
        )
        is None
    )


def differences(before, after, kind):
    old, new = {x["key"]: x for x in before}, {x["key"]: x for x in after}
    rows = []
    for key in dict.fromkeys([*old, *new]):
        a, b = old.get(key), new.get(key)
        state = (
            "added"
            if a is None
            else "removed"
            if b is None
            else "unchanged"
            if a == b
            else "renamed"
        )
        structural = bool(a and b and a.get("optional") != b.get("optional"))
        rows.append(
            {
                "key": key,
                "kind": kind,
                "status": "requires_review" if structural else state,
                "current": a,
                "proposed": b,
                "canonical_identifier_changed": a is None or b is None,
                "structural_change": structural,
            }
        )
    return rows


def preview(db, config, payload):
    if not config.local_unit_id or not config.hierarchy_snapshot.get("levels"):
        raise HTTPException(
            409, "Custom hierarchy requires_configuration; no built-in structure assigned."
        )
    target_version = (
        payload.target_version if payload.target_version is not None else config.template_version
    )
    if config.template_version and target_version and target_version < config.template_version:
        raise HTTPException(409, "Template downgrades require a separate reviewed workflow.")
    if target_version is not None:
        released = template_registry.template(config.denomination, target_version)
    else:
        released = {
            "levels": deepcopy(config.hierarchy_snapshot["levels"]),
            "provenance": "church_approved",
        }
    old_levels = deepcopy(config.hierarchy_snapshot["levels"])
    levels = deepcopy(released["levels"])
    # Same-version overrides preserve the exact installed base, including legacy snapshots.
    old_governance = config.hierarchy_snapshot.get("governance", {})
    if target_version == config.template_version:
        levels = deepcopy(old_governance.get("base_levels", old_levels))
    overrides = deepcopy(old_governance.get("overrides", {}))
    seen = set()
    for item in payload.overrides:
        key = item.level_key + (":" + item.position_key if item.position_key else "")
        if key in seen:
            raise HTTPException(422, "Duplicate override target.")
        seen.add(key)
        values = overrides.setdefault(key, {})
        for locale, label in item.labels.items():
            if label is None:
                values.pop(locale, None)
            else:
                values[locale] = label
        if not values:
            overrides.pop(key, None)
    base = deepcopy(levels)
    targets = {}
    for level in levels:
        targets[level["key"]] = level
        for position in level.get("positions", []):
            targets[level["key"] + ":" + position["key"]] = position
    for key, labels in overrides.items():
        if key not in targets:
            raise HTTPException(422, "Override references an unknown canonical level/office.")
        targets[key]["labels"] = {**targets[key].get("labels", {}), **labels}
        targets[key]["provenance"] = "church_approved"
    terms = {level["key"]: deepcopy(level["labels"]) for level in levels}
    # Existing pre-governance terminology is the installed label layer, not a
    # future catalogue default. Preserve it when adding same-version overrides.
    if target_version == config.template_version and not old_governance:
        for level in levels:
            inherited = config.terminology_snapshot.get(level["key"], {})
            level["labels"] = {**level["labels"], **inherited, **overrides.get(level["key"], {})}
        terms = {l["key"]: deepcopy(l["labels"]) for l in levels}
        for level in base:
            level["labels"] = {
                **level["labels"],
                **config.terminology_snapshot.get(level["key"], {}),
            }
    # Keep legacy English label/title fields consistent with approved labels.
    for level in levels:
        level["label"] = level["labels"].get("en", level.get("label", "Organization"))
        for position in level.get("positions", []):
            position["title"] = position["labels"].get("en", position.get("title", "Office"))
    problems = []
    if [(l["key"], l.get("optional", False)) for l in old_levels] != [
        (l["key"], l.get("optional", False)) for l in levels
    ]:
        problems.append("Hierarchy identifiers/order/optional levels require structural review.")
    office_changes = []
    for key in dict.fromkeys([l["key"] for l in old_levels + levels]):
        old = next((l for l in old_levels if l["key"] == key), {})
        new = next((l for l in levels if l["key"] == key), {})
        rows = differences(old.get("positions", []), new.get("positions", []), "position")
        office_changes.extend({"level_key": key, **row} for row in rows)
        if any(row["status"] == "removed" for row in rows):
            problems.append(
                "Removed office keys require review; assignments will not be remapped or deleted."
            )
    path = ancestry(db, config.local_unit_id)
    publication = []
    for unit in path:
        proposed = terms.get(unit.level_key)
        changed = proposed != unit.labels_snapshot
        allowed = unit.id == config.local_unit_id and local_leaf(db, unit, config.branch_id)
        impact = (
            "church_owned_local_leaf"
            if allowed
            else "shared_or_ancestor_requires_independent_approval"
        )
        publication.append(
            {
                "unit_id": str(unit.id),
                "level_key": unit.level_key,
                "current": unit.labels_snapshot,
                "proposed": proposed,
                "impact": impact,
                "is_published": unit.is_published,
                "status": "requires_review"
                if changed and not allowed
                else "renamed"
                if changed
                else "unchanged",
            }
        )
        if changed and not allowed:
            problems.append(
                "Ancestor/shared unit labels require independent approval; no partial publication."
            )
    after = {
        "template_version": target_version,
        "terminology_snapshot": terms,
        "hierarchy_snapshot": {
            **deepcopy(config.hierarchy_snapshot),
            "levels": levels,
            "governance": {
                "base_levels": base,
                "overrides": overrides,
                "template_provenance": released.get("provenance", "vinyrd_default"),
                "release_digest": fingerprint(released),
            },
        },
    }
    # Bind approval to exact config, release, override proposal and publication impact.
    token = fingerprint({"revision": revision(config), "after": after, "publication": publication})
    return {
        "denomination": config.denomination,
        "installed_version": config.template_version,
        "target_version": target_version,
        "revision": revision(config),
        "preview_token": token,
        "compatibility_status": "requires_review" if problems else "compatible",
        "problems": list(dict.fromkeys(problems)),
        "levels": differences(
            [
                {**l, "labels": config.terminology_snapshot.get(l["key"], l["labels"])}
                for l in old_levels
            ],
            levels,
            "level",
        ),
        "positions": office_changes,
        "publication": publication,
        "provenance": {
            "template": released.get("provenance", "vinyrd_default"),
            "overrides": "church_approved",
        },
        "approval_status": "not_approved",
        "proposed_snapshot": after,
    }


def approve(db, actor, payload):
    # Same lock as setup: publication/reuse cannot race. Config lock also serializes
    # stale approvals and idempotent requests. No security-definer writes.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(19870421, 19)"))
    config = installed(db, actor.branch_id, lock=True)
    request_digest = fingerprint(payload.model_dump(mode="json"))
    for row in records(db, actor.branch_id):
        previous = json.loads(row.metadata_json)
        if previous.get("request_id") == str(payload.request_id):
            if previous.get("request_digest") != request_digest:
                raise HTTPException(409, "Request ID already used for another approval.")
            return {
                "approval_id": str(row.id),
                "applied_version": previous["after"]["template_version"],
                "idempotent": True,
            }
    if payload.expected_revision != revision(config):
        raise HTTPException(409, "Stale configuration. Review again before approving.")
    review = preview(db, config, payload)
    if review["preview_token"] != payload.preview_token:
        raise HTTPException(409, "Preview changed. Review again before approving.")
    if review["compatibility_status"] != "compatible":
        raise HTTPException(
            409,
            {"message": "Manual review required; nothing applied.", "problems": review["problems"]},
        )
    before, after = snapshot(config), review["proposed_snapshot"]
    for unit in ancestry(db, config.local_unit_id):
        labels = after["terminology_snapshot"].get(unit.level_key)
        if labels != unit.labels_snapshot:
            unit.labels_snapshot = deepcopy(labels)
    config.template_version = after["template_version"]
    config.hierarchy_snapshot = deepcopy(after["hierarchy_snapshot"])
    config.terminology_snapshot = deepcopy(after["terminology_snapshot"])
    row = write_audit_log(
        db,
        actor=actor,
        action=ACTION,
        entity_type="branch",
        entity_id=actor.branch_id,
        metadata={
            "denomination": config.denomination,
            "request_id": str(payload.request_id),
            "request_digest": request_digest,
            "before": before,
            "after": after,
            "publication": review["publication"],
            "compatibility_status": review["compatibility_status"],
            "provenance": review["provenance"],
        },
    )
    db.flush()
    return {
        "approval_id": str(row.id),
        "applied_version": config.template_version,
        "idempotent": False,
    }

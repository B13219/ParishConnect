"""Explicit, atomic church setup. Assignment scope is descriptive, not an access grant."""

import hashlib
import json
import unicodedata
from copy import deepcopy
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, select, text

from app.core.security import role_slug
from app.db.base import utc_now
from app.models import (
    Branch,
    ChurchOrganizationConfiguration,
    OrganizationOfficeAssignment,
    OrganizationUnit,
    Role,
    User,
)
from app.services.audit import write_audit_log
from app.services.denominations import denomination_catalog, normalize_denomination
from app.services.terminology import Terminology, runtime_levels, unit_presentation


class SetupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    denomination: str = Field(min_length=1, max_length=120)
    organization_level: str | None = Field(default=None, max_length=80)
    template_version: int | None = Field(default=None, ge=1)


class UnitInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    level_key: str = Field(min_length=1, max_length=80)
    canonical_name: str = Field(min_length=1, max_length=200)
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    region: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    localized_names: dict[Literal["en", "sw"], str | None] = Field(default_factory=dict)
    is_published: bool = False

    @field_validator("localized_names")
    @classmethod
    def names(cls, value):
        if any(
            name is not None and (not name.strip() or len(name) > 200) for name in value.values()
        ):
            raise ValueError("Official names must be nonblank and at most 200 characters.")
        return {key: name.strip() if name else None for key, name in value.items()}


class ConfirmInput(SetupInput):
    units: list[UnitInput] = Field(default_factory=list, max_length=20)


class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    user_id: UUID
    organization_unit_id: UUID
    position_key: str = Field(min_length=1, max_length=120)
    permission_role: str = Field(min_length=1, max_length=80)
    status: Literal["active", "inactive"] = "active"


def normalized_name(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def setup_preview(payload):
    denomination = normalize_denomination(payload.denomination)
    template = next((t for t in denomination_catalog() if t["value"] == denomination), None)
    if template is None:
        if payload.organization_level or payload.template_version:
            raise HTTPException(
                422, "Custom denominations require a custom hierarchy; omit level/version."
            )
        return {
            "denomination": denomination,
            "template_version": None,
            "setup_status": "custom_required",
            "levels": [],
            "expected_parents": [],
            "available_offices": [],
            "default_terminology": {},
            "organization_level": None,
        }
    levels = template["levels"]
    key = payload.organization_level or levels[-1]["key"]
    selected = next((i for i, level in enumerate(levels) if level["key"] == key), None)
    if selected is None:
        raise HTTPException(422, "Unknown canonical organization level.")
    if payload.template_version and payload.template_version != template["template_version"]:
        raise HTTPException(409, "Template changed. Preview the available version again.")
    return {
        "denomination": denomination,
        "template_version": template["template_version"],
        "setup_status": "draft",
        "organization_level": key,
        "levels": levels,
        "expected_parents": levels[:selected],
        "available_offices": levels[selected]["positions"],
        "default_terminology": {level["key"]: level["labels"] for level in levels},
    }


def unit_data(unit, resolver=None):
    return {
        "id": unit.id,
        "parent_id": unit.parent_id,
        "level_key": unit.level_key,
        "canonical_name": unit.canonical_name,
        "presentation": unit_presentation(unit, resolver),
        "localized_names": unit.localized_names,
        "labels": unit.labels_snapshot,
        "is_published": unit.is_published,
        "is_managed": unit.is_managed,
        "status": unit.status,
    }


def ancestry(db, unit_id):
    result, seen = [], set()
    while unit_id:
        if unit_id in seen or len(seen) >= 32:
            raise HTTPException(409, "Invalid organization ancestry.")
        seen.add(unit_id)
        unit = db.get(OrganizationUnit, unit_id)
        if unit is None:
            raise HTTPException(409, "Organization ancestry is unavailable.")
        result.append(unit)
        unit_id = unit.parent_id
    return list(reversed(result))


def is_unit_descendant_of(db, child, ancestor):
    """Strict descendant; a unit is not its own descendant."""
    return child != ancestor and any(unit.id == ancestor for unit in ancestry(db, child))


def organization_scope_ids(db, unit_id):
    """Inclusive descendant scope. Caller must separately authorize any use of it."""
    tree = select(OrganizationUnit.id).where(OrganizationUnit.id == unit_id).cte(recursive=True)
    tree = tree.union(
        select(OrganizationUnit.id).join(tree, OrganizationUnit.parent_id == tree.c.id)
    )
    return list(db.scalars(select(tree.c.id)))


def user_organization_assignments(db, user_id):
    return list(
        db.scalars(
            select(OrganizationOfficeAssignment).where(
                OrganizationOfficeAssignment.user_id == user_id,
                OrganizationOfficeAssignment.status == "active",
            )
        )
    )


def configuration_data(db, branch_id):
    config = db.get(ChurchOrganizationConfiguration, branch_id)
    if config is None:
        branch = db.get(Branch, branch_id)
        return {
            "setup_status": "draft",
            "denomination": branch.denomination,
            "local_unit_id": None,
            "organization_path": [],
        }
    return {
        "branch_id": config.branch_id,
        "denomination": config.denomination,
        "template_version": config.template_version,
        "setup_status": config.setup_status,
        "local_unit_id": config.local_unit_id,
        "configured_at": config.configured_at,
        "runtime_levels": runtime_levels(Terminology(config)),
        "terminology_snapshot": config.terminology_snapshot,
        "hierarchy_snapshot": config.hierarchy_snapshot,
        "terminology": Terminology(config).payload(
            ancestry(db, config.local_unit_id)[-1].level_key if config.local_unit_id else None
        ),
        "organization_path": [
            unit_data(u, Terminology(config)) for u in ancestry(db, config.local_unit_id)
        ],
    }


def confirm_setup(db, actor, payload):
    # One lock per setup transaction (low-volume administration) also serializes
    # shared public ancestor reuse across branches. Never persists on preview.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(19870421, 19)"))
    branch = db.scalar(select(Branch).where(Branch.id == actor.branch_id).with_for_update())
    incoming = payload.model_dump(mode="json")
    incoming["denomination"] = normalize_denomination(payload.denomination)
    digest = fingerprint(incoming)
    config = db.get(ChurchOrganizationConfiguration, branch.id)
    if config and config.confirmation_fingerprint == digest:
        return config  # Snapshot remains fixed even if the template later changes.
    if config and config.setup_status == "configured":
        raise HTTPException(
            409, "Already configured. Structural reconfiguration requires a later workflow."
        )
    preview = setup_preview(payload)
    if preview["setup_status"] == "custom_required":
        if payload.units:
            raise HTTPException(422, "Do not apply built-in units to a custom denomination.")
        hierarchy = {"levels": [], "path": []}
        local = None
    else:
        if payload.template_version is None:
            raise HTTPException(422, "Confirm the template version shown in preview.")
        levels = preview["levels"]
        target = preview["organization_level"]
        end = next(i for i, level in enumerate(levels) if level["key"] == target)
        permitted = levels[: end + 1]
        keys = [unit.level_key for unit in payload.units]
        expected = [
            level["key"] for level in permitted if not level["optional"] or level["key"] == target
        ]
        if not keys or keys[-1] != target or len(keys) != len(set(keys)):
            raise HTTPException(422, "Provide one ordered ancestry ending at the selected level.")
        if keys != [level["key"] for level in permitted if level["key"] in keys] or not set(
            expected
        ) <= set(keys):
            raise HTTPException(422, "Invalid hierarchy: required parents cannot be skipped.")
        parent, path = None, []
        for entry in payload.units:
            data = entry.model_dump(mode="json")
            match = fingerprint(
                {
                    "denomination": preview["denomination"],
                    "level": entry.level_key,
                    "name": normalized_name(entry.canonical_name),
                    "parent": str(parent.id) if parent else None,
                    "country": entry.country,
                    "region": entry.region,
                    "city": entry.city,
                }
            )
            # Never inspect/reuse another tenant's unpublished registry records.
            candidates = db.scalars(
                select(OrganizationUnit)
                .where(
                    OrganizationUnit.match_key == match,
                    OrganizationUnit.status == "active",
                    or_(
                        OrganizationUnit.owner_branch_id == branch.id,
                        OrganizationUnit.is_published.is_(True),
                    ),
                )
                .order_by(OrganizationUnit.created_at, OrganizationUnit.id)
            ).all()
            expected_labels = next(
                level["labels"] for level in levels if level["key"] == entry.level_key
            )
            if any(
                candidate.is_published and candidate.labels_snapshot != expected_labels
                for candidate in candidates
            ):
                raise HTTPException(
                    409,
                    "Matching published organization has different terminology; independent review required.",
                )
            unit = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.localized_names == entry.localized_names
                    and candidate.labels_snapshot == expected_labels
                    and candidate.is_published == entry.is_published
                    and (entry.level_key != target or candidate.owner_branch_id == branch.id)
                ),
                None,
            )
            if (
                unit
                and entry.level_key == target
                and db.scalar(select(Branch.id).where(Branch.organization_unit_id == unit.id))
            ):
                raise HTTPException(
                    409, "This unit is already linked to a branch; do not claim another church."
                )
            if unit is None:
                unit = OrganizationUnit(
                    **data,
                    normalized_name=normalized_name(entry.canonical_name),
                    denomination=preview["denomination"],
                    parent_id=parent.id if parent else None,
                    owner_branch_id=branch.id,
                    match_key=match,
                    labels_snapshot=deepcopy(
                        next(level["labels"] for level in levels if level["key"] == entry.level_key)
                    ),
                    is_managed=entry.level_key == target,
                )
                db.add(unit)
                db.flush()
                write_audit_log(
                    db,
                    actor=actor,
                    action="organization.unit_created",
                    entity_type="organization_unit",
                    entity_id=unit.id,
                    metadata={"level_key": unit.level_key},
                )
            path.append({"unit_id": str(unit.id), "level_key": unit.level_key})
            parent = unit
        local = parent
        hierarchy = {"levels": deepcopy(levels), "path": path}
        branch.organization_unit_id = local.id
        write_audit_log(
            db,
            actor=actor,
            action="organization.branch_linked",
            entity_type="branch",
            entity_id=branch.id,
            metadata={"organization_unit_id": str(local.id)},
        )
    if config is None:
        config = ChurchOrganizationConfiguration(branch_id=branch.id)
        db.add(config)
    config.denomination = preview["denomination"]
    config.template_version = preview["template_version"]
    config.local_unit_id = local.id if local else None
    config.setup_status = "configured" if local else "custom_required"
    config.configured_by = actor.id
    config.configured_at = utc_now()
    config.hierarchy_snapshot = hierarchy
    config.terminology_snapshot = deepcopy(preview["default_terminology"])
    config.confirmation_fingerprint = digest
    branch.denomination = preview["denomination"]
    write_audit_log(
        db,
        actor=actor,
        action="organization.setup_confirmed",
        entity_type="branch",
        entity_id=branch.id,
        metadata={"template_version": config.template_version, "setup_status": config.setup_status},
    )
    db.flush()
    return config


def save_assignment(db, actor, payload):
    config = db.scalar(
        select(ChurchOrganizationConfiguration)
        .where(ChurchOrganizationConfiguration.branch_id == actor.branch_id)
        .with_for_update()
    )
    # No authority over ancestor offices is inferred from a local Branch admin.
    if (
        not config
        or config.setup_status != "configured"
        or config.local_unit_id != payload.organization_unit_id
    ):
        raise HTTPException(
            403, "Only this branch's configured unit can receive office assignments."
        )
    target = db.get(User, payload.user_id)
    if target is None or target.branch_id != actor.branch_id or target.status != "active":
        raise HTTPException(404, "Active staff user not found in this branch.")
    unit = db.get(OrganizationUnit, config.local_unit_id)
    level = next(l for l in config.hierarchy_snapshot["levels"] if l["key"] == unit.level_key)
    if payload.position_key not in {p["key"] for p in level["positions"]}:
        raise HTTPException(422, "Office key must belong to the installed level template.")
    roles = {role_slug(name) for name in db.scalars(select(Role.name))}
    if payload.permission_role not in roles:
        raise HTTPException(422, "Select an existing VINYRD permission profile.")
    assignment = db.scalar(
        select(OrganizationOfficeAssignment).where(
            OrganizationOfficeAssignment.organization_unit_id == unit.id,
            OrganizationOfficeAssignment.user_id == target.id,
            OrganizationOfficeAssignment.position_key == payload.position_key,
        )
    )
    action = "organization.office_changed" if assignment else "organization.office_created"
    if assignment is None:
        assignment = OrganizationOfficeAssignment(
            branch_id=actor.branch_id,
            organization_unit_id=unit.id,
            user_id=target.id,
            position_key=payload.position_key,
        )
        db.add(assignment)
    assignment.permission_role = payload.permission_role
    assignment.status = payload.status
    db.flush()
    write_audit_log(
        db,
        actor=actor,
        action=action,
        entity_type="organization_office_assignment",
        entity_id=assignment.id,
        metadata={"position_key": assignment.position_key, "status": assignment.status},
    )
    return assignment


def public_organization_paths(db, branch_ids, denominations=None):
    """Batch traversal, public-only at every hop; never emit an incomplete private path."""
    starts = dict(
        db.execute(
            select(Branch.id, Branch.organization_unit_id).where(Branch.id.in_(branch_ids))
        ).all()
    )
    units, pending = {}, {value for value in starts.values() if value}
    for _ in range(32):
        if not pending:
            break
        rows = db.scalars(
            select(OrganizationUnit).where(
                OrganizationUnit.id.in_(pending),
                OrganizationUnit.is_published.is_(True),
                OrganizationUnit.status == "active",
            )
        ).all()
        units.update({unit.id: unit for unit in rows})
        pending = {u.parent_id for u in rows if u.parent_id and u.parent_id not in units}
    result = {}
    for branch_id, unit_id in starts.items():
        path, seen = [], set()
        declared = (denominations or {}).get(branch_id)
        if (
            declared
            and unit_id in units
            and normalize_denomination(declared) != units[unit_id].denomination
        ):
            result[branch_id] = []
            continue
        while unit_id:
            if unit_id not in units or unit_id in seen:
                path = []
                break
            seen.add(unit_id)
            unit = units[unit_id]
            path.append(
                {
                    "level_key": unit.level_key,
                    "name": unit.canonical_name,
                    "labels": unit.labels_snapshot,
                    "presentation": unit_presentation(unit),
                }
            )
            unit_id = unit.parent_id
        result[branch_id] = list(reversed(path))
    return result

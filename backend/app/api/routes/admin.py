import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import password_hash, require_roles, role_slug, user_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import (
    AttendanceRecord,
    AuditLog,
    Branch,
    Contribution,
    Event,
    Household,
    ImportBatch,
    Member,
    Message,
    MessageRecipient,
    PrayerRequest,
    Role,
    SermonLesson,
    User,
    UserRole,
    Visitor,
)
from app.services.audit import write_audit_log

router = APIRouter()


class AdminUserCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None
    password: str
    role: str
    status: str = "active"


class AdminUserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str | None = None
    role: str | None = None
    status: str | None = None


class BranchUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    contact_phone: str | None = None
    denomination: str | None = None
    default_language: str | None = None
    timezone: str | None = None
    community_label: str | None = None

class BranchGeofenceUpdate(BaseModel):
    geofence_enabled: bool
    setup_method: str = Field(pattern="^(map|manual)$")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    attendance_radius_meters: int = Field(default=100, ge=25, le=500)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "BranchGeofenceUpdate":
        if self.geofence_enabled and (
            self.latitude is None or self.longitude is None
        ):
            raise ValueError(
                "Latitude and longitude are required when geofencing is enabled."
            )

        return self

BACKUP_MODELS = {
    "attendance_records": AttendanceRecord,
    "audit_logs": AuditLog,
    "branches": Branch,
    "contributions": Contribution,
    "events": Event,
    "households": Household,
    "imports": ImportBatch,
    "members": Member,
    "message_recipients": MessageRecipient,
    "messages": Message,
    "prayer_requests": PrayerRequest,
    "sermon_lessons": SermonLesson,
    "roles": Role,
    "user_roles": UserRole,
    "users": User,
    "visitors": Visitor,
}


def get_default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create or seed a branch before managing users.",
        )
    return branch


def role_by_slug(db: Session, slug: str) -> Role:
    roles = db.scalars(select(Role).order_by(Role.name.asc())).all()
    role = next((item for item in roles if role_slug(item.name) == slug), None)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    return role


def assign_primary_role(db: Session, user: User, role: Role) -> None:
    db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    db.add(UserRole(user_id=user.id, role_id=role.id))


def serialize_role(role: Role) -> dict[str, object]:
    return {
        "id": str(role.id),
        "name": role.name,
        "slug": role_slug(role.name),
        "description": role.description,
    }


def serialize_user(user: User, db: Session) -> dict[str, object]:
    roles = user_roles(db, user.id)
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "status": user.status,
        "roles": roles,
        "primary_role": roles[0] if roles else "unassigned",
        "created_at": user.created_at.isoformat(),
    }


def serialize_audit_log(log: AuditLog, db: Session) -> dict[str, object]:
    actor = db.get(User, log.actor_user_id) if log.actor_user_id else None
    return {
        "id": str(log.id),
        "actor": actor.name if actor else "System",
        "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": str(log.entity_id) if log.entity_id else None,
        "metadata": json.loads(log.metadata_json or "{}"),
        "created_at": log.created_at.isoformat(),
    }


def serialize_branch(branch: Branch) -> dict[str, object]:
    return {
        "id": str(branch.id),
        "name": branch.name,
        "location": branch.location,
        "contact_phone": branch.contact_phone,
        "latitude": branch.latitude,
        "longitude": branch.longitude,
        "attendance_radius_meters": branch.attendance_radius_meters,
        "geofence_enabled": branch.geofence_enabled,
        "created_at": branch.created_at.isoformat(),
        "updated_at": branch.updated_at.isoformat(),
        "denomination": branch.denomination,
        "default_language": branch.default_language,
        "timezone": branch.timezone,
        "community_label": branch.community_label, 
    }

def table_counts(db: Session) -> dict[str, int]:
    return {
        name: db.scalar(select(func.count()).select_from(model)) or 0
        for name, model in BACKUP_MODELS.items()
    }


@router.get("/branch")
def get_branch_settings(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("administrator")),
) -> dict[str, object]:
    return {"module": "admin", "branch": serialize_branch(get_default_branch(db))}


@router.patch("/branch")
def update_branch_settings(
    payload: BranchUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("administrator")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(branch, key, value)
    write_audit_log(
        db,
        actor=actor,
        action="admin.branch_updated",
        entity_type="branch",
        entity_id=branch.id,
        metadata={"updated_fields": sorted(updates.keys())},
    )
    db.commit()
    db.refresh(branch)
    return {"module": "admin", "branch": serialize_branch(branch)}

@router.get("/branch/geofence")
def get_branch_geofence_settings(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("administrator", "pastor_leader")),
) -> dict[str, object]:
    branch = get_default_branch(db)

    return {
        "module": "admin",
        "geofence": {
            "branch_id": str(branch.id),
            "branch_name": branch.name,
            "latitude": branch.latitude,
            "longitude": branch.longitude,
            "attendance_radius_meters": branch.attendance_radius_meters,
            "geofence_enabled": branch.geofence_enabled,
        },
    }


@router.put("/branch/geofence")
def update_branch_geofence_settings(
    payload: BranchGeofenceUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles("administrator", "pastor_leader")
    ),
) -> dict[str, object]:
    branch = get_default_branch(db)

    branch.latitude = payload.latitude
    branch.longitude = payload.longitude
    branch.attendance_radius_meters = payload.attendance_radius_meters
    branch.geofence_enabled = payload.geofence_enabled

    write_audit_log(
        db,
        actor=actor,
        action="admin.branch_geofence_updated",
        entity_type="branch",
        entity_id=branch.id,
        metadata={
            "setup_method": payload.setup_method,
            "geofence_enabled": payload.geofence_enabled,
            "attendance_radius_meters": payload.attendance_radius_meters,
            "coordinates_configured": (
                payload.latitude is not None
                and payload.longitude is not None
            ),
        },
    )

    db.commit()
    db.refresh(branch)

    return {
        "module": "admin",
        "geofence": {
            "branch_id": str(branch.id),
            "branch_name": branch.name,
            "setup_method": payload.setup_method,
            "latitude": branch.latitude,
            "longitude": branch.longitude,
            "attendance_radius_meters": branch.attendance_radius_meters,
            "geofence_enabled": branch.geofence_enabled,
        },
    }

@router.post("/backup-manifest")
def create_backup_manifest(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("administrator")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    counts = table_counts(db)
    manifest = {
        "module": "admin",
        "kind": "backup_manifest",
        "generated_at": utc_now().isoformat(),
        "branch": serialize_branch(branch),
        "table_counts": counts,
        "notes": [
            "This manifest records export scope and row counts for operational audit.",
            "Full database dump scheduling belongs in deployment infrastructure.",
        ],
    }
    write_audit_log(
        db,
        actor=actor,
        action="admin.backup_manifest_exported",
        entity_type="branch",
        entity_id=branch.id,
        metadata={"table_counts": counts},
    )
    db.commit()
    return manifest


@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("administrator")),
) -> dict[str, object]:
    roles = db.scalars(select(Role).order_by(Role.name.asc())).all()
    return {"module": "admin", "roles": [serialize_role(role) for role in roles]}


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("administrator")),
) -> dict[str, object]:
    users = db.scalars(select(User).order_by(User.created_at.desc()).limit(50)).all()
    return {"module": "admin", "users": [serialize_user(user, db) for user in users]}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("administrator")),
) -> dict[str, object]:
    if db.scalar(select(User).where(User.email == str(payload.email))) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists.")
    branch = get_default_branch(db)
    role = role_by_slug(db, payload.role)
    user = User(
        branch_id=branch.id,
        name=payload.name,
        email=str(payload.email),
        phone=payload.phone,
        password_hash=password_hash(payload.password),
        status=payload.status,
    )
    db.add(user)
    db.flush()
    assign_primary_role(db, user, role)
    write_audit_log(
        db,
        actor=actor,
        action="admin.user_created",
        entity_type="user",
        entity_id=user.id,
        metadata={"email": user.email, "role": role_slug(role.name)},
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user, db)


@router.patch("/users/{user_id}")
def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("administrator")),
) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.identity_self_managed:
        raise HTTPException(403, "This person manages their global account. Manage church records instead.")

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        existing = db.scalar(select(User).where(User.email == str(updates["email"])))
        if existing is not None and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists.")
        user.email = str(updates.pop("email"))
    if updates.get("password"):
        user.password_hash = password_hash(updates.pop("password"))
    elif "password" in updates:
        updates.pop("password")
    if updates.get("role"):
        role = role_by_slug(db, updates.pop("role"))
        assign_primary_role(db, user, role)
        updates["role"] = role_slug(role.name)
    elif "role" in updates:
        updates.pop("role")

    for key, value in updates.items():
        if key in {"name", "phone", "status"}:
            setattr(user, key, value)

    write_audit_log(
        db,
        actor=actor,
        action="admin.user_updated",
        entity_type="user",
        entity_id=user.id,
        metadata={"updated_fields": sorted(updates.keys()), "email": user.email},
    )
    db.commit()
    db.refresh(user)
    return serialize_user(user, db)


@router.get("/audit-logs")
def list_audit_logs(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("administrator")),
) -> dict[str, object]:
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(50)).all()
    return {"module": "admin", "audit_logs": [serialize_audit_log(log, db) for log in logs]}

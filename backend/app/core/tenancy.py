"""Church scoping for existing staff ORM queries, including aggregates and exports.

Only require_roles enables this scope, after authenticating a staff identity.
Global identity services use explicit ownership checks and do not use this scope.
"""

from fastapi import HTTPException
from sqlalchemy import event, inspect, select, text
from sqlalchemy.orm import Session, with_loader_criteria

from app.db.base import Base
from app.models import (
    AttendanceRecord,
    AuditLog,
    Branch,
    CommunityGroup,
    CommunityGroupMembership,
    Contribution,
    Event,
    Household,
    HouseholdPerson,
    ImportBatch,
    Member,
    Message,
    MessageRecipient,
    Ministry,
    MinistryMembership,
    PrayerRequest,
    SermonLesson,
    ServiceTemplate,
    User,
    UserRole,
)

BRANCH_MODELS = (
    AttendanceRecord,
    AuditLog,
    CommunityGroup,
    Contribution,
    Event,
    Household,
    ImportBatch,
    Member,
    Message,
    Ministry,
    PrayerRequest,
    SermonLesson,
    ServiceTemplate,
    User,
)
PARENTS = {
    HouseholdPerson: ("household_id", Household),
    CommunityGroupMembership: ("community_group_id", CommunityGroup),
    MinistryMembership: ("ministry_id", Ministry),
    MessageRecipient: ("message_id", Message),
    UserRole: ("user_id", User),
}


def set_actor(db: Session, user: User) -> None:
    db.info["identity_actor"] = str(user.id)
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('vinyrd.user_id', :actor, true)"), {"actor": str(user.id)}
        )


@event.listens_for(Session, "after_begin")
def restore_actor(db, transaction, connection):
    if connection.dialect.name == "postgresql" and db.info.get("identity_actor"):
        connection.execute(
            text("SELECT set_config('vinyrd.user_id', :actor, true)"),
            {"actor": db.info["identity_actor"]},
        )


@event.listens_for(Session, "do_orm_execute")
def scope_staff_queries(state):
    church = state.session.info.get("staff_church")
    if church is None or not state.is_orm_statement:
        return
    options = [with_loader_criteria(Branch, Branch.id == church, include_aliases=True)]
    for model in BRANCH_MODELS:
        options.append(with_loader_criteria(model, model.branch_id == church, include_aliases=True))
    for model, (key, parent) in PARENTS.items():
        options.append(
            with_loader_criteria(
                model,
                getattr(model, key).in_(select(parent.id).where(parent.branch_id == church)),
                include_aliases=True,
            )
        )
    state.statement = state.statement.options(*options)


@event.listens_for(Session, "before_flush")
def validate_staff_writes(db, flush_context, instances):
    church = db.info.get("staff_church")
    if church is None:
        return
    for obj in set(db.new) | set(db.dirty) | set(db.deleted):
        if isinstance(obj, BRANCH_MODELS) and obj.branch_id != church:
            raise HTTPException(403, "Record belongs to a different church.")
        if isinstance(obj, Branch) and obj.id != church:
            raise HTTPException(403, "Record belongs to a different church.")
        for model, (key, parent) in PARENTS.items():
            if isinstance(obj, model):
                linked = db.get(parent, getattr(obj, key))
                if linked is None or linked.branch_id != church:
                    raise HTTPException(403, "Related record belongs to a different church.")
        # Also validate referenced members, events, group leaders, households and
        # staff. A church-local row must not point into another church's records.
        models = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}
        for column in inspect(type(obj)).columns:
            value = getattr(obj, column.key)
            if value is None:
                continue
            for foreign_key in column.foreign_keys:
                target = models.get(foreign_key.column.table.name)
                if target not in BRANCH_MODELS:
                    continue
                linked = db.get(target, value)
                if linked is None or linked.branch_id != church:
                    raise HTTPException(403, "Related record belongs to a different church.")

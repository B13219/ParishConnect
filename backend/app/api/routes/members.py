import csv
from io import StringIO
from uuid import UUID

from fastapi.responses import Response
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.base import utc_now
from app.db.session import get_db
from app.models import Branch, Household, HouseholdPerson, Member, User, Visitor
from app.services.audit import write_audit_log
from datetime import date





router = APIRouter()


class PersonPayload(BaseModel):
    first_name: str
    last_name: str
    phone: str | None = None
    email: str | None = None


class MemberCreate(PersonPayload):
    membership_status: str = "active"
    address: str | None = None
    area: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    marital_status: str | None = None
    occupation: str | None = None
    preferred_language: str | None = None
    notes: str | None = None

class MemberUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    membership_status: str | None = None
    address: str | None = None
    area: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    marital_status: str | None = None
    occupation: str | None = None
    preferred_language: str | None = None
    notes: str | None = None


class VisitorCreate(PersonPayload):
    follow_up_status: str = "new"
    address: str | None = None
    area: str | None = None
    gender: str | None = None
    preferred_language: str | None = None
    notes: str | None = None
    


class VisitorUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    follow_up_status: str | None = None
    address: str | None = None
    area: str | None = None
    gender: str | None = None
    preferred_language: str | None = None
    notes: str | None = None


class HouseholdCreate(BaseModel):
    name: str
    primary_member_id: UUID | None = None
    primary_phone: str | None = None
    notes: str | None = None


class HouseholdPersonCreate(BaseModel):
    person_type: str
    relationship: str
    member_id: UUID | None = None
    visitor_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    can_self_check_in: bool = True
    status: str = "active"


def get_default_branch(db: Session) -> Branch:
    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create or seed a branch before adding people.",
        )
    return branch


def serialize_member(member: Member) -> dict[str, object]:
    return {
        "id": str(member.id),
        "first_name": member.first_name,
        "last_name": member.last_name,
        "name": f"{member.first_name} {member.last_name}",
        "phone": member.phone,
        "email": member.email,
        "status": member.membership_status,
        "address": member.address,
        "area": member.area,
        "gender": member.gender,
        "date_of_birth": (
            member.date_of_birth.isoformat()
            if member.date_of_birth
            else None
        ),
        "marital_status": member.marital_status,
        "occupation": member.occupation,
        "preferred_language": member.preferred_language,
        "notes": member.notes,
    }


def serialize_visitor(visitor: Visitor) -> dict[str, object]:
    return {
        "id": str(visitor.id),
        "first_name": visitor.first_name,
        "last_name": visitor.last_name,
        "name": f"{visitor.first_name} {visitor.last_name}",
        "phone": visitor.phone,
        "email": visitor.email,
        "follow_up_status": visitor.follow_up_status,
        "converted_member_id": str(visitor.converted_member_id)
        if visitor.converted_member_id
        else None,
        "address": visitor.address,
        "area": visitor.area,
        "gender": visitor.gender,
        "preferred_language": visitor.preferred_language,
        "notes": visitor.notes,
    }


def serialize_household_person(person: HouseholdPerson, db: Session) -> dict[str, object]:
    member = db.get(Member, person.member_id) if person.member_id else None
    visitor = db.get(Visitor, person.visitor_id) if person.visitor_id else None
    first_name = member.first_name if member else visitor.first_name if visitor else person.first_name
    last_name = member.last_name if member else visitor.last_name if visitor else person.last_name

    return {
        "id": str(person.id),
        "person_type": person.person_type,
        "relationship": person.relationship,
        "member_id": str(person.member_id) if person.member_id else None,
        "visitor_id": str(person.visitor_id) if person.visitor_id else None,
        "first_name": first_name,
        "last_name": last_name,
        "name": f"{first_name or ''} {last_name or ''}".strip(),
        "can_self_check_in": person.can_self_check_in == "yes",
        "status": person.status,
    }


def serialize_household(household: Household, db: Session) -> dict[str, object]:
    people = db.scalars(
        select(HouseholdPerson).where(HouseholdPerson.household_id == household.id)
    ).all()
    primary_member = db.get(Member, household.primary_member_id) if household.primary_member_id else None
    return {
        "id": str(household.id),
        "name": household.name,
        "primary_member_id": str(household.primary_member_id)
        if household.primary_member_id
        else None,
        "primary_contact": f"{primary_member.first_name} {primary_member.last_name}"
        if primary_member
        else None,
        "primary_phone": household.primary_phone,
        "notes": household.notes,
        "people": [serialize_household_person(person, db) for person in people],
    }


@router.get("/")
def list_members(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "receptionist")),
) -> dict[str, object]:
    members = db.scalars(select(Member).order_by(Member.created_at.desc()).limit(20)).all()
    visitors = db.scalars(select(Visitor).order_by(Visitor.created_at.desc()).limit(20)).all()

    return {
        "module": "members",
        "status": "demo-data-ready",
        "members": [serialize_member(member) for member in members],
        "visitors": [serialize_visitor(visitor) for visitor in visitors],
    }

@router.get("/export.csv")
def export_people_csv(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "receptionist")),
) -> Response:
    members = db.scalars(
        select(Member).order_by(
            Member.last_name.asc(),
            Member.first_name.asc(),
        )
    ).all()

    visitors = db.scalars(
        select(Visitor).order_by(
            Visitor.last_name.asc(),
            Visitor.first_name.asc(),
        )
    ).all()

    output = StringIO()

    fieldnames = [
        "record_type",
        "id",
        "first_name",
        "last_name",
        "phone",
        "email",
        "address",
        "area",
        "gender",
        "date_of_birth",
        "marital_status",
        "occupation",
        "preferred_language",
        "status",
        "notes",
    ]

    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    for member in members:
        writer.writerow(
            {
                "record_type": "member",
                "id": str(member.id),
                "first_name": member.first_name,
                "last_name": member.last_name,
                "phone": member.phone or "",
                "email": member.email or "",
                "address": member.address or "",
                "area": member.area or "",
                "gender": member.gender or "",
                "date_of_birth": (
                    member.date_of_birth.isoformat()
                    if member.date_of_birth
                    else ""
                ),
                "marital_status": member.marital_status or "",
                "occupation": member.occupation or "",
                "preferred_language": member.preferred_language or "",
                "status": member.membership_status,
                "notes": member.notes or "",
            }
        )

    for visitor in visitors:
        writer.writerow(
            {
                "record_type": "visitor",
                "id": str(visitor.id),
                "first_name": visitor.first_name,
                "last_name": visitor.last_name,
                "phone": visitor.phone or "",
                "email": visitor.email or "",
                "address": visitor.address or "",
                "area": visitor.area or "",
                "gender": visitor.gender or "",
                "date_of_birth": "",
                "marital_status": "",
                "occupation": "",
                "preferred_language": visitor.preferred_language or "",
                "status": visitor.follow_up_status,
                "notes": visitor.notes or "",
            }
        )

    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition":
                'attachment; filename="parishconnect-people.csv"'
        },
    )

@router.get("/households")
def list_households(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("pastor_leader", "receptionist")),
) -> dict[str, object]:
    households = db.scalars(select(Household).order_by(Household.created_at.desc()).limit(20)).all()
    return {
        "module": "households",
        "status": "demo-data-ready",
        "households": [serialize_household(household, db) for household in households],
    }


@router.post("/households", status_code=status.HTTP_201_CREATED)
def create_household(
    payload: HouseholdCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("receptionist")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    if payload.primary_member_id and db.get(Member, payload.primary_member_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary member not found.")

    household = Household(
        branch_id=branch.id,
        name=payload.name,
        primary_member_id=payload.primary_member_id,
        primary_phone=payload.primary_phone,
        notes=payload.notes,
    )
    db.add(household)
    db.flush()
    if payload.primary_member_id:
        db.add(
            HouseholdPerson(
                household_id=household.id,
                member_id=payload.primary_member_id,
                person_type="member",
                relationship="primary",
                can_self_check_in="yes",
            )
        )
    db.commit()
    db.refresh(household)
    return serialize_household(household, db)


@router.post("/households/{household_id}/people", status_code=status.HTTP_201_CREATED)
def add_household_person(
    household_id: UUID,
    payload: HouseholdPersonCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("receptionist")),
) -> dict[str, object]:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found.")
    if payload.person_type not in {"member", "visitor", "child", "dependent"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="person_type must be member, visitor, child, or dependent.",
        )
    if payload.member_id and db.get(Member, payload.member_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
    if payload.visitor_id and db.get(Visitor, payload.visitor_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found.")
    if payload.person_type in {"child", "dependent"} and (
        not payload.first_name or not payload.last_name
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Children and dependents require first_name and last_name.",
        )

    person = HouseholdPerson(
        household_id=household.id,
        member_id=payload.member_id,
        visitor_id=payload.visitor_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        person_type=payload.person_type,
        relationship=payload.relationship,
        can_self_check_in="yes" if payload.can_self_check_in else "no",
        status=payload.status,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return serialize_household_person(person, db)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("receptionist")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    member = Member(
        branch_id=branch.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        membership_status=payload.membership_status,
        joined_at=utc_now(),
        address=payload.address,
        area=payload.area,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        marital_status=payload.marital_status,
        occupation=payload.occupation,
        preferred_language=payload.preferred_language,
        notes=payload.notes,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return serialize_member(member)


@router.patch("/{member_id}")
def update_member(
    member_id: UUID,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader", "receptionist")),
) -> dict[str, object]:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(member, key, str(value) if key == "email" and value else value)

    if updates:
        write_audit_log(
            db,
            actor=actor,
            action="people.member_updated",
            entity_type="member",
            entity_id=member.id,
            metadata={"updated_fields": sorted(updates.keys()), "status": member.membership_status},
        )
    db.commit()
    db.refresh(member)
    return serialize_member(member)


@router.post("/visitors", status_code=status.HTTP_201_CREATED)
def create_visitor(
    payload: VisitorCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("receptionist")),
) -> dict[str, object]:
    branch = get_default_branch(db)
    visitor = Visitor(
        branch_id=branch.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        follow_up_status=payload.follow_up_status,
        address=payload.address,
        area=payload.area,
        gender=payload.gender,
        preferred_language=payload.preferred_language,
        notes=payload.notes,
    )
    db.add(visitor)
    db.commit()
    db.refresh(visitor)
    return serialize_visitor(visitor)


@router.patch("/visitors/{visitor_id}")
def update_visitor(
    visitor_id: UUID,
    payload: VisitorUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("receptionist")),
) -> dict[str, object]:
    visitor = db.get(Visitor, visitor_id)
    if visitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found.")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(visitor, key, str(value) if key == "email" and value else value)

    if updates:
        write_audit_log(
            db,
            actor=actor,
            action="people.visitor_updated",
            entity_type="visitor",
            entity_id=visitor.id,
            metadata={"updated_fields": sorted(updates.keys()), "status": visitor.follow_up_status},
        )
    db.commit()
    db.refresh(visitor)
    return serialize_visitor(visitor)


@router.post("/visitors/{visitor_id}/convert", status_code=status.HTTP_201_CREATED)
def convert_visitor(
    visitor_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("pastor_leader", "receptionist")),
) -> dict[str, object]:
    visitor = db.get(Visitor, visitor_id)
    if visitor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found.")
    if visitor.converted_member_id is not None:
        member = db.get(Member, visitor.converted_member_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Visitor references a missing converted member.",
            )
        return {"member": serialize_member(member), "visitor": serialize_visitor(visitor)}

    member = Member(
        branch_id=visitor.branch_id,
        first_name=visitor.first_name,
        last_name=visitor.last_name,
        phone=visitor.phone,
        email=visitor.email,
        membership_status="active",
        joined_at=utc_now(),
        address=visitor.address,
        area=visitor.area,
        gender=visitor.gender,
        preferred_language=visitor.preferred_language,
        notes=visitor.notes,
    )
    db.add(member)
    db.flush()
    visitor.converted_member_id = member.id
    visitor.follow_up_status = "converted"
    write_audit_log(
        db,
        actor=actor,
        action="people.visitor_converted",
        entity_type="visitor",
        entity_id=visitor.id,
        metadata={"converted_member_id": str(member.id)},
    )
    db.commit()
    db.refresh(member)
    db.refresh(visitor)
    return {"member": serialize_member(member), "visitor": serialize_visitor(visitor)}

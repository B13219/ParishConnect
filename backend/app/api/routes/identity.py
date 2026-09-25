from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, current_user, password_hash, user_profile
from app.core.tenancy import set_actor
from app.db.session import get_db
from app.models import (
    Branch,
    ChurchFollow,
    ChurchMembership,
    ChurchPublicProfile,
    Member,
    MembershipRequest,
    Profile,
    User,
)
from app.services.global_identity import (
    OPEN_REQUESTS,
    lock_user,
    profile_data,
    require_church_admin,
    review_request,
    set_primary,
)

router = APIRouter()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Registration(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=79)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("first_name", "last_name", "email", "phone", mode="before")
    @classmethod
    def strip_contact(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.lower()
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("A valid email address is required.")
        local, domain = value.split("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("A valid email address is required.")
        return value


class ProfileUpdate(Input):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=79)
    phone: str | None = Field(default=None, max_length=40)
    avatar_url: str | None = Field(default=None, max_length=2048, pattern=r"^https://")
    country: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)


class RequestCreate(Input):
    message: str | None = Field(default=None, max_length=2000)
    share_contact: bool = False


class RequestReview(Input):
    status: Literal["approved", "rejected", "more_info_required"]
    matched_member_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=2000)


class MembershipUpdate(Input):
    status: Literal["pending", "active", "inactive", "former", "suspended"]


class MembershipView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    church_id: UUID
    user_id: UUID | None
    legacy_member_id: UUID | None
    membership_number: str | None
    status: Literal["pending", "active", "inactive", "former", "suspended"]
    role: str
    is_primary: bool
    joined_at: datetime | None
    approved_at: datetime | None


class RequestView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    church_id: UUID
    user_id: UUID
    status: str
    message: str | None
    created_at: datetime
    reviewed_at: datetime | None
    rejection_reason: str | None
    matched_member_id: UUID | None
    applicant_snapshot: dict


def commit(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A conflicting account or relationship already exists.") from exc


def church_exists(db, church_id):
    if db.get(Branch, church_id) is None:
        raise HTTPException(404, "Church not found.")


@router.post("/auth/register", status_code=201)
def register(payload: Registration, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(func.lower(User.email) == payload.email)):
        raise HTTPException(
            409, "An account already uses this email. Sign in or reset its password."
        )
    user = User(
        id=uuid4(),
        name=f"{payload.first_name} {payload.last_name}",
        email=payload.email,
        phone=payload.phone,
        password_hash=password_hash(payload.password),
        identity_self_managed=True,
        status="active",
    )
    db.add(user)
    set_actor(db, user)
    db.flush()
    profile = db.get(Profile, user.id)
    profile.first_name = payload.first_name
    profile.last_name = payload.last_name
    commit(db)
    return {
        "access_token": create_access_token(user, db),
        "token_type": "bearer",
        "user": user_profile(db, user),
    }


@router.get("/identity/me")
def identity_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return profile_data(db, user)


@router.put("/identity/me")
def update_profile(
    payload: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    user.name = f"{payload.first_name} {payload.last_name}"
    user.phone = payload.phone
    user.identity_self_managed = True
    commit(db)
    return profile_data(db, user)


@router.get("/identity/churches")
def churches(user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Compatibility response shape; only explicitly published directory entries.
    return [
        {"id": b.church_id, "name": b.name, "location": b.location}
        for b in db.scalars(
            select(ChurchPublicProfile)
            .where(ChurchPublicProfile.is_published.is_(True))
            .order_by(ChurchPublicProfile.name)
        )
    ]


@router.get("/identity/memberships", response_model=list[MembershipView])
def memberships(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(ChurchMembership).where(ChurchMembership.user_id == user.id)).all()


@router.put("/identity/memberships/{membership_id}/primary", response_model=MembershipView)
def primary(membership_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership = set_primary(db, user, membership_id)
    commit(db)
    return membership


@router.post("/identity/churches/{church_id}/requests", response_model=RequestView, status_code=201)
def request_membership(
    church_id: UUID,
    payload: RequestCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    church_exists(db, church_id)
    lock_user(db, user.id)
    if db.scalar(
        select(ChurchMembership.id).where(
            ChurchMembership.user_id == user.id,
            ChurchMembership.church_id == church_id,
            ChurchMembership.status.in_(("active", "suspended")),
        )
    ):
        raise HTTPException(409, "An active or suspended membership already exists.")
    if db.scalar(
        select(MembershipRequest.id).where(
            MembershipRequest.user_id == user.id,
            MembershipRequest.church_id == church_id,
            MembershipRequest.status.in_(OPEN_REQUESTS),
        )
    ):
        raise HTTPException(409, "An open request already exists.")
    profile = profile_data(db, user)
    snapshot = {
        "name": user.name,
        "first_name": profile["first_name"],
        "last_name": profile["last_name"],
    }
    if payload.share_contact:
        snapshot.update({key: profile[key] for key in ("email", "phone", "avatar_url")})
    request = MembershipRequest(
        user_id=user.id, church_id=church_id, message=payload.message, applicant_snapshot=snapshot
    )
    db.add(request)
    commit(db)
    return request


@router.get("/identity/requests", response_model=list[RequestView])
def requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(MembershipRequest).where(MembershipRequest.user_id == user.id)).all()


@router.post("/identity/requests/{request_id}/cancel", response_model=RequestView)
def cancel_request(
    request_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    lock_user(db, user.id)
    request = db.scalar(
        select(MembershipRequest)
        .where(MembershipRequest.id == request_id, MembershipRequest.user_id == user.id)
        .with_for_update()
    )
    if request is None:
        raise HTTPException(404, "Request not found.")
    if request.status not in OPEN_REQUESTS:
        raise HTTPException(409, "This request has already been resolved.")
    request.status = "cancelled"
    commit(db)
    return request


@router.get("/identity/churches/{church_id}/requests", response_model=list[RequestView])
def church_requests(
    church_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    require_church_admin(db, user, church_id)
    return db.scalars(
        select(MembershipRequest).where(MembershipRequest.church_id == church_id)
    ).all()


@router.post("/identity/requests/{request_id}/review", response_model=RequestView)
def review(
    request_id: UUID,
    payload: RequestReview,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    request = review_request(
        db, user, request_id, payload.status, payload.matched_member_id, payload.reason
    )
    commit(db)
    return request


@router.get("/identity/follows")
def follows(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        {"id": f.id, "church_id": f.church_id, "created_at": f.created_at}
        for f in db.scalars(select(ChurchFollow).where(ChurchFollow.user_id == user.id))
    ]


@router.get("/identity/churches/{church_id}/memberships", response_model=list[MembershipView])
def church_memberships(
    church_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    require_church_admin(db, user, church_id)
    return db.scalars(select(ChurchMembership).where(ChurchMembership.church_id == church_id)).all()


@router.patch("/identity/memberships/{membership_id}", response_model=MembershipView)
def update_membership(
    membership_id: UUID,
    payload: MembershipUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership = db.scalar(
        select(ChurchMembership).where(
            ChurchMembership.id == membership_id, ChurchMembership.church_id == user.branch_id
        )
    )
    if membership is None:
        raise HTTPException(404, "Membership not found.")
    require_church_admin(db, user, membership.church_id)
    if membership.user_id:
        lock_user(db, membership.user_id)
    db.refresh(membership, with_for_update=True)
    membership.status = payload.status
    if payload.status != "active":
        membership.is_primary = False
    if membership.legacy_member_id:
        member = db.get(Member, membership.legacy_member_id)
        member.membership_status = payload.status
    commit(db)
    return membership


@router.put("/identity/churches/{church_id}/follow")
def follow(church_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    church_exists(db, church_id)
    lock_user(db, user.id)
    if not db.scalar(
        select(ChurchFollow.id).where(
            ChurchFollow.user_id == user.id, ChurchFollow.church_id == church_id
        )
    ):
        db.add(ChurchFollow(user_id=user.id, church_id=church_id))
    commit(db)
    return {"church_id": church_id, "following": True}


@router.delete("/identity/churches/{church_id}/follow")
def unfollow(church_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lock_user(db, user.id)
    follow = db.scalar(
        select(ChurchFollow).where(
            ChurchFollow.user_id == user.id, ChurchFollow.church_id == church_id
        )
    )
    if follow:
        db.delete(follow)
    commit(db)
    return {"church_id": church_id, "following": False}

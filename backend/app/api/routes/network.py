"""Public network data is an explicit publication, never a legacy-table dump."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.routes.identity import MembershipView, RequestView, commit
from app.core.security import current_user
from app.db.session import get_db
from app.models import (
    Branch,
    ChurchFollow,
    ChurchMembership,
    ChurchPublicProfile,
    Member,
    MembershipRequest,
    User,
)
from app.services.denominations import denomination_catalog
from app.services.global_identity import lock_user, require_church_admin, set_primary

router = APIRouter()


class PublicItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=2000)
    starts_at: datetime | None = None
    location: str | None = Field(default=None, max_length=240)


class PublicProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    region: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    denomination: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=240)
    logo_url: str | None = Field(default=None, pattern=r"^https://", max_length=2048)
    about: str | None = Field(default=None, max_length=6000)
    service_times: str | None = Field(default=None, max_length=2000)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, pattern=r"^https://", max_length=2048)
    public_events: list[PublicItem] = Field(default_factory=list, max_length=50)
    public_announcements: list[PublicItem] = Field(default_factory=list, max_length=50)
    public_ministries: list[PublicItem] = Field(default_factory=list, max_length=50)
    is_published: bool

    @field_validator("country", mode="before")
    @classmethod
    def country_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


def public_data(profile):
    # Explicit allowlist: adding a model field cannot accidentally publish it.
    return {
        "church_id": profile.church_id,
        **{
            key: getattr(profile, key)
            for key in PublicProfileInput.model_fields
            if key != "is_published"
        },
    }


@router.get("/denominations")
def denominations():
    return {"items": denomination_catalog(), "custom_allowed": True}


@router.get("/churches")
def discover(
    q: str = Query(default="", max_length=160),
    country: str = Query(default="", max_length=2),
    region: str = Query(default="", max_length=100),
    city: str = Query(default="", max_length=100),
    denomination: str = Query(default="", max_length=120),
    view: Literal["all", "new", "local", "tanzania"] = "all",
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(ChurchPublicProfile).where(ChurchPublicProfile.is_published.is_(True))
    if q.strip():
        query = query.where(ChurchPublicProfile.name.icontains(q.strip(), autoescape=True))
    if view == "tanzania":
        country = "TZ"
    if view == "local" and not (city.strip() or region.strip()):
        raise HTTPException(422, "Choose a region or city for local churches.")
    for key, value in (
        ("country", country),
        ("region", region),
        ("city", city),
        ("denomination", denomination),
    ):
        if value.strip():
            query = query.where(
                func.lower(getattr(ChurchPublicProfile, key)) == value.strip().lower()
            )
    query = query.order_by(
        ChurchPublicProfile.created_at.desc() if view == "new" else ChurchPublicProfile.name,
        ChurchPublicProfile.church_id,
    )
    rows = db.scalars(query.offset(offset).limit(limit + 1)).all()
    return {
        "items": [public_data(row) for row in rows[:limit]],
        "has_more": len(rows) > limit,
        "offset": offset,
        "limit": limit,
    }


@router.get("/churches/{church_id}")
def public_profile(church_id: UUID, db: Session = Depends(get_db)):
    profile = db.scalar(
        select(ChurchPublicProfile).where(
            ChurchPublicProfile.church_id == church_id, ChurchPublicProfile.is_published.is_(True)
        )
    )
    if profile is None:
        raise HTTPException(404, "Public church profile not found.")
    return public_data(profile)


@router.get("/me")
def network_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    memberships = db.scalars(
        select(ChurchMembership).where(ChurchMembership.user_id == user.id)
    ).all()
    result = []
    for membership in memberships:
        branch = db.get(Branch, membership.church_id)
        result.append(
            {
                **MembershipView.model_validate(membership).model_dump(),
                "church_name": branch.name if branch else "Church",
            }
        )
    return {
        "memberships": result,
        "requests": [
            RequestView.model_validate(r)
            for r in db.scalars(
                select(MembershipRequest)
                .where(MembershipRequest.user_id == user.id)
                .order_by(MembershipRequest.created_at.desc())
            )
        ],
        "follows": [
            f.church_id
            for f in db.scalars(select(ChurchFollow).where(ChurchFollow.user_id == user.id))
        ],
    }


@router.post("/me/initialize-home")
def initialize_home(user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Only the owner reads their complete membership set. A church reviewer
    # never learns whether a different church is already home.
    lock_user(db, user.id)
    primary = db.scalar(
        select(ChurchMembership).where(
            ChurchMembership.user_id == user.id, ChurchMembership.is_primary.is_(True)
        )
    )
    if primary is None:
        first = db.scalar(
            select(ChurchMembership)
            .where(ChurchMembership.user_id == user.id, ChurchMembership.status == "active")
            .order_by(ChurchMembership.created_at, ChurchMembership.id)
            .limit(1)
        )
        if first:
            primary = set_primary(db, user, first.id)
    commit(db)
    return {"home_church_id": primary.church_id if primary else None}


@router.get("/admin/profile")
def admin_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_church_admin(db, user, user.branch_id)
    profile = db.get(ChurchPublicProfile, user.branch_id)
    if profile:
        return {**public_data(profile), "is_published": profile.is_published}
    branch = db.get(Branch, user.branch_id)
    return {"church_id": branch.id, "name": branch.name, "is_published": False}


@router.put("/admin/profile")
def save_public_profile(
    payload: PublicProfileInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    require_church_admin(db, user, user.branch_id)
    lock_user(db, user.id)
    # Serialize competing administrators using the church row, not just user row.
    db.scalar(select(Branch).where(Branch.id == user.branch_id).with_for_update())
    profile = db.get(ChurchPublicProfile, user.branch_id)
    if profile is None:
        profile = ChurchPublicProfile(church_id=user.branch_id)
        db.add(profile)
    for key, value in payload.model_dump(mode="json").items():
        setattr(profile, key, value)
    commit(db)
    return {**public_data(profile), "is_published": profile.is_published}


def possible_matches(db, request):
    snapshot = request.applicant_snapshot or {}
    conditions = []
    if snapshot.get("email"):
        conditions.append(func.lower(Member.email) == snapshot["email"].lower())
    if snapshot.get("phone"):
        conditions.append(Member.phone == snapshot["phone"])
    if snapshot.get("first_name") and snapshot.get("last_name"):
        conditions.append(
            (func.lower(Member.first_name) == snapshot["first_name"].lower())
            & (func.lower(Member.last_name) == snapshot["last_name"].lower())
        )
    if not conditions:
        return []
    query = (
        select(Member)
        .where(
            Member.branch_id == request.church_id,
            or_(*conditions),
            ~select(User.id).where(User.member_id == Member.id).exists(),
            ~select(ChurchMembership.id)
            .where(
                ChurchMembership.legacy_member_id == Member.id,
                ChurchMembership.user_id.is_not(None),
            )
            .exists(),
        )
        .limit(20)
    )
    return [
        {
            "id": member.id,
            "name": f"{member.first_name} {member.last_name}",
            "email": member.email,
            "phone": member.phone,
            "warning": "Possible match only. Verify identity before linking.",
        }
        for member in db.scalars(query)
    ]


@router.get("/admin/requests")
def admin_requests(
    status: Literal[
        "pending", "approved", "rejected", "more_info_required", "cancelled"
    ] = "pending",
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_church_admin(db, user, user.branch_id)
    requests = db.scalars(
        select(MembershipRequest)
        .where(MembershipRequest.church_id == user.branch_id, MembershipRequest.status == status)
        .order_by(MembershipRequest.created_at.desc(), MembershipRequest.id)
        .offset(offset)
        .limit(51)
    ).all()
    return {
        "church_id": user.branch_id,
        "has_more": len(requests) > 50,
        "items": [
            {
                **RequestView.model_validate(r).model_dump(),
                "possible_matches": possible_matches(db, r),
            }
            for r in requests[:50]
        ],
    }

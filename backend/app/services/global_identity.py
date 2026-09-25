"""Identity operations. Callers commit once; approval/linking is atomic."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import user_roles
from app.db.base import utc_now
from app.models import ChurchMembership, Member, MembershipRequest, Profile, User

OPEN_REQUESTS = ("pending", "more_info_required")


def lock_user(db: Session, user_id: UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(404, "Account not found.")
    return user


def require_church_admin(db: Session, actor: User, church_id: UUID) -> None:
    if actor.branch_id != church_id or "administrator" not in user_roles(db, actor.id):
        raise HTTPException(403, "Church administrator permission required.")


def set_primary(db: Session, user: User, membership_id: UUID) -> ChurchMembership:
    lock_user(db, user.id)  # Serializes home changes and approvals for this identity.
    memberships = list(
        db.scalars(
            select(ChurchMembership).where(ChurchMembership.user_id == user.id).with_for_update()
        )
    )
    target = next((m for m in memberships if m.id == membership_id), None)
    if target is None:
        raise HTTPException(404, "Membership not found.")
    if target.status != "active":
        raise HTTPException(409, "Only an active membership can be the home church.")
    for membership in memberships:
        membership.is_primary = False
    db.flush()  # Release the partial unique index before setting the new primary.
    target.is_primary = True
    return target


def review_request(
    db: Session,
    actor: User,
    request_id: UUID,
    decision: str,
    matched_member_id: UUID | None,
    reason: str | None,
) -> MembershipRequest:
    # Check the church before loading or locking another person's account.
    request = db.scalar(
        select(MembershipRequest).where(
            MembershipRequest.id == request_id, MembershipRequest.church_id == actor.branch_id
        )
    )
    if request is None:
        raise HTTPException(404, "Membership request not found.")
    require_church_admin(db, actor, request.church_id)
    user = lock_user(db, request.user_id)
    db.refresh(request, with_for_update=True)
    if request.status not in OPEN_REQUESTS:
        raise HTTPException(409, "This request has already been resolved.")
    if decision == "approved":
        approve_membership(db, actor, user, request, matched_member_id)
    elif matched_member_id is not None:
        raise HTTPException(422, "A member match is only accepted with approval.")
    request.status = decision
    request.reviewed_at = utc_now()
    request.reviewed_by = actor.id
    request.rejection_reason = reason
    return request


def approve_membership(db, actor, user, request, matched_member_id):
    existing = db.scalar(
        select(ChurchMembership)
        .where(
            ChurchMembership.user_id == user.id,
            ChurchMembership.church_id == request.church_id,
        )
        .with_for_update()
    )
    if existing and existing.status == "active":
        raise HTTPException(409, "An active membership already exists.")
    if existing and existing.legacy_member_id:
        if matched_member_id and matched_member_id != existing.legacy_member_id:
            raise HTTPException(409, "This account already has a different member record here.")
        matched_member_id = existing.legacy_member_id
    if matched_member_id:
        member = db.scalar(
            select(Member)
            .where(Member.id == matched_member_id, Member.branch_id == request.church_id)
            .with_for_update()
        )
        if member is None:
            raise HTTPException(404, "Member not found in this church.")
        legacy_owner = db.scalar(
            select(User.id).where(User.member_id == member.id, User.id != user.id)
        )
        linked = db.scalar(
            select(ChurchMembership)
            .where(ChurchMembership.legacy_member_id == member.id)
            .with_for_update()
        )
        if legacy_owner or (linked and linked.user_id not in (None, user.id)):
            raise HTTPException(409, "This member is already linked to another account.")
        if existing and linked and existing.id != linked.id:
            raise HTTPException(409, "Reconcile the existing membership before linking.")
    else:
        # This lookup does not auto-claim. Even an unverified matching email must
        # lead to explicit church review instead of silently duplicating a person.
        first, _, last = user.name.partition(" ")
        candidates = [func.lower(Member.email) == user.email.lower()]
        if user.phone:
            candidates.append(Member.phone == user.phone)
        candidates.append(
            (func.lower(Member.first_name) == first.lower())
            & (func.lower(Member.last_name) == last.lower())
        )
        if db.scalar(
            select(Member.id)
            .where(Member.branch_id == request.church_id, or_(*candidates))
            .limit(1)
        ):
            raise HTTPException(409, "Possible existing member: review and explicitly match first.")
        member = Member(
            branch_id=request.church_id,
            first_name=first[:100],
            last_name=last[:100],
            email=user.email,
            phone=user.phone,
            membership_status="active",
        )
        db.add(member)
        db.flush()
        linked = db.scalar(
            select(ChurchMembership).where(ChurchMembership.legacy_member_id == member.id)
        )
    membership = existing or linked
    if membership is None:
        membership = ChurchMembership(church_id=request.church_id, legacy_member_id=member.id)
        db.add(membership)
    membership.user_id = user.id
    membership.status = "active"
    membership.role = "member"  # Never conveys a staff role.
    membership.approved_by = actor.id
    membership.approved_at = utc_now()
    membership.joined_at = membership.joined_at or utc_now()
    member.membership_status = "active"
    request.matched_member_id = member.id
    # Linking through the self-service workflow transfers credential control to
    # the person. A church must not reset or disable a shared global identity.
    user.identity_self_managed = True
    db.flush()
    # The owner selects a home church. Reviewers must not inspect memberships
    # in other churches merely to decide whether to set a primary flag.


def current_membership(db: Session, user: User, church_id: UUID | None) -> ChurchMembership | None:
    query = select(ChurchMembership).where(ChurchMembership.user_id == user.id)
    if church_id:
        query = query.where(ChurchMembership.church_id == church_id)
    else:
        query = query.where(ChurchMembership.is_primary.is_(True))
    return db.scalar(query)


def profile_data(db: Session, user: User) -> dict:
    profile = db.get(Profile, user.id)
    first, _, last = user.name.partition(" ")
    return {
        "user_id": user.id,
        "first_name": profile.first_name if profile else first,
        "last_name": profile.last_name if profile else last,
        "email": user.email,
        "phone": profile.phone if profile else user.phone,
        **{key: getattr(profile, key, None) for key in ("avatar_url", "country", "region", "city")},
    }

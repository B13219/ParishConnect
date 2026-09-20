from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import password_hash, role_slug
from app.core.settings import settings
from app.db.session import SessionLocal
from app.models import Branch, Role, User, UserRole

ROLE_DEFINITIONS = [
    ("Administrator", "Full Vinyrd administration access"),
    ("Pastor / Leader", "Pastoral care, sermons, reporting, and ministry oversight"),
    ("Accountant", "Stewardship and finance records"),
    ("Receptionist", "People, households, imports, and front-desk workflows"),
    ("Usher", "Attendance check-in access"),
    ("Member", "Vinyrd member portal access"),
]


def ensure_role(db: Session, name: str, description: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name, description=description)
        db.add(role)
        db.flush()
    return role


def bootstrap_admin(
    db: Session,
    *,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    branch_name: str,
    branch_location: str | None = None,
) -> dict[str, object]:
    email = admin_email.strip().lower()
    name = admin_name.strip()
    password = admin_password

    if not name or not email:
        raise ValueError("Bootstrap administrator name and email are required.")
    if len(password) < 12 or password.lower() == "parishconnect":
        raise ValueError("Bootstrap administrator password must be at least 12 characters.")

    branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
    if branch is None:
        branch = Branch(
            name=branch_name.strip() or "Vinyrd Pilot Church",
            location=branch_location.strip() if branch_location else None,
        )
        db.add(branch)
        db.flush()

    roles = {
        role_slug(name): ensure_role(db, name, description)
        for name, description in ROLE_DEFINITIONS
    }
    admin_role = roles["administrator"]

    user = db.scalar(select(User).where(User.email == email))
    created = False
    if user is None:
        user = User(
            branch_id=branch.id,
            name=name,
            email=email,
            password_hash=password_hash(password),
            status="active",
        )
        db.add(user)
        db.flush()
        created = True
    else:
        user.branch_id = user.branch_id or branch.id
        user.status = "active"

    link = db.get(UserRole, {"user_id": user.id, "role_id": admin_role.id})
    if link is None:
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))

    db.commit()
    db.refresh(user)
    return {
        "created": created,
        "user_id": str(user.id),
        "email": user.email,
        "branch_id": str(branch.id),
        "branch_name": branch.name,
    }


def main() -> int:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        print("Vinyrd bootstrap admin: credentials not supplied; skipping.")
        return 0

    with SessionLocal() as db:
        result = bootstrap_admin(
            db,
            admin_name=settings.bootstrap_admin_name or "Vinyrd Administrator",
            admin_email=settings.bootstrap_admin_email,
            admin_password=settings.bootstrap_admin_password,
            branch_name=settings.bootstrap_branch_name,
            branch_location=settings.bootstrap_branch_location or None,
        )

    action = "created" if result["created"] else "already exists"
    print(
        "Vinyrd bootstrap admin: "
        f"{action}; {result['email']} @ {result['branch_name']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

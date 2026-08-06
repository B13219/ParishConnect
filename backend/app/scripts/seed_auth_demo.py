from sqlalchemy import select

from app.core.security import password_hash
from app.db.session import SessionLocal
from app.models import Branch, Role, User, UserRole

DEMO_PASSWORD = "parishconnect"
DEMO_ROLES = {
    "Administrator": "Full system access",
    "Pastor / Leader": "Reports and ministry oversight",
    "Accountant": "Stewardship and finance records",
    "Receptionist": "Visitor and front-desk records",
    "Usher": "Attendance check-in access",
    "Member": "Member portal access",
}
DEMO_USERS = [
    {
        "name": "Amina Joseph",
        "email": "admin@graceparish.test",
        "phone": "+255 700 111 222",
        "role": "Administrator",
    },
    {
        "name": "Pastor Daniel Mushi",
        "email": "pastor@graceparish.test",
        "phone": "+255 700 333 444",
        "role": "Pastor / Leader",
    },
    {
        "name": "Grace Treasurer",
        "email": "accountant@graceparish.test",
        "phone": "+255 700 444 555",
        "role": "Accountant",
    },
    {
        "name": "Rehema Front Desk",
        "email": "reception@graceparish.test",
        "phone": "+255 700 555 666",
        "role": "Receptionist",
    },
    {
        "name": "Jonas Usher",
        "email": "usher@graceparish.test",
        "phone": "+255 700 777 888",
        "role": "Usher",
    },
]


def seed_auth_demo() -> dict[str, int]:
    with SessionLocal() as db:
        branch = db.scalar(select(Branch).order_by(Branch.created_at.asc()))
        if branch is None:
            raise RuntimeError("Seed a branch before adding demo auth users.")

        roles_created = 0
        users_created = 0
        links_created = 0
        roles: dict[str, Role] = {}
        for name, description in DEMO_ROLES.items():
            role = db.scalar(select(Role).where(Role.name == name))
            if role is None:
                role = Role(name=name, description=description)
                db.add(role)
                db.flush()
                roles_created += 1
            roles[name] = role

        for item in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == item["email"]))
            if user is None:
                user = User(
                    branch_id=branch.id,
                    name=item["name"],
                    email=item["email"],
                    phone=item["phone"],
                    password_hash=password_hash(DEMO_PASSWORD),
                    status="active",
                )
                db.add(user)
                db.flush()
                users_created += 1
            role = roles[item["role"]]
            link = db.get(UserRole, {"user_id": user.id, "role_id": role.id})
            if link is None:
                db.add(UserRole(user_id=user.id, role_id=role.id))
                links_created += 1

        db.commit()
        return {"roles": roles_created, "users": users_created, "role_links": links_created}


def main() -> None:
    print(f"Auth seed complete: {seed_auth_demo()}")


if __name__ == "__main__":
    main()

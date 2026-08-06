from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import password_hash
from app.models import Branch, Role, User, UserRole

TEST_PASSWORD = "parishconnect"


def add_test_user(db: Session, branch: Branch, role_name: str) -> User:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name, description=f"{role_name} test role")
        db.add(role)
        db.flush()

    email = role_name.lower().replace(" ", "_").replace("/", "").replace("__", "_") + "@test.local"
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            branch_id=branch.id,
            name=f"{role_name} User",
            email=email,
            password_hash=password_hash(TEST_PASSWORD),
            status="active",
        )
        db.add(user)
        db.flush()

    if db.get(UserRole, {"user_id": user.id, "role_id": role.id}) is None:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    return user


def auth_headers(client: TestClient, role_name: str = "Administrator") -> dict[str, str]:
    email = role_name.lower().replace(" ", "_").replace("/", "").replace("__", "_") + "@test.local"
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

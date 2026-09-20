import base64
import hashlib
import hmac
import json
from datetime import timedelta
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.db.base import utc_now
from app.db.session import get_db
from app.models import Role, User, UserRole


def password_hash(password: str, *, salt: str | None = None) -> str:
    salt_value = salt or settings.password_salt
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_value.encode(), 100_000)
    return "pbkdf2_sha256$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash == "demo-password-hash-change-before-production":
        return password == settings.demo_password
    return hmac.compare_digest(password_hash(password), stored_hash)


def role_slug(role_name: str) -> str:
    return (
        role_name.lower()
        .replace("/", "")
        .replace(" ", "_")
        .replace("__", "_")
        .strip("_")
    )


def user_roles(db: Session, user_id: UUID) -> list[str]:
    roles = db.scalars(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name.asc())
    ).all()
    return [role_slug(role) for role in roles]


def user_profile(db: Session, user: User) -> dict[str, object]:
    roles = user_roles(db, user.id)
    return {
        "id": str(user.id),
        "member_id": str(user.member_id) if user.member_id else None,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "status": user.status,
        "roles": roles,
        "primary_role": roles[0] if roles else "unassigned",
    }


def _token_signature(payload: str) -> str:
    digest = hmac.new(settings.auth_token_secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def create_access_token(user: User, db: Session) -> str:
    expires_at = utc_now() + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "roles": user_roles(db, user.id),
        "exp": int(expires_at.timestamp()),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    return f"{encoded}.{_token_signature(encoded)}"


def create_password_reset_token(user: User) -> str:
    expires_at = utc_now() + timedelta(minutes=30)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "purpose": "password_reset",
        "exp": int(expires_at.timestamp()),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    return f"{encoded}.{_token_signature(encoded)}"


def decode_access_token(token: str) -> dict[str, object]:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
    if not hmac.compare_digest(_token_signature(encoded), signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode()).decode())
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
    if int(payload.get("exp", 0)) < int(utc_now().timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired.")
    return payload


def decode_password_reset_token(token: str) -> dict[str, object]:
    payload = decode_access_token(token)
    if payload.get("purpose") != "password_reset":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid reset token.")
    return payload


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required.")
    payload = decode_access_token(authorization.split(" ", 1)[1])
    user_id = payload.get("sub")
    try:
        user = db.get(User, UUID(str(user_id)))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable.")
    return user


def require_roles(*allowed_roles: str):
    allowed = set(allowed_roles)

    def dependency(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        roles = set(user_roles(db, user.id))
        if "administrator" in roles or roles.intersection(allowed):
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    return dependency

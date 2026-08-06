from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_password_reset_token,
    current_user,
    decode_password_reset_token,
    password_hash,
    user_profile,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.services.audit import write_audit_log

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or user.status != "active" or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return {
        "access_token": create_access_token(user, db),
        "token_type": "bearer",
        "user": user_profile(db, user),
    }


@router.post("/logout")
def logout(user: User = Depends(current_user)) -> dict[str, object]:
    return {"status": "logged_out", "user_id": str(user.id)}


@router.post("/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    response: dict[str, object] = {
        "status": "accepted",
        "detail": "If the email exists, a password reset will be prepared.",
    }
    if user is None or user.status != "active":
        return response

    token = create_password_reset_token(user)
    write_audit_log(
        db,
        actor=user,
        action="auth.password_reset_requested",
        entity_type="user",
        entity_id=user.id,
        metadata={"email": user.email},
    )
    db.commit()
    response["demo_reset_token"] = token
    return response


@router.post("/password-reset/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    token_payload = decode_password_reset_token(payload.token)
    user = db.get(User, UUID(str(token_payload.get("sub"))))
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid reset token.")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")

    user.password_hash = password_hash(payload.new_password)
    write_audit_log(
        db,
        actor=user,
        action="auth.password_reset_confirmed",
        entity_type="user",
        entity_id=user.id,
        metadata={"email": user.email},
    )
    db.commit()
    return {"status": "password_updated"}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    return {"user": user_profile(db, user)}

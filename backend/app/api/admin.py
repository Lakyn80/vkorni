"""
admin.py
--------
Admin authentication endpoints.

Routes:
    POST /api/admin/setup           — create first admin (only if none exists)
    POST /api/admin/login           — returns JWT token
    POST /api/admin/change-password — protected; change own password
    POST /api/admin/reset-token     — protected; generate a one-time reset token
    POST /api/admin/reset-password  — use reset token to set new password
"""
import time
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext

from app.api.deps import get_current_admin, json_response
from app.db.sqlalchemy_db import AdminUser, SessionLocal
from app.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── helpers ───────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return _pwd.hash(password)


def _verify(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def _make_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": username, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )



# ── schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    username: str
    token: str
    new_password: str


# ── routes ────────────────────────────────────────────────────────────────────

@router.post("/login")
def login(payload: LoginRequest):
    """Authenticate and return a JWT Bearer token."""
    with SessionLocal() as db:
        user = db.query(AdminUser).filter_by(username=payload.username).first()

    if not user or not _verify(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _make_token(user.username)
    return json_response({"access_token": token, "token_type": "bearer"})


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: str = Depends(get_current_admin),
):
    """Change password for the currently authenticated admin."""
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    with SessionLocal() as db:
        user = db.query(AdminUser).filter_by(username=current_user).first()
        if not user:
            raise HTTPException(status_code=404, detail="Admin not found")
        if not _verify(payload.current_password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        user.hashed_password = _hash(payload.new_password)
        db.commit()

    return json_response({"status": "ok"})


@router.post("/reset-token")
def generate_reset_token(current_user: str = Depends(get_current_admin)):
    """Generate a one-time reset token (valid 15 minutes). Returns the token."""
    token = secrets.token_urlsafe(32)
    expires = time.time() + 15 * 60  # 15 minutes

    with SessionLocal() as db:
        user = db.query(AdminUser).filter_by(username=current_user).first()
        if not user:
            raise HTTPException(status_code=404, detail="Admin not found")
        user.reset_token = token
        user.reset_token_expires = expires
        db.commit()

    return json_response({"reset_token": token, "expires_in_seconds": 900})


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """Use a reset token to set a new password (no auth required)."""
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    with SessionLocal() as db:
        user = db.query(AdminUser).filter_by(username=payload.username).first()
        if not user or not user.reset_token:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        if user.reset_token != payload.token:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        if user.reset_token_expires is None or time.time() > user.reset_token_expires:
            raise HTTPException(status_code=400, detail="Reset token has expired")

        user.hashed_password = _hash(payload.new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()

    return json_response({"status": "ok"})

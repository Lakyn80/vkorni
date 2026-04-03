"""
deps.py
-------
Shared dependencies for all API routers.
"""
import re

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

_bearer = HTTPBearer(auto_error=False)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "*",
}

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    return _WHITESPACE_RE.sub(" ", name).strip()


def normalize_person_name(name: str) -> str:
    # Treat commas inside a single person name as punctuation, not a separator.
    return normalize_name(name.replace(",", " "))


def validate_name(name: str) -> str:
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Missing or empty name")
    cleaned = normalize_name(name)
    if len(cleaned) > 120:
        raise HTTPException(status_code=400, detail="Name is too long")
    if any(ord(ch) < 32 for ch in cleaned):
        raise HTTPException(status_code=400, detail="Invalid characters in name")
    return cleaned


def validate_person_name(name: str) -> str:
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Missing or empty name")
    cleaned = normalize_person_name(name)
    if len(cleaned) > 120:
        raise HTTPException(status_code=400, detail="Name is too long")
    if any(ord(ch) < 32 for ch in cleaned):
        raise HTTPException(status_code=400, detail="Invalid characters in name")
    return cleaned


def json_response(payload: dict) -> JSONResponse:
    return JSONResponse(content=payload, headers=CORS_HEADERS)


def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency — validates Bearer JWT and returns the admin username."""
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        username: str | None = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

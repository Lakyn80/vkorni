"""
deps.py
-------
Shared dependencies for all API routers.
"""
from fastapi import HTTPException
from fastapi.responses import JSONResponse

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


def validate_name(name: str) -> str:
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Missing or empty name")
    cleaned = name.strip()
    if len(cleaned) > 120:
        raise HTTPException(status_code=400, detail="Name is too long")
    if any(ord(ch) < 32 for ch in cleaned):
        raise HTTPException(status_code=400, detail="Invalid characters in name")
    return cleaned


def json_response(payload: dict) -> JSONResponse:
    return JSONResponse(content=payload, headers=CORS_HEADERS)

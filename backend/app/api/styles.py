"""
styles.py
---------
Endpoints: writing style management (ChromaDB-backed).

Routes:
    POST /api/style
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import validate_name, json_response
from app.db.chroma_client import upsert_style

router = APIRouter(prefix="/api", tags=["styles"])


class StylePayload(BaseModel):
    name: str
    text: str


@router.post("/style")
def upsert_style_profile(payload: StylePayload):
    style_name = validate_name(payload.name)
    style_text = (payload.text or "").strip()
    if len(style_text) < 50:
        raise HTTPException(status_code=400, detail="Style text is too short")
    upsert_style(style_name, style_text)
    return json_response({"status": "OK", "name": style_name})

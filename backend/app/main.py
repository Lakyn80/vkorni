import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db.sqlalchemy_db import init_db
from app.api.biography import router as biography_router
from app.api.export import router as export_router
from app.api.batch import router as batch_router
from app.api.images import router as images_router
from app.api.styles import router as styles_router
from app.api.admin import router as admin_router

init_db()

app = FastAPI(title="VKorni API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file mounts ────────────────────────────────────────────────────────
for env_var, mount_path, name in [
    ("PHOTOS_DIR",         "/static/photos",          "photos"),
    ("IMAGE_ACCEPTED_DIR", "/static/accepted_images", "accepted_images"),
    ("IMAGE_REJECTED_DIR", "/static/rejected_images", "rejected_images"),
]:
    directory = os.getenv(env_var, f"/app/static/{name}")
    os.makedirs(directory, exist_ok=True)
    app.mount(mount_path, StaticFiles(directory=directory), name=name)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(biography_router)
app.include_router(export_router)
app.include_router(batch_router)
app.include_router(images_router)
app.include_router(styles_router)
app.include_router(admin_router)

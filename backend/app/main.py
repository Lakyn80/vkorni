from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api.routes import router

app = FastAPI(title="VKorni API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.getenv("PHOTOS_DIR", "/app/static/photos")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static/photos", StaticFiles(directory=static_dir), name="photos")

accepted_dir = os.getenv("IMAGE_ACCEPTED_DIR", "/app/static/accepted_images")
os.makedirs(accepted_dir, exist_ok=True)
app.mount("/static/accepted_images", StaticFiles(directory=accepted_dir), name="accepted_images")

rejected_dir = os.getenv("IMAGE_REJECTED_DIR", "/app/static/rejected_images")
os.makedirs(rejected_dir, exist_ok=True)
app.mount("/static/rejected_images", StaticFiles(directory=rejected_dir), name="rejected_images")

app.include_router(router)

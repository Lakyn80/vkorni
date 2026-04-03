import os


class Settings:
    # Wikipedia / Wikidata
    wiki_lang: str        = os.getenv("WIKI_LANG", "ru")
    wiki_user_agent: str  = os.getenv("WIKI_USER_AGENT", "vkorni-bot/1.0")
    wikidata_base: str    = os.getenv("WIKIDATA_BASE_URL", "https://www.wikidata.org")
    wiki_max_images: int  = int(os.getenv("WIKI_MAX_IMAGES", "5"))

    # Redis / Queue
    redis_url: str        = os.getenv("REDIS_URL", "redis://redis:6379/0")
    worker_max_retries: int  = int(os.getenv("WORKER_MAX_RETRIES", "3"))
    worker_retry_delay: int  = int(os.getenv("WORKER_RETRY_DELAY", "5"))
    bulk_export_item_timeout: int = int(os.getenv("BULK_EXPORT_ITEM_TIMEOUT", "900"))
    bulk_export_max_attempts: int = int(os.getenv("BULK_EXPORT_MAX_ATTEMPTS", "5"))
    bulk_export_retry_delay_seconds: int = int(os.getenv("BULK_EXPORT_RETRY_DELAY_SECONDS", "15"))
    bulk_export_watchdog_interval_seconds: int = int(os.getenv("BULK_EXPORT_WATCHDOG_INTERVAL_SECONDS", "60"))
    bulk_export_stall_seconds: int = int(os.getenv("BULK_EXPORT_STALL_SECONDS", "180"))

    # Google Vision
    vision_api_key: str   = os.getenv("GOOGLE_VISION_API_KEY", "")

    # Image pipeline directories
    photos_dir: str       = os.getenv("PHOTOS_DIR", "/app/static/photos")
    accepted_dir: str     = os.getenv("IMAGE_ACCEPTED_DIR", "/app/static/accepted_images")
    rejected_dir: str     = os.getenv("IMAGE_REJECTED_DIR", "/app/static/rejected_images")
    batch_size: int       = int(os.getenv("IMAGE_BATCH_SIZE", "2"))

    # Frame assets (relative to backend root)
    frames_dir: str       = os.getenv("FRAMES_DIR", "/app/frames")

    # Public URL of this backend — used to serve framed images inline in XenForo.
    # Must be reachable by vkorni.com (set to VPS IP/domain when deployed).
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "").rstrip("/")

    # Admin auth
    jwt_secret: str  = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))


settings = Settings()

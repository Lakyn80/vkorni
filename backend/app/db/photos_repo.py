import os
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("PHOTOS_DB_PATH", "/app/photos.db")


def _ensure_dir() -> None:
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


@contextmanager
def _conn():
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                source_url TEXT,
                description TEXT,
                status TEXT DEFAULT 'pending'
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_photos_person
            ON photos(person_name);
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_photos_source_url
            ON photos(source_url);
            """
        )
        # Migrate existing tables that lack the status column
        try:
            conn.execute("ALTER TABLE photos ADD COLUMN status TEXT DEFAULT 'pending';")
        except Exception:
            pass  # Column already exists
        conn.commit()


def add_photo(person_name: str, file_path: str, source_url: str | None, description: str | None) -> None:
    init_db()
    try:
        with _conn() as conn:
            conn.execute(
                """
                INSERT INTO photos (person_name, file_path, source_url, description)
                VALUES (?, ?, ?, ?);
                """,
                (person_name, file_path, source_url, description),
            )
            conn.commit()
    except Exception:
        logger.exception("Failed to insert photo", extra={"person": person_name, "file_path": file_path})
        raise


def find_photo_by_source_url(source_url: str) -> dict | None:
    init_db()
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, person_name, file_path, source_url, description
            FROM photos
            WHERE source_url = ?
            ORDER BY id DESC
            LIMIT 1;
            """,
            (source_url,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "person_name": row[1],
        "file_path": row[2],
        "source_url": row[3],
        "description": row[4],
    }


def get_photos_by_person(person_name: str) -> list[dict]:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, person_name, file_path, source_url, description
            FROM photos
            WHERE person_name = ?
            ORDER BY id ASC;
            """,
            (person_name,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "person_name": r[1],
            "file_path": r[2],
            "source_url": r[3],
            "description": r[4],
        }
        for r in rows
    ]


def delete_photos_by_person(person_name: str) -> None:
    init_db()
    with _conn() as conn:
        conn.execute("DELETE FROM photos WHERE person_name = ?;", (person_name,))
        conn.commit()


def update_photo_status(file_path: str, status: str) -> None:
    """Update the pipeline status of a photo ('pending', 'accepted', 'rejected')."""
    init_db()
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE photos SET status = ? WHERE file_path = ?;",
                (status, file_path),
            )
            conn.commit()
    except Exception:
        logger.exception("Failed to update photo status", extra={"file_path": file_path})

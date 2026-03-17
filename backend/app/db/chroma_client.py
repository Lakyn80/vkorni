import os
import logging
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

CHROMA_PATH = os.getenv("CHROMA_PATH", "/app/chroma_data")

client = chromadb.Client(
    Settings(
        persist_directory=CHROMA_PATH,
        is_persistent=True,
    )
)

collection = client.get_or_create_collection("styles")


def upsert_style(name: str, text: str) -> None:
    if not text:
        return
    try:
        collection.upsert(
            documents=[text],
            metadatas=[{"name": name}],
            ids=[name],
        )
        try:
            client.persist()
        except Exception:
            pass  # persist() removed in newer chromadb versions
    except Exception:
        logger.exception("Chroma upsert failed", extra={"name": name})
        raise


def add_document(name: str, text: str) -> None:
    upsert_style(name, text)


def get_style(name: str) -> str | None:
    try:
        result = collection.get(ids=[name])
        docs = result.get("documents", [])
        if docs:
            return docs[0]
    except Exception:
        logger.exception("Chroma get failed", extra={"name": name})
    return None


def search_styles(query: str, top_k: int = 3) -> list[dict]:
    try:
        results = collection.query(query_texts=[query], n_results=top_k)
        docs = results.get("documents", [[]])[0]
        return [{"text": d} for d in docs]
    except Exception:
        logger.exception("Chroma search failed", extra={"query": query})
        return []

# -*- coding: utf-8 -*-
import chromadb
from chromadb.config import Settings

# === JEDNA PERSISTENTNÍ CHROMA PRO VKORNI ===
PERSIST_PATH = "/app/chroma_data"

_client = None
_collection = None

def _get_client():
    global _client
    if _client is None:
        _client = chromadb.Client(
            Settings(
                persist_directory=PERSIST_PATH,
                is_persistent=True,
            )
        )
    return _client

def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection("biographies")
    return _collection

# === TATO FUNKCE CHYBĚLA → TÍM PADAL BACKEND ===
def add_document(name: str, text: str):
    col = _get_collection()
    col.add(
        documents=[text],
        metadatas=[{"name": name}],
        ids=[name]
    )

def search_similar(name: str, top_k: int = 3):
    col = _get_collection()
    results = col.query(
        query_texts=[name],
        n_results=top_k
    )
    docs = results.get("documents", [[]])[0]
    return [{"text": d} for d in docs]

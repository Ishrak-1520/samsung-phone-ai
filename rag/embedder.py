import os
import sys
from dotenv import load_dotenv
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from db.database import SessionLocal
from db.models import Embedding, Phone, Spec

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# nomic-embed-text requires document prefix when indexing chunks
DOCUMENT_PREFIX = "search_document: "


def get_embedding(text_val: str) -> list[float]:
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {"model": EMBEDDING_MODEL, "prompt": text_val}
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["embedding"]


def build_chunk(phone_model: str, category: str, spec_rows: list) -> str:
    spec_parts = "; ".join(f"{row.key}: {row.value}" for row in spec_rows)
    return f"{phone_model} | {category}: {spec_parts}"


def embed_phone(phone: Phone, db) -> int:
    db.query(Embedding).filter(Embedding.phone_id == phone.id).delete()
    db.flush()

    specs = db.query(Spec).filter(Spec.phone_id == phone.id).order_by(Spec.category).all()
    categories: dict[str, list] = {}
    for spec in specs:
        categories.setdefault(spec.category, []).append(spec)

    chunk_count = 0
    for category, rows in categories.items():
        chunk_text = build_chunk(phone.model, category, rows)
        vector = get_embedding(DOCUMENT_PREFIX + chunk_text)

        embedding_row = Embedding(
            phone_id=phone.id,
            category=category,
            chunk_text=chunk_text,
            embedding=vector,
        )
        db.add(embedding_row)
        chunk_count += 1

    db.flush()
    return chunk_count


def run_embedder():
    db = SessionLocal()
    try:
        phones = db.query(Phone).order_by(Phone.id).all()
        print(f"Found {len(phones)} phones. Embedding with '{EMBEDDING_MODEL}'")

        total_chunks = 0
        for phone in phones:
            count = embed_phone(phone, db)
            total_chunks += count
            print(f"  {phone.model}: {count} chunks")

        db.commit()
        print(f"Saved {total_chunks} chunks to embeddings table")

    except Exception as e:
        db.rollback()
        print(f"Error during embedding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_embedder()

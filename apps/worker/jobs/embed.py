from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from apps.worker.worker import celery_app
from apps.api.db.session import SessionLocal
from apps.api.db.models import Chunk, Embedding
from packages.rag.embeddings import embed_texts


@celery_app.task(name="embed.embed_chunks")
def embed_chunks(document_version_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        chunks: List[Chunk] = (
            db.query(Chunk).filter(Chunk.document_version_id == document_version_id).order_by(Chunk.id).all()
        )
        texts = [c.text for c in chunks]
        if not texts:
            return {"ok": True, "embeddings": 0}
        model, dim, vectors = embed_texts(texts)
        for chunk, vec in zip(chunks, vectors):
            db.merge(Embedding(chunk_id=chunk.id, model=model, dim=dim, vector=vec))
        db.commit()
        return {"ok": True, "embeddings": len(texts), "model": model}
    finally:
        db.close()



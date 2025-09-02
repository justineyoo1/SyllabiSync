from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from apps.api.db.session import db_session
from apps.api.db.models import Document, DocumentVersion, User


router = APIRouter(prefix="/documents", tags=["documents"]) 


@router.get("")
def list_documents() -> list[dict]:
    with db_session() as db:
        docs = db.query(Document).order_by(Document.id.desc()).all()
        return [
            {"id": d.id, "title": d.title, "storage_uri": d.storage_uri, "created_at": d.created_at.isoformat()}
            for d in docs
        ]


@router.get("/{doc_id}/versions")
def list_versions(doc_id: int) -> list[dict]:
    with db_session() as db:
        vers = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).order_by(DocumentVersion.id).all()
        return [
            {"id": v.id, "pages": v.pages, "created_at": v.created_at.isoformat()}
            for v in vers
        ]


@router.post("/reset")
def reset_documents(purge_storage: bool = False) -> dict:
    # MVP: default dev user only
    deleted = 0
    with db_session() as db:
        user = db.query(User).filter(User.email == "dev@local").one_or_none()
        if not user:
            return {"deleted": 0}
        # Optional: best-effort S3 deletion could be added here
        deleted = db.query(Document).filter(Document.user_id == user.id).delete(synchronize_session=False)
        db.commit()
    return {"deleted": int(deleted)}



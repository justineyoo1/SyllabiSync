from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from apps.api.db.session import db_session
from apps.api.db.models import Document, DocumentVersion


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



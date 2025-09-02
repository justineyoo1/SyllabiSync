from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from apps.api.schemas.uploads import (
    NotifyUploadRequest,
    NotifyUploadResponse,
    PresignRequest,
    PresignResponse,
)
from apps.api.services.uploads import create_presigned_post
from apps.api.db.models import Document, DocumentVersion, User
from apps.api.db.session import db_session
from apps.worker.jobs.ingest import parse_pdf


router = APIRouter(prefix="/files", tags=["files"]) 


@router.post("/presign", response_model=PresignResponse)
def presign(body: PresignRequest) -> PresignResponse:
    url, fields, storage_uri = create_presigned_post(body.filename, body.content_type)
    return PresignResponse(url=url, fields=fields, storage_uri=storage_uri)


@router.post("/notify", response_model=NotifyUploadResponse)
def notify(body: NotifyUploadRequest) -> NotifyUploadResponse:
    # Note: In a real app, use auth for user_id. For MVP, ensure a default user exists.
    with db_session() as db:
        default_user = db.query(User).filter(User.email == "dev@local").one_or_none()
        if default_user is None:
            default_user = User(email="dev@local", hashed_password="dev")
            db.add(default_user)
            db.flush()

        doc = Document(user_id=default_user.id, title=body.title, storage_uri=body.storage_uri)
        db.add(doc)
        db.flush()
        doc_id = doc.id

        ver = DocumentVersion(document_id=doc_id, content_sha256="pending", pages=0)
        db.add(ver)
        db.flush()
        ver_id = ver.id
        db.commit()

    # enqueue parse job; chunking and embeddings are chained inside worker
    parse_pdf.delay(ver_id, body.storage_uri)
    return NotifyUploadResponse(document_id=doc_id, document_version_id=ver_id, job_enqueued=True)



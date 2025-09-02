from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
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


# Preview: proxy the PDF bytes so the browser can render without direct MinIO access
import re
import io
import boto3
from packages.common.config import get_settings


def _download_s3(storage_uri: str) -> bytes:
    settings = get_settings()
    m = re.match(r"s3://([^/]+)/(.+)", storage_uri)
    if not m:
        raise ValueError("invalid storage_uri")
    bucket, key = m.groups()
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_secure,
    )
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


@router.get("/preview")
def preview(storage_uri: str) -> StreamingResponse:
    data = _download_s3(storage_uri)
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf")



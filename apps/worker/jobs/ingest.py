from __future__ import annotations

import io
import os
import re
from typing import List

import boto3
from sqlalchemy.orm import Session

from apps.worker.worker import celery_app
from apps.api.db.session import SessionLocal
from apps.api.db.models import DocumentVersion, Page, Chunk
from apps.worker.jobs.embed import embed_chunks
from apps.worker.jobs.events import extract_events
from packages.parsers.pdf import extract_pages_from_pdf_bytes
from packages.rag.chunking import split_text_into_chunks
from packages.common.config import get_settings


def _read_s3_bytes(storage_uri: str) -> bytes:
    # storage_uri: s3://bucket/key
    settings = get_settings()
    match = re.match(r"s3://([^/]+)/(.+)", storage_uri)
    if not match:
        raise ValueError("invalid storage_uri")
    bucket, key = match.groups()
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


@celery_app.task(name="ingest.parse_pdf")
def parse_pdf(document_version_id: int, storage_uri: str) -> dict:
    db: Session = SessionLocal()
    try:
        ver = db.get(DocumentVersion, document_version_id)
        if ver is None:
            return {"ok": False, "error": "version_not_found"}
        data = _read_s3_bytes(storage_uri)
        pages = extract_pages_from_pdf_bytes(data)
        ver.pages = len(pages)
        for i, text in enumerate(pages, start=1):
            db.add(Page(document_version_id=ver.id, page_number=i, text=text))
        db.commit()
        # chain chunking next
        chunk_pages.delay(ver.id)
        return {"ok": True, "pages": len(pages)}
    finally:
        db.close()


@celery_app.task(name="ingest.chunk_pages")
def chunk_pages(document_version_id: int, max_len: int = 800, overlap: int = 100) -> dict:
    db: Session = SessionLocal()
    try:
        pages: List[Page] = (
            db.query(Page).filter(Page.document_version_id == document_version_id).order_by(Page.page_number).all()
        )
        created = 0
        for page in pages:
            for start, end, chunk_text in split_text_into_chunks(page.text, max_len=max_len, overlap=overlap):
                db.add(
                    Chunk(
                        document_version_id=document_version_id,
                        page_number=page.page_number,
                        text=chunk_text,
                        start_offset=start,
                        end_offset=end,
                    )
                )
                created += 1
        db.commit()
        # chain embeddings next, then extract events
        embed_chunks.delay(document_version_id)
        extract_events.delay(document_version_id)
        return {"ok": True, "chunks": created}
    finally:
        db.close()



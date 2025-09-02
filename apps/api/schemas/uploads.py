from __future__ import annotations

from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    filename: str = Field(..., description="Original file name, e.g., syllabus.pdf")
    content_type: str = Field(..., description="MIME type, e.g., application/pdf")


class PresignResponse(BaseModel):
    url: str
    fields: dict[str, str]
    storage_uri: str = Field(..., description="s3://bucket/key to be used in notify call")


class NotifyUploadRequest(BaseModel):
    title: str
    storage_uri: str


class NotifyUploadResponse(BaseModel):
    document_id: int
    document_version_id: int
    job_enqueued: bool



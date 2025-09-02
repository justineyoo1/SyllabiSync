from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    documents: Mapped[list[Document]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(back_populates="document", cascade="all, delete-orphan")  # type: ignore[name-defined]


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document: Mapped[Document] = relationship(back_populates="versions")
    pages_rel: Mapped[list[Page]] = relationship(back_populates="document_version", cascade="all, delete-orphan")  # type: ignore[name-defined]
    chunks: Mapped[list[Chunk]] = relationship(back_populates="document_version", cascade="all, delete-orphan")  # type: ignore[name-defined]

    __table_args__ = (
        Index("uq_document_version_hash", "document_id", "content_sha256", unique=True),
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    bbox_meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    document_version: Mapped[DocumentVersion] = relationship(back_populates="pages_rel")

    __table_args__ = (
        Index("ix_pages_docver_page", "document_version_id", "page_number", unique=True),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    document_version: Mapped[DocumentVersion] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_docver_page", "document_version_id", "page_number"),
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)
    model: Mapped[str] = mapped_column(String(128), primary_key=True)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(1536))

    # backref if needed via relationship from Chunk


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    source_start_offset: Mapped[int] = mapped_column(Integer, nullable=True)
    source_end_offset: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)




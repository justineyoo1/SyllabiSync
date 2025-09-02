"""initial tables and pgvector extension

Revision ID: 20250902_000001
Revises: 
Create Date: 2025-09-02 00:00:01.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "20250902_000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("storage_uri", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "document_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "content_sha256", name="uq_document_version_hash"),
    )

    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_version_id", sa.Integer(), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("bbox_meta", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_pages_docver_page", "pages", ["document_version_id", "page_number"], unique=True)

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_version_id", sa.Integer(), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
    )
    op.create_index("ix_chunks_docver_page", "chunks", ["document_version_id", "page_number"], unique=False)

    op.create_table(
        "embeddings",
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("model", sa.String(length=128), primary_key=True),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("vector", Vector(1536)),
    )


def downgrade() -> None:
    op.drop_table("embeddings")
    op.drop_index("ix_chunks_docver_page", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_pages_docver_page", table_name="pages")
    op.drop_table("pages")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("users")
    # keep extension installed



"""add events table

Revision ID: 20250902_000002
Revises: 20250902_000001
Create Date: 2025-09-02 00:00:02.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20250902_000002"
down_revision: Union[str, None] = "20250902_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_version_id", sa.Integer(), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("source_start_offset", sa.Integer(), nullable=True),
        sa.Column("source_end_offset", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_events_docver", "events", ["document_version_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_events_docver", table_name="events")
    op.drop_table("events")



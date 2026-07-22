"""create upload_sessions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

upload_sessions 表：上传完成前的暂态会话（SPEC.md 第 8.3 节）。通过 project_id
外键归属项目；expires_at 记录过期时间，过期会话不能完成正式接入。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", name=op.f("fk_upload_sessions_project_id_projects")),
            nullable=False,
        ),
        sa.Column("declared_filename", sa.String(length=255), nullable=False),
        sa.Column("declared_size_bytes", sa.Integer(), nullable=False),
        sa.Column("declared_mime", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upload_sessions")),
    )
    op.create_index(op.f("ix_upload_sessions_project_id"), "upload_sessions", ["project_id"])
    op.create_index(op.f("ix_upload_sessions_status"), "upload_sessions", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_upload_sessions_status"), table_name="upload_sessions")
    op.drop_index(op.f("ix_upload_sessions_project_id"), table_name="upload_sessions")
    op.drop_table("upload_sessions")

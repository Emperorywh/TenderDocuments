"""create document_versions table

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-23

document_versions 表：不可变文件版本。原始对象键/哈希/大小/MIME/版本号一经创建
不可覆盖；status 与 canonical_object_key/page_count 等处理态字段可演进。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", name=op.f("fk_document_versions_document_id_documents")),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_object_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("canonical_object_key", sa.String(length=512), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("published_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effect_order", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_versions")),
    )
    # 同一逻辑文件内版本号唯一；同哈希同文档不重复（C-018 在应用层细化）。
    op.create_index(
        op.f("uq_document_versions_document_id_version_number"),
        "document_versions",
        ["document_id", "version_number"],
        unique=True,
    )
    op.create_index(
        op.f("ix_document_versions_sha256"),
        "document_versions",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_versions_sha256"), table_name="document_versions")
    op.drop_index(
        op.f("uq_document_versions_document_id_version_number"), table_name="document_versions"
    )
    op.drop_table("document_versions")

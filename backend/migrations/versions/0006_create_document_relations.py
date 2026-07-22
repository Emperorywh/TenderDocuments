"""create document_relations table

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-23

document_relations 表：文件间替代/补充/引用关系。归属 project_id；禁止自引用
（CHECK）；跨项目非法关系由应用用例按 project_id 校验（C-024）。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", name=op.f("fk_document_relations_project_id_projects")),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", name=op.f("fk_document_relations_source_documents")),
            nullable=False,
        ),
        sa.Column(
            "target_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", name=op.f("fk_document_relations_target_documents")),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
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
        sa.CheckConstraint(
            "source_document_id <> target_document_id",
            name="ck_document_relations_no_self_reference",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_relations")),
    )
    op.create_index(
        op.f("ix_document_relations_project_id"), "document_relations", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_relations_project_id"), table_name="document_relations")
    op.drop_table("document_relations")

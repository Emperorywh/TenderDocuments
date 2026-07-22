"""create projects table

Revision ID: 0001
Revises:
Create Date: 2026-07-23

projects 表：项目顶层归属边界（B-001）。
- 业务主键为系统生成 UUID；
- 无身份字段（organization_id/user_id/created_by/reviewed_by/tenant_id）；
- 生命周期状态以字符串存储（ProjectLifecycleStatus 取值）；
- 含乐观版本号与归档/待删除/清除时间戳。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("industry", sa.String(length=64), nullable=False),
        sa.Column("project_type", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_deletion_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    # 便于按状态筛选活动项目（归档项目默认不出现在活动列表）。
    op.create_index(op.f("ix_projects_lifecycle_state"), "projects", ["lifecycle_state"])


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_lifecycle_state"), table_name="projects")
    op.drop_table("projects")

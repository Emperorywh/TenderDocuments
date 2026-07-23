"""create analysis_tasks table

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-23

analysis_tasks 表：原子分析任务。每个任务显式关联运行（analysis_run_id）与项目
（project_id），使 Worker 能校验任务/运行/项目归属一致，不信任消息中的孤立 ID
（SPEC.md 第 4.3 节）。idempotency_key 在运行内唯一，防重复正式结果
（SPEC.md 第 11.3 节）。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "analysis_run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", name=op.f("fk_analysis_tasks_run")),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", name=op.f("fk_analysis_tasks_project")),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_tasks")),
        sa.UniqueConstraint(
            "analysis_run_id",
            "idempotency_key",
            name="uq_analysis_tasks_run_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_analysis_tasks_analysis_run_id"), "analysis_tasks", ["analysis_run_id"]
    )
    op.create_index(
        op.f("ix_analysis_tasks_project_id"), "analysis_tasks", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_tasks_project_id"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_analysis_run_id"), table_name="analysis_tasks")
    op.drop_table("analysis_tasks")

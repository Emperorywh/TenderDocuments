"""create task_attempts table

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-23

task_attempts 表：每次执行尝试记录。每次执行（含重试）新增一条，不覆盖旧尝试
（SPEC.md 第 5.4、11.2 节）。attempt_number 在任务内唯一自增，使重试历史可追溯。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "analysis_task_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_tasks.id", name=op.f("fk_task_attempts_task")),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_attempts")),
        sa.UniqueConstraint(
            "analysis_task_id",
            "attempt_number",
            name="uq_task_attempts_task_number",
        ),
    )
    op.create_index(
        op.f("ix_task_attempts_analysis_task_id"),
        "task_attempts",
        ["analysis_task_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_task_attempts_analysis_task_id"), table_name="task_attempts"
    )
    op.drop_table("task_attempts")

"""add task_attempts heartbeat timestamp

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-23

为 task_attempts 增加 heartbeat_at：运行中的任务定期刷新该时间戳，卡死任务扫描
（D-017）据此识别心跳过期（Worker 崩溃/卡死）的执行尝试并恢复（SPEC.md 第 12.2 节
“心跳扫描恢复卡死任务”、第 11.2 节）。heartbeat_at 与 started_at 分离：started_at
为执行开始（不可变），heartbeat_at 为最近心跳（随执行刷新）。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_attempts",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_attempts", "heartbeat_at")

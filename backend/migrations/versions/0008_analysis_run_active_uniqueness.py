"""add active analysis run uniqueness constraint

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-23

为 analysis_runs 增加活动运行唯一约束：同一项目同一输入指纹只能存在一个活动
（非终态）运行（SPEC.md 第 11.3 节）。终态集与领域层
ACTIVE_RUN_STATUSES / TERMINAL_RUN_STATUSES 保持一致：CANCELLED、FAILED、
PUBLISHED、OUTDATED 不占用唯一名额（允许失败重试与同输入重分析）。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 活动运行唯一约束的排除集：与 analysis.domain.ACTIVE_RUN_STATUSES 一致。
_TERMINAL_STATUSES = ("CANCELLED", "FAILED", "PUBLISHED", "OUTDATED")
_WHERE_CLAUSE = "status NOT IN ('CANCELLED', 'FAILED', 'PUBLISHED', 'OUTDATED')"

_INDEX_NAME = "uq_analysis_runs_active_project_input"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "analysis_runs",
        ["project_id", "input_fingerprint"],
        unique=True,
        postgresql_where=sa.text(_WHERE_CLAUSE),
        sqlite_where=sa.text(_WHERE_CLAUSE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="analysis_runs")

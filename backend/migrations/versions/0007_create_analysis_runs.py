"""create analysis_runs and analysis_run_inputs tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-23

analysis_runs 表：分析运行编排记录，status 与 completeness 为两个独立字段
（SPEC.md 第 5.3 节、ADR-011）；input_fingerprint 为不可变输入指纹（C-026）。
analysis_run_inputs 表：运行输入版本集合关系（运行 ↔ DocumentVersion），position
保留生效顺序；唯一约束防止同一版本在同一运行重复计入。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", name=op.f("fk_analysis_runs_project_id_projects")),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("completeness", sa.String(length=16), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(
        op.f("ix_analysis_runs_project_id"), "analysis_runs", ["project_id"]
    )
    op.create_index(
        op.f("ix_analysis_runs_input_fingerprint"),
        "analysis_runs",
        ["input_fingerprint"],
    )

    op.create_table(
        "analysis_run_inputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "analysis_run_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_runs.id", name=op.f("fk_analysis_run_inputs_run")),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            sa.Uuid(),
            sa.ForeignKey(
                "document_versions.id",
                name=op.f("fk_analysis_run_inputs_version"),
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_run_inputs")),
        sa.UniqueConstraint(
            "analysis_run_id",
            "document_version_id",
            name="uq_analysis_run_inputs_run_version",
        ),
    )
    op.create_index(
        op.f("ix_analysis_run_inputs_analysis_run_id"),
        "analysis_run_inputs",
        ["analysis_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_analysis_run_inputs_analysis_run_id"),
        table_name="analysis_run_inputs",
    )
    op.drop_table("analysis_run_inputs")
    op.drop_index(op.f("ix_analysis_runs_input_fingerprint"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_project_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")

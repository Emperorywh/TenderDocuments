"""analysis 模块 ORM Model（D-001 起）。

analysis_runs 表：一次完整分析运行的编排记录。运行状态（status）与完整性
（completeness）是两个独立字段，禁止用单字段混合（SPEC.md 第 5.3 节、ADR-011）。
input_fingerprint 为不可变输入指纹（C-026），用于输入去重与幂等；实际输入版本集合
由 analysis_run_inputs 子表显式表达“运行 ↔ 输入版本”关系。

analysis_run_inputs 表：运行输入版本集合关系。每条记录是一个
(analysis_run_id, document_version_id) 成员，position 保留生效顺序（C-023/C-025）。
唯一约束防止同一版本在同一运行中重复计入。

两表均通过 project_id 显式归属项目（SPEC.md 第 4.3 节），无身份字段。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from tender_insight.shared.orm import Base, TimestampMixin


class AnalysisRunModel(Base, TimestampMixin):
    """analysis_runs 表：分析运行编排记录。

    status 取 AnalysisRunStatus；completeness 取 AnalysisRunCompleteness 或 NULL
    （尚未计算）。input_fingerprint 经 C-026 算法计算，一经写入即不可变（运行输入
    集合的稳定标识）。
    """

    __tablename__ = "analysis_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # 显式归属项目；外键确保只允许引用已存在项目。
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id"),
        nullable=False,
    )
    # 运行状态机（AnalysisRunStatus），独立于完整性。
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    # 完整性（AnalysisRunCompleteness），独立于状态；运行完成前为 NULL。
    completeness: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 不可变输入指纹（C-026）：运行输入版本集合的稳定哈希。
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    # 运行发起时刻（业务时间，带时区）。
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AnalysisRunInputModel(Base):
    """analysis_run_inputs 表：运行输入版本集合关系（D-001）。

    一个运行包含多个输入版本成员；position 保留 C-023/C-025 计算的生效顺序。
    唯一约束保证同一版本在同一运行中只计入一次。
    """

    __tablename__ = "analysis_run_inputs"
    __table_args__ = (
        UniqueConstraint(
            "analysis_run_id",
            "document_version_id",
            name="uq_analysis_run_inputs_run_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    analysis_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analysis_runs.id"),
        nullable=False,
    )
    document_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_versions.id"),
        nullable=False,
    )
    # 输入版本在生效顺序中的位置（1-based，C-023/C-025）。
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

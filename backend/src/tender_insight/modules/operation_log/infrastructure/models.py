"""operation_log ORM Model（B-014）。

operation_logs 表为只追加审计记录。刻意：
- 不含身份字段（created_by/reviewed_by/organization_id 等），由 A-024 护栏保证；
- 不含 updated_at（记录永不更新，append-only 由数据库触发器强制）；
- 仅 occurred_at 记录发生时间。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from tender_insight.shared.orm import Base


class OperationLogModel(Base):
    """operation_logs 表 ORM Model（只追加）。"""

    __tablename__ = "operation_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # 请求追踪标识；无上下文时可为空（SPEC.md 第 6.2 节）。
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 动作，如 project.create / project.archive。
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    # 资源类型与 ID，如 ("project", "<uuid>")。
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 结果：success / failure。
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    # 失败时的稳定错误码。
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 发生时间；由数据库默认填充。
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

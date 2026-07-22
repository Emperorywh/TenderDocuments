"""operation_log SQLAlchemy 写入适配器（B-016）。

实现 OperationRecorder 端口，把 OperationRecord 写入 append-only 的
operation_logs 表。适配器只暂存 INSERT，不在内部提交；事务边界由调用用例控制
（成功记录与业务变更同事务提交；失败记录的独立提交策略见 B-017 集成）。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from tender_insight.modules.operation_log.application import OperationRecord
from tender_insight.modules.operation_log.infrastructure.models import OperationLogModel


class SqlAlchemyOperationRecorder:
    """OperationRecorder 端口的 SQLAlchemy 实现（只追加写入）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, operation: OperationRecord) -> None:
        # 直接构造 ORM 实例并暂存；occurred_at 由数据库默认填充。
        self._session.add(
            OperationLogModel(
                id=uuid4(),
                request_id=operation.request_id,
                action=operation.action,
                resource_type=operation.resource_type,
                resource_id=operation.resource_id,
                result=operation.result,
                error_code=operation.error_code,
            )
        )

"""任务心跳刷新（D-016）。

运行中的任务在执行期间定期刷新其当前 RUNNING 尝试的 heartbeat_at 时间戳。卡死任务
扫描（D-017）据此识别心跳过期（Worker 崩溃/卡死）的执行尝试并恢复（SPEC.md 第 12.2
节“心跳扫描恢复卡死任务”、第 11.2 节“重新执行必须生成新的 TaskAttempt”）。

心跳写在当前 RUNNING 尝试上（每次执行一条尝试，D-005/013）；无 RUNNING 尝试（任务未
运行或已终态）返回 False，调用方据此停止无效刷新。不在内部提交，随 Worker 心跳周期
短事务持久化。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import desc

from tender_insight.modules.analysis.infrastructure.models import TaskAttemptModel

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到签名。
    from sqlalchemy.orm import Session

# TaskAttempt 级执行状态（D-005）。
_ATTEMPT_RUNNING = "RUNNING"


def refresh_heartbeat(session: Session, task_id: UUID, *, now: datetime) -> bool:
    """刷新当前 RUNNING 尝试的 heartbeat_at；无 RUNNING 尝试返回 False。

    每次执行仅一条 RUNNING 尝试（D-013 领取创建、D-015 提交终结），取最新 RUNNING
    尝试刷新心跳。返回 True 表示已刷新，False 表示任务当前无运行尝试（不应再刷新）。
    """
    attempt = (
        session.query(TaskAttemptModel)
        .filter_by(analysis_task_id=task_id, status=_ATTEMPT_RUNNING)
        .order_by(desc(TaskAttemptModel.attempt_number))
        .first()
    )
    if attempt is None:
        return False
    attempt.heartbeat_at = now
    return True

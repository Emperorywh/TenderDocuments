"""analysis 应用层：用例编排、端口（仓储、任务投递、进度投影）。

D-013 增加任务执行领取结果 ClaimedExecution：Worker 原子领取执行权后获得的最小执行
上下文（稳定 ID 与 task_type），不暴露完整领域聚合（SPEC.md 第 7.2 节）。仅依赖
标准库，使 application/domain 不耦合 ORM。

D-014 增加经 DB 确认的任务归属 TaskOwnership；D-017 增加卡死任务识别结果 StuckTask。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ClaimedExecution:
    """已领取的任务执行上下文（Worker 据此执行原子任务，D-013）。

    task_id/analysis_run_id/project_id 为稳定归属标识（供 D-014 校验一致性）；
    task_type 决定执行分支；attempt_number 标识本次执行尝试（每次领取新建，D-005）。
    """

    task_id: UUID
    analysis_run_id: UUID
    project_id: UUID
    task_type: str
    attempt_number: int


@dataclass(frozen=True)
class TaskOwnership:
    """经 DB 校验的任务归属（D-014）。

    字段均来自数据库权威（非消息声称），Worker 据此执行，确保不信任消息中的孤立 ID
    （SPEC.md 第 4.3 节）。
    """

    task_id: UUID
    analysis_run_id: UUID
    project_id: UUID


@dataclass(frozen=True)
class StuckTask:
    """心跳过期的卡死任务（D-017）。

    当前 RUNNING 尝试的最近活动（heartbeat_at，无则 started_at）早于阈值，判定为
    Worker 卡死/崩溃。供 D-018 恢复（重新领取或失败转换）。last_activity 为判定依据。
    """

    task_id: UUID
    analysis_run_id: UUID
    project_id: UUID
    attempt_number: int
    last_activity: datetime


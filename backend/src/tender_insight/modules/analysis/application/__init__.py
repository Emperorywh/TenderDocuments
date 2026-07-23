"""analysis 应用层：用例编排、端口（仓储、任务投递、进度投影）。

D-013 增加任务执行领取结果 ClaimedExecution：Worker 原子领取执行权后获得的最小执行
上下文（稳定 ID 与 task_type），不暴露完整领域聚合（SPEC.md 第 7.2 节）。仅依赖
标准库，使 application/domain 不耦合 ORM。
"""

from __future__ import annotations

from dataclasses import dataclass
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

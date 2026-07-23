"""AnalysisTask 领域聚合（D-006）。

原子分析任务聚合，封装任务级状态机不变量。所有状态转换经 shared
state_transitions 集中校验，非法转换抛 InvalidTransitionError（映射 409）。

任务级状态（AnalysisTaskStatus）与执行尝试记录（TaskAttempt，D-005）分离：
每次执行/重试新增一条 attempt，任务状态按 PENDING→DISPATCHED→RUNNING→SUCCEEDED
（或 RETRY_SCHEDULED→DISPATCHED 重试、FAILED/CANCELLED 终态）演进
（SPEC.md 第 5.4 节）。

纯领域模型（标准库 + shared 纯值对象/状态机），不依赖 Web/ORM/队列/SDK。
"""

from __future__ import annotations

from dataclasses import dataclass

from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import validate_transition
from tender_insight.shared.states import AnalysisTaskStatus


@dataclass
class AnalysisTask:
    """原子分析任务聚合根。

    通过 create 工厂构造为 PENDING；状态命令就地变更 status。
    analysis_run_id 与 project_id 创建后只读，Worker 据此校验归属一致性。
    """

    id: Uuid
    analysis_run_id: Uuid
    project_id: Uuid
    task_type: str
    idempotency_key: str
    status: AnalysisTaskStatus

    def __post_init__(self) -> None:
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        if not self.task_type.strip():
            raise ValueError("任务类型不能为空")
        if not self.idempotency_key.strip():
            raise ValueError("任务幂等键不能为空")

    # ---- 工厂 ----

    @classmethod
    def create(
        cls,
        *,
        analysis_run_id: Uuid,
        project_id: Uuid,
        task_type: str,
        idempotency_key: str,
        task_id: Uuid | None = None,
    ) -> AnalysisTask:
        """创建 PENDING 任务。"""
        return cls(
            id=task_id if task_id is not None else Uuid.new(),
            analysis_run_id=analysis_run_id,
            project_id=project_id,
            task_type=task_type,
            idempotency_key=idempotency_key,
            status=AnalysisTaskStatus.PENDING,
        )

    # ---- 状态转换（集中校验，非法转换抛 InvalidTransitionError）----

    def _transition(self, target: AnalysisTaskStatus) -> None:
        validate_transition(AnalysisTaskStatus, self.status, target)
        self.status = target

    def dispatch(self) -> None:
        """PENDING/RETRY_SCHEDULED → DISPATCHED：任务已投递待执行。

        重试路径：RETRY_SCHEDULED → DISPATCHED 重新进入执行（SPEC.md 第 5.4 节）。
        """
        self._transition(AnalysisTaskStatus.DISPATCHED)

    def start(self) -> None:
        """DISPATCHED → RUNNING：Worker 已领取并开始执行。"""
        self._transition(AnalysisTaskStatus.RUNNING)

    def succeed(self) -> None:
        """RUNNING → SUCCEEDED：执行成功。"""
        self._transition(AnalysisTaskStatus.SUCCEEDED)

    def schedule_retry(self) -> None:
        """RUNNING → RETRY_SCHEDULED：可重试失败，安排重试（不覆盖旧尝试）。"""
        self._transition(AnalysisTaskStatus.RETRY_SCHEDULED)

    def fail(self) -> None:
        """DISPATCHED/RUNNING/RETRY_SCHEDULED → FAILED：不可重试失败，终态。"""
        self._transition(AnalysisTaskStatus.FAILED)

    def cancel(self) -> None:
        """活动状态 → CANCELLED：取消（未领取或协作停止）。"""
        self._transition(AnalysisTaskStatus.CANCELLED)

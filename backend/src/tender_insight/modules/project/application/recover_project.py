"""恢复待删除项目应用用例（B-013，B-017 接入操作记录）。

到期前可恢复：PENDING_DELETION → ACTIVE，并清除 pending_deletion_at。
超过保留期（30 天）则拒绝恢复（前置条件不满足）。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.modules.project.domain.project import pending_deletion_deadline
from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.errors import NotFoundError, PreconditionFailedError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context
from tender_insight.shared.states import ProjectLifecycleStatus


class RecoverProjectCommand(BaseModel):
    project_id: str


class RecoverProjectResult(BaseModel):
    project_id: str
    lifecycle_state: str


class RecoverProjectUseCase:
    def __init__(
        self,
        repository,
        session,
        session_factory: Callable[[], object] | None = None,
        open_recorder: Callable[[object], OperationRecorder] | None = None,
    ) -> None:
        self._repository = repository
        self._session = session
        self._session_factory = session_factory
        self._open_recorder = open_recorder

    def execute(
        self,
        command: RecoverProjectCommand,
        *,
        clock: Clock | None = None,
    ) -> RecoverProjectResult:
        ctx = current_request_context()

        def perform() -> RecoverProjectResult:
            project_id = Uuid.from_str(command.project_id)
            project = self._repository.get(project_id)
            if project is None:
                raise NotFoundError(f"项目不存在：{command.project_id}")
            if project.lifecycle_state != ProjectLifecycleStatus.PENDING_DELETION:
                project.recover_from_deletion()  # 触发非法转换异常
                raise PreconditionFailedError("项目不在待删除状态")
            assert project.pending_deletion_at is not None
            now = BusinessInstant.now(clock=clock).value
            if now >= pending_deletion_deadline(project.pending_deletion_at):
                raise PreconditionFailedError("项目已过待删除保留期，不可恢复")
            project.recover_from_deletion()
            self._repository.save(project)
            return RecoverProjectResult(
                project_id=str(project.id),
                lifecycle_state=project.lifecycle_state.value,
            )

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="project.recover",
            resource_type="project",
            resource_id=command.project_id,
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )

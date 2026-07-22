"""恢复归档项目应用用例（B-011，B-017 接入操作记录）。

将归档项目恢复为活动；恢复后字段与关联数据保持不变（SPEC.md 第 6.3 节）。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class RestoreProjectCommand(BaseModel):
    project_id: str


class RestoreProjectResult(BaseModel):
    project_id: str
    lifecycle_state: str


class RestoreProjectUseCase:
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

    def execute(self, command: RestoreProjectCommand) -> RestoreProjectResult:
        ctx = current_request_context()

        def perform() -> RestoreProjectResult:
            project_id = Uuid.from_str(command.project_id)
            project = self._repository.get(project_id)
            if project is None:
                raise NotFoundError(f"项目不存在：{command.project_id}")
            project.restore_from_archive()
            self._repository.save(project)
            return RestoreProjectResult(
                project_id=str(project.id),
                lifecycle_state=project.lifecycle_state.value,
            )

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="project.restore",
            resource_type="project",
            resource_id=command.project_id,
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )

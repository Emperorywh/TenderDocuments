"""归档项目应用用例（B-010，B-017 接入操作记录）。

归档使项目默认不出现在活动列表，但数据不删除、可恢复（SPEC.md 第 6.3 节）。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class ArchiveProjectCommand(BaseModel):
    project_id: str


class ArchiveProjectResult(BaseModel):
    project_id: str
    lifecycle_state: str
    archived: bool


class ArchiveProjectUseCase:
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

    def execute(self, command: ArchiveProjectCommand) -> ArchiveProjectResult:
        ctx = current_request_context()

        def perform() -> ArchiveProjectResult:
            project_id = Uuid.from_str(command.project_id)
            project = self._repository.get(project_id)
            if project is None:
                raise NotFoundError(f"项目不存在：{command.project_id}")
            project.archive()
            self._repository.save(project)
            return ArchiveProjectResult(
                project_id=str(project.id),
                lifecycle_state=project.lifecycle_state.value,
                archived=True,
            )

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="project.archive",
            resource_type="project",
            resource_id=command.project_id,
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )

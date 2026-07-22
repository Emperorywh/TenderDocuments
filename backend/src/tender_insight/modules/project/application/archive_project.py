"""归档项目应用用例（B-010）。

归档使项目默认不出现在活动列表，但数据不删除、可恢复（SPEC.md 第 6.3 节）。
"""

from __future__ import annotations

from pydantic import BaseModel

from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


class ArchiveProjectCommand(BaseModel):
    project_id: str


class ArchiveProjectResult(BaseModel):
    project_id: str
    lifecycle_state: str
    archived: bool


class ArchiveProjectUseCase:
    def __init__(self, repository, session) -> None:
        self._repository = repository
        self._session = session

    def execute(self, command: ArchiveProjectCommand) -> ArchiveProjectResult:
        project_id = Uuid.from_str(command.project_id)
        project = self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"项目不存在：{command.project_id}")
        project.archive()
        self._repository.save(project)
        self._session.commit()
        return ArchiveProjectResult(
            project_id=str(project.id),
            lifecycle_state=project.lifecycle_state.value,
            archived=True,
        )

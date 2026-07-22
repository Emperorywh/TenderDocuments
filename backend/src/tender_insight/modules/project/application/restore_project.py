"""恢复归档项目应用用例（B-011）。

将归档项目恢复为活动；恢复后字段与关联数据保持不变（SPEC.md 第 6.3 节）。
"""

from __future__ import annotations

from pydantic import BaseModel

from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


class RestoreProjectCommand(BaseModel):
    project_id: str


class RestoreProjectResult(BaseModel):
    project_id: str
    lifecycle_state: str


class RestoreProjectUseCase:
    def __init__(self, repository, session) -> None:
        self._repository = repository
        self._session = session

    def execute(self, command: RestoreProjectCommand) -> RestoreProjectResult:
        project_id = Uuid.from_str(command.project_id)
        project = self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"项目不存在：{command.project_id}")
        # 非法转换（如从 ACTIVE 恢复）由领域状态机拒绝。
        project.restore_from_archive()
        self._repository.save(project)
        self._session.commit()
        return RestoreProjectResult(
            project_id=str(project.id),
            lifecycle_state=project.lifecycle_state.value,
        )

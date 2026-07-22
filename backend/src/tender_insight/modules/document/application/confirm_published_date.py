"""文件发布日期确认用例（C-022）。

操作人员设置文件版本的发布日期；必须带时区（SPEC.md 第 6.4 节，A-008），
无时区或非法日期在领域层被拒绝。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from tender_insight.modules.document.application import DocumentVersionRepository
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


class ConfirmPublishedDateCommand(BaseModel):
    version_id: str
    published_at: datetime  # Pydantic v2 解析 ISO 字符串；时区在领域层校验


class ConfirmPublishedDateResult(BaseModel):
    version_id: str
    published_at: datetime


class ConfirmPublishedDateUseCase:
    def __init__(self, *, repository: DocumentVersionRepository, session) -> None:
        self._repository = repository
        self._session = session

    def execute(self, command: ConfirmPublishedDateCommand) -> ConfirmPublishedDateResult:
        version_id = Uuid.from_str(command.version_id)
        version = self._repository.get(version_id)
        if version is None:
            raise NotFoundError(f"文件版本不存在：{command.version_id}")
        # 领域层强制带时区：naive 抛 NaiveBusinessTimeError（稳定错误码）。
        version.set_published_date(command.published_at)
        self._repository.save(version)
        self._session.commit()
        return ConfirmPublishedDateResult(
            version_id=str(version.id),
            published_at=version.published_date,  # type: ignore[arg-type]
        )

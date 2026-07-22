"""文件业务类型确认用例（C-021）。

操作人员显式确认逻辑文件的业务类型（招标文件/澄清/补遗等）。未确认（OTHER）的
文件不进入分析输入集合（SPEC.md 第 6.4 节，C-025 校验）。
"""

from __future__ import annotations

from pydantic import BaseModel

from tender_insight.modules.document.application import DocumentRepository
from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


class ConfirmDocumentTypeCommand(BaseModel):
    """business_type 为枚举：非法值由 Pydantic 在边界拒绝（422 VALIDATION_ERROR）。"""

    document_id: str
    business_type: DocumentBusinessType


class ConfirmDocumentTypeResult(BaseModel):
    document_id: str
    business_type: str
    confirmed: bool


class ConfirmDocumentTypeUseCase:
    def __init__(self, *, repository: DocumentRepository, session) -> None:
        self._repository = repository
        self._session = session

    def execute(self, command: ConfirmDocumentTypeCommand) -> ConfirmDocumentTypeResult:
        document_id = Uuid.from_str(command.document_id)
        document = self._repository.get(document_id)
        if document is None:
            raise NotFoundError(f"文件不存在：{command.document_id}")

        document.confirm_business_type(command.business_type)
        self._repository.save(document)
        self._session.commit()
        return ConfirmDocumentTypeResult(
            document_id=str(document.id),
            business_type=document.business_type.value,
            confirmed=document.is_business_type_confirmed,
        )

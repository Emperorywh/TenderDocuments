"""文件业务类型确认用例（C-021，C-030 接入操作记录）。

操作人员显式确认逻辑文件的业务类型（招标文件/澄清/补遗等）。未确认（OTHER）的
文件不进入分析输入集合（SPEC.md 第 6.4 节，C-025 校验）。

每个命令恰好产生一条操作记录（成功同事务、失败独立事务），未注入录制器时跳过
记录，保持用例事务边界一致。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from tender_insight.modules.document.application import DocumentRepository
from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class ConfirmDocumentTypeCommand(BaseModel):
    """business_type 为枚举：非法值由 Pydantic 在边界拒绝（422 VALIDATION_ERROR）。"""

    document_id: str
    business_type: DocumentBusinessType


class ConfirmDocumentTypeResult(BaseModel):
    document_id: str
    business_type: str
    confirmed: bool


class ConfirmDocumentTypeUseCase:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        session,
        session_factory: Callable[[], object] | None = None,
        open_recorder: Callable[[object], OperationRecorder] | None = None,
    ) -> None:
        self._repository = repository
        self._session = session
        self._session_factory = session_factory
        self._open_recorder = open_recorder

    def execute(self, command: ConfirmDocumentTypeCommand) -> ConfirmDocumentTypeResult:
        document_id = Uuid.from_str(command.document_id)
        ctx = current_request_context()

        def perform() -> ConfirmDocumentTypeResult:
            document = self._repository.get(document_id)
            if document is None:
                raise NotFoundError(f"文件不存在：{command.document_id}")
            document.confirm_business_type(command.business_type)
            self._repository.save(document)
            return ConfirmDocumentTypeResult(
                document_id=str(document.id),
                business_type=document.business_type.value,
                confirmed=document.is_business_type_confirmed,
            )

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="document.confirm_type",
            resource_type="document",
            resource_id=str(document_id),
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )

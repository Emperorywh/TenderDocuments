"""文件替代/补充/引用关系命令（C-024，C-030 接入操作记录）。

创建文件间关系。校验：两文件同属一个项目（拒绝非法跨项目）、禁止自引用（数据库
CHECK 兜底）、REPLACES 关系不得形成环（循环替代被拒绝）。历史版本不被覆盖——关系
独立追加，不修改既有 DocumentVersion（SPEC.md 第 6.4 节）。

每个命令恰好产生一条操作记录（成功同事务、失败独立事务）。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from tender_insight.modules.document.application import (
    DocumentRelationRepository,
    DocumentRepository,
)
from tender_insight.modules.document.domain.document_types import DocumentRelationType
from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.shared.errors import ConflictError, NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class CreateDocumentRelationCommand(BaseModel):
    project_id: str
    source_document_id: str
    target_document_id: str
    relation_type: DocumentRelationType


class CreateDocumentRelationResult(BaseModel):
    relation_type: str
    source_document_id: str
    target_document_id: str


class CreateDocumentRelationUseCase:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        relation_repository: DocumentRelationRepository,
        session,
        session_factory: Callable[[], object] | None = None,
        open_recorder: Callable[[object], OperationRecorder] | None = None,
    ) -> None:
        self._documents = document_repository
        self._relations = relation_repository
        self._session = session
        self._session_factory = session_factory
        self._open_recorder = open_recorder

    def execute(self, command: CreateDocumentRelationCommand) -> CreateDocumentRelationResult:
        project_id = Uuid.from_str(command.project_id)
        source_id = Uuid.from_str(command.source_document_id)
        target_id = Uuid.from_str(command.target_document_id)
        ctx = current_request_context()

        def perform() -> CreateDocumentRelationResult:
            # 两文件须存在且同属该项目。
            source = self._documents.get(source_id)
            target = self._documents.get(target_id)
            if source is None or target is None:
                raise NotFoundError("源或目标文件不存在")
            if source.project_id != project_id or target.project_id != project_id:
                raise ConflictError("文件不属于该项目（非法跨项目关系）")
            if source_id == target_id:
                raise ConflictError("不允许自引用关系")

            # REPLACES 关系不得形成环：若 target 经现有 REPLACES 链可达 source，则拒绝。
            if command.relation_type == DocumentRelationType.REPLACES:
                self._assert_no_replaces_cycle(project_id, source_id, target_id)

            self._relations.add(
                project_id=project_id,
                source_document_id=source_id,
                target_document_id=target_id,
                relation_type=command.relation_type.value,
            )
            return CreateDocumentRelationResult(
                relation_type=command.relation_type.value,
                source_document_id=str(source_id),
                target_document_id=str(target_id),
            )

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="document.relation.create",
            resource_type="document",
            resource_id=str(source_id),
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )

    def _assert_no_replaces_cycle(
        self, project_id: Uuid, source_id: Uuid, target_id: Uuid
    ) -> None:
        """拟建 source→target；若 target 经现有 REPLACES 链可达 source，则成环。"""
        edges = self._relations.relations_in_project(
            project_id, relation_type=DocumentRelationType.REPLACES.value
        )
        adjacency: dict[Uuid, list[Uuid]] = {}
        for src, dst in edges:
            adjacency.setdefault(src, []).append(dst)
        # 从 target 出发能否到达 source。
        visited: set[Uuid] = set()
        stack = [target_id]
        while stack:
            node = stack.pop()
            if node == source_id:
                raise ConflictError("替代关系将形成循环")
            if node in visited:
                continue
            visited.add(node)
            stack.extend(adjacency.get(node, []))

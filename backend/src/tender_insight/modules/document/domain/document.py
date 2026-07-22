"""Document 领域实体（C-017 支撑）。

逻辑文件：一个项目下的一类招标材料（招标文件/澄清/补遗等）。逻辑文件有多个不可变
版本（DocumentVersion）。SPEC.md 第 6.4 节。
"""

from __future__ import annotations

from dataclasses import dataclass

from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.shared.identifiers import Uuid


@dataclass(frozen=True)
class Document:
    """逻辑文件聚合。"""

    id: Uuid
    project_id: Uuid
    business_type: DocumentBusinessType
    name: str

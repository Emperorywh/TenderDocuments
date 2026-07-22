"""Document 领域实体（C-017 支撑，C-021 业务类型确认）。

逻辑文件：一个项目下的一类招标材料（招标文件/澄清/补遗等）。逻辑文件有多个不可变
版本（DocumentVersion）。业务类型在上传完成时暂记为 OTHER，由操作人员显式确认
（SPEC.md 第 6.4 节）；未确认（OTHER）的文件不进入分析输入集合（C-025）。
"""

from __future__ import annotations

from dataclasses import dataclass

from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.shared.identifiers import Uuid

# 业务类型确认前的占位类型。
_UNCONFIRMED_TYPE = DocumentBusinessType.OTHER


@dataclass
class Document:
    """逻辑文件聚合。"""

    id: Uuid
    project_id: Uuid
    business_type: DocumentBusinessType
    name: str

    def confirm_business_type(self, business_type: DocumentBusinessType) -> None:
        """确认/修正文件业务类型。"""
        if not isinstance(business_type, DocumentBusinessType):
            raise ValueError(f"非法业务类型：{business_type!r}")
        self.business_type = business_type

    @property
    def is_business_type_confirmed(self) -> bool:
        """业务类型是否已确认（非 OTHER 占位）。"""
        return self.business_type != _UNCONFIRMED_TYPE

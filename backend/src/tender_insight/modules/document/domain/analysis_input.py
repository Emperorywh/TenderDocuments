"""分析输入版本集合计算（C-025）。

按 SPEC.md 第 6.4、9.4 节，确定进入分析的有效版本集合：仅业务类型已确认、状态为
有效（READY/PROCESSED）的版本；被 REPLACES 的文档整体排除；再按生效顺序稳定排序。

纯计算：固定版本图得到唯一有序集合（确定性）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tender_insight.modules.document.domain.effect_order import (
    EffectOrderInput,
    compute_effect_order,
)
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import DocumentVersionStatus

# 有效（可纳入分析）的版本状态。
_EFFECTIVE_STATUSES = frozenset(
    {DocumentVersionStatus.READY, DocumentVersionStatus.PROCESSED}
)


@dataclass(frozen=True)
class AnalysisVersionDescriptor:
    """参与分析输入集合计算的版本描述。"""

    version_id: Uuid
    document_id: Uuid
    business_type_confirmed: bool
    status: DocumentVersionStatus
    published_date: datetime | None
    version_number: int


def compute_analysis_input_set(
    descriptors: list[AnalysisVersionDescriptor],
    replaces: list[tuple[Uuid, Uuid]],
) -> list[Uuid]:
    """计算有序有效版本集合。

    replaces 为 (source_document_id, target_document_id) 列表：被替代的文档整体排除。
    返回按生效顺序排序的有效版本 ID 列表；确定性。
    """
    # 被替代的文档集合（target 文档的版本整体排除）。
    replaced_documents = {target for _source, target in replaces}

    effective = [
        d
        for d in descriptors
        if d.business_type_confirmed
        and d.status in _EFFECTIVE_STATUSES
        and d.document_id not in replaced_documents
    ]
    # 复用生效顺序排序（确定性）。
    order = compute_effect_order(
        [
            EffectOrderInput(
                version_id=d.version_id,
                published_date=d.published_date,
                version_number=d.version_number,
            )
            for d in effective
        ]
    )
    ordered = sorted(effective, key=lambda d: order[d.version_id])
    return [d.version_id for d in ordered]

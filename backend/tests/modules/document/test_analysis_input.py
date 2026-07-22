"""分析输入版本集合计算测试（C-025 独立验证）。

验证固定版本图得到唯一有序集合，且被替代/未确认/非有效状态版本被排除。
"""

from __future__ import annotations

from datetime import UTC, datetime

from tender_insight.modules.document.domain.analysis_input import (
    AnalysisVersionDescriptor,
    compute_analysis_input_set,
)
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import DocumentVersionStatus


def _desc(
    *,
    confirmed: bool = True,
    status: DocumentVersionStatus = DocumentVersionStatus.READY,
    date: datetime | None = None,
    version: int = 1,
    document_id: Uuid | None = None,
) -> AnalysisVersionDescriptor:
    return AnalysisVersionDescriptor(
        version_id=Uuid.new(),
        document_id=document_id or Uuid.new(),
        business_type_confirmed=confirmed,
        status=status,
        published_date=date,
        version_number=version,
    )


def test_fixed_graph_yields_unique_ordered_set() -> None:
    """固定版本图重复计算得到唯一有序集合。"""
    doc_a, doc_b = Uuid.new(), Uuid.new()
    a = _desc(date=datetime(2026, 7, 1, tzinfo=UTC), document_id=doc_a)
    b = _desc(date=datetime(2026, 7, 5, tzinfo=UTC), document_id=doc_b)

    result1 = compute_analysis_input_set([a, b], [])
    result2 = compute_analysis_input_set([b, a], [])
    assert result1 == result2
    # 更早发布的 a 在前。
    assert result1 == [a.version_id, b.version_id]


def test_unconfirmed_excluded() -> None:
    unconfirmed = _desc(confirmed=False)
    confirmed = _desc(confirmed=True)
    result = compute_analysis_input_set([unconfirmed, confirmed], [])
    assert result == [confirmed.version_id]


def test_non_effective_status_excluded() -> None:
    uploading = _desc(status=DocumentVersionStatus.UPLOADING)
    ready = _desc(status=DocumentVersionStatus.READY)
    result = compute_analysis_input_set([uploading, ready], [])
    assert result == [ready.version_id]


def test_replaced_document_excluded() -> None:
    """被 REPLACES 的文档整体排除。"""
    doc_a, doc_b = Uuid.new(), Uuid.new()
    a = _desc(document_id=doc_a)
    b = _desc(document_id=doc_b)
    # A 替代 B → B 的版本排除。
    result = compute_analysis_input_set([a, b], [(doc_a, doc_b)])
    assert result == [a.version_id]

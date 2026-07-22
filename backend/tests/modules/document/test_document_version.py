"""DocumentVersion 迁移与不可变性测试（C-015 独立验证）。

验证版本表存在、原始对象键/哈希等核心元数据不可被覆盖更新。
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from tender_insight.modules.document.domain.document_version import DocumentVersion
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import DocumentVersionStatus


def test_document_versions_table_structure(engine) -> None:
    inspector = inspect(engine)
    assert "document_versions" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("document_versions")}
    required = {
        "id",
        "document_id",
        "version_number",
        "original_object_key",
        "sha256",
        "size_bytes",
        "mime",
        "status",
        "canonical_object_key",
        "page_count",
    }
    assert required <= cols


def test_unique_version_number_per_document(engine) -> None:
    """同一逻辑文件内 (document_id, version_number) 唯一。"""
    inspector = inspect(engine)
    indexes = inspector.get_indexes("document_versions")
    assert any(
        idx["unique"] and set(idx["column_names"]) == {"document_id", "version_number"}
        for idx in indexes
    ), f"未找到唯一索引：{indexes}"


def test_core_fields_are_read_only() -> None:
    """核心原始元数据通过只读 property 暴露，无公开 setter。"""
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=Uuid.new(),
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=1024,
        mime="application/pdf",
    )
    assert version.original_object_key == "original/abc"
    assert version.sha256 == "a" * 64
    assert version.size_bytes == 1024
    # 核心 property 无 setter：赋值抛 AttributeError。
    with pytest.raises(AttributeError):
        version.original_object_key = "original/tampered"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        version.sha256 = "b" * 64  # type: ignore[misc]


def test_state_transitions_change_only_status_and_processing_fields() -> None:
    """状态机只改 status 与处理态，不改核心原始元数据。"""
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=Uuid.new(),
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=1024,
        mime="application/pdf",
    )
    core_snapshot = (version.original_object_key, version.sha256, version.size_bytes, version.mime)

    version.mark_stored()
    version.mark_validating()
    version.clear_security()
    version.mark_ready(canonical_object_key="canonical/abc", page_count=10)

    assert version.status == DocumentVersionStatus.READY
    assert version.canonical_object_key == "canonical/abc"
    assert version.page_count == 10
    # 核心原始元数据保持不变。
    assert (version.original_object_key, version.sha256, version.size_bytes, version.mime) == core_snapshot


def test_illegal_transition_rejected() -> None:
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=Uuid.new(),
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=1,
        mime="application/pdf",
    )
    from tender_insight.shared.state_transitions import InvalidTransitionError

    # VALIDATING -> VALIDATING 非法（状态机拒绝，不涉及安全门）。
    version.mark_stored()
    version.mark_validating()
    with pytest.raises(InvalidTransitionError):
        version.mark_validating()


def test_ready_requires_security_clearance() -> None:
    """未完成安全检查不能进入 READY（C-019 安全门）。"""
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=Uuid.new(),
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=1,
        mime="application/pdf",
    )
    version.mark_stored()
    version.mark_validating()
    # 未放行安全检查：mark_ready 被拒。
    with pytest.raises(PermissionError):
        version.mark_ready()
    assert version.status == DocumentVersionStatus.VALIDATING

    # 放行后可进入 READY。
    version.clear_security()
    version.mark_ready()
    assert version.status == DocumentVersionStatus.READY


def test_security_clearance_only_in_validating() -> None:
    """安全放行仅在 VALIDATING 状态允许。"""
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=Uuid.new(),
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=1,
        mime="application/pdf",
    )
    # UPLOADING 状态不允许放行。
    with pytest.raises(PermissionError):
        version.clear_security()

"""集中状态机目录测试（A-021 独立验证）。

验证六个状态机按 SPEC.md 定义齐全、各机内部状态唯一、状态机名称唯一，
且这些枚举类在全代码库中仅定义一次（无重复定义）。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tender_insight.shared import states as states_module
from tender_insight.shared.states import (
    STATE_MACHINES,
    AnalysisRunCompleteness,
    AnalysisRunStatus,
    AnalysisTaskStatus,
    DocumentVersionStatus,
    PageStatus,
    ReportSnapshotStatus,
    ReviewStatus,
)

# 预期状态机类名集合。
ENUM_CLASS_NAMES = {
    "DocumentVersionStatus",
    "PageStatus",
    "AnalysisRunStatus",
    "AnalysisRunCompleteness",
    "AnalysisTaskStatus",
    "ReviewStatus",
    "ReportSnapshotStatus",
}

# 各状态机按 SPEC.md 应包含的成员（值与名称一致）。
EXPECTED_MEMBERS: dict[type, set[str]] = {
    DocumentVersionStatus: {
        "UPLOADING", "STORED", "VALIDATING", "READY", "PROCESSING", "PROCESSED",
        "REJECTED", "UPLOAD_FAILED", "PROCESSING_FAILED",
    },
    PageStatus: {"PENDING", "NATIVE_TEXT_READY", "OCR_REQUIRED", "OCR_READY", "FAILED"},
    AnalysisRunStatus: {
        "DRAFT", "QUEUED", "PARSING", "EXTRACTING", "ANALYZING", "VERIFYING",
        "REVIEW_REQUIRED", "READY", "PUBLISHED", "CANCEL_REQUESTED", "CANCELLED",
        "FAILED", "OUTDATED",
    },
    AnalysisRunCompleteness: {"COMPLETE", "INCOMPLETE"},
    AnalysisTaskStatus: {
        "PENDING", "DISPATCHED", "RUNNING", "SUCCEEDED", "RETRY_SCHEDULED",
        "FAILED", "CANCELLED",
    },
    ReviewStatus: {
        "DETECTED", "NEEDS_REVIEW", "CONFIRMED", "MODIFIED", "REJECTED", "RESOLVED",
    },
    ReportSnapshotStatus: {"GENERATING", "AVAILABLE", "FAILED", "OUTDATED"},
}


@pytest.mark.parametrize("enum_cls,expected", list(EXPECTED_MEMBERS.items()))
def test_state_machine_members_match_spec(enum_cls: type, expected: set[str]) -> None:
    """每个状态机包含 SPEC.md 要求的全部状态。"""
    actual = {member.name for member in enum_cls}
    assert actual == expected, f"{enum_cls.__name__} 成员不匹配：缺 {expected - actual}，多 {actual - expected}"


def test_state_machine_names_are_unique() -> None:
    """注册表中状态机名称唯一，无重复键。"""
    machine_names = list(STATE_MACHINES)
    assert len(machine_names) == len(set(machine_names)), "状态机名称重复"


def test_each_machine_has_unique_member_names() -> None:
    """每个状态机内部成员名唯一（枚举保证，显式断言以锁定语义）。"""
    for machine_name, enum_cls in STATE_MACHINES.items():
        names = [m.name for m in enum_cls]
        assert len(names) == len(set(names)), f"{machine_name} 存在重复成员名"


def test_enum_classes_defined_only_once() -> None:
    """七个状态枚举类在全代码库中各只定义一次（无重复定义）。

    通过 AST 扫描 src 下所有 class 定义，断言每个状态枚举类名恰好出现一次，
    确保状态机目录是唯一权威来源，杜绝散落重定义。
    """
    src_root = Path(states_module.__file__).resolve().parent.parent
    occurrences: dict[str, list[Path]] = {name: [] for name in ENUM_CLASS_NAMES}
    for path in src_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in occurrences:
                occurrences[node.name].append(path)

    duplicates = {name: locs for name, locs in occurrences.items() if len(locs) != 1}
    assert not duplicates, f"状态枚举存在重复定义或缺失：{duplicates}"

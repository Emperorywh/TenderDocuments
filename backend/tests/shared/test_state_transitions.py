"""状态转换通用验证器测试（A-022 独立验证）。

验证合法转换通过、非法转换抛出稳定错误（INVALID_STATE_TRANSITION），
且 API 层将其映射为 409 Problem Details。
"""

from __future__ import annotations

from enum import StrEnum

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tender_insight.shared.errors import ErrorCode, add_problem_exception_handler
from tender_insight.shared.state_transitions import (
    InvalidTransitionError,
    is_valid_transition,
    validate_transition,
)
from tender_insight.shared.states import (
    AnalysisRunStatus,
    AnalysisTaskStatus,
    DocumentVersionStatus,
    ReviewStatus,
)


class _UnknownMachine(StrEnum):
    """仅用于测试：一个未登记到转换表的状态机。"""

    A = "A"
    B = "B"


def test_legal_transition_passes() -> None:
    """合法转换静默通过。"""
    validate_transition(DocumentVersionStatus, DocumentVersionStatus.UPLOADING, DocumentVersionStatus.STORED)
    validate_transition(AnalysisRunStatus, AnalysisRunStatus.READY, AnalysisRunStatus.PUBLISHED)
    validate_transition(AnalysisTaskStatus, AnalysisTaskStatus.RUNNING, AnalysisTaskStatus.SUCCEEDED)
    assert is_valid_transition(ReviewStatus, ReviewStatus.NEEDS_REVIEW, ReviewStatus.CONFIRMED)


@pytest.mark.parametrize(
    "machine,current,target",
    [
        (DocumentVersionStatus, DocumentVersionStatus.UPLOADING, DocumentVersionStatus.PROCESSED),
        (AnalysisRunStatus, AnalysisRunStatus.DRAFT, AnalysisRunStatus.PUBLISHED),
        (AnalysisTaskStatus, AnalysisTaskStatus.SUCCEEDED, AnalysisTaskStatus.RUNNING),
        (ReviewStatus, ReviewStatus.RESOLVED, ReviewStatus.CONFIRMED),
    ],
)
def test_illegal_transition_raises_stable_error(machine, current, target) -> None:
    """非法转换抛出 InvalidTransitionError，携带稳定错误码。"""
    with pytest.raises(InvalidTransitionError) as info:
        validate_transition(machine, current, target)
    assert info.value.code == "INVALID_STATE_TRANSITION"
    # 错误信息包含来源与目标，便于定位（不作为契约文本）。
    msg = str(info.value)
    assert current.value in msg
    assert target.value in msg


def test_unknown_machine_rejected() -> None:
    """未在转换表中登记的状态机（如完整性派生字段）拒绝校验。"""
    with pytest.raises(InvalidTransitionError):
        validate_transition(_UnknownMachine, _UnknownMachine.A, _UnknownMachine.B)


def test_api_maps_invalid_transition_to_409() -> None:
    """FastAPI 处理器把 InvalidTransitionError 映射为 409 Problem Details。"""
    app = FastAPI()

    @app.get("/transition")
    def _raise() -> None:
        validate_transition(
            DocumentVersionStatus,
            DocumentVersionStatus.UPLOADING,
            DocumentVersionStatus.PROCESSED,
        )

    add_problem_exception_handler(app)
    with TestClient(app) as client:
        response = client.get("/transition")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error_code"] == ErrorCode.INVALID_STATE_TRANSITION.value

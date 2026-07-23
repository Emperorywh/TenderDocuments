"""AnalysisRun 状态机领域测试（D-002 独立验证）。

验证每条合法路径可流转、非法跳转被拒绝，且完整性独立于状态。
"""

from __future__ import annotations

import pytest

from tender_insight.modules.analysis.domain.analysis_run import AnalysisRun
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import InvalidTransitionError
from tender_insight.shared.states import AnalysisRunCompleteness as _C
from tender_insight.shared.states import AnalysisRunStatus as _S


def _make_run() -> AnalysisRun:
    return AnalysisRun.create(
        project_id=Uuid.new(),
        input_fingerprint="a" * 64,
        input_version_ids=(Uuid.new(),),
    )


def test_create_is_draft() -> None:
    run = _make_run()
    assert run.status == _S.DRAFT
    assert run.completeness is None
    assert run.started_at is None


def test_happy_path_to_published_then_outdated() -> None:
    """主路径：DRAFT→QUEUED→…→READY→PUBLISHED→OUTDATED 全部可流转。"""
    run = _make_run()
    run.queue()
    run.start_parsing()
    run.start_extracting()
    run.start_analyzing()
    run.start_verifying()
    run.mark_ready(completeness=_C.COMPLETE)
    assert run.status == _S.READY
    assert run.completeness == _C.COMPLETE
    assert run.started_at is not None
    run.publish()
    assert run.status == _S.PUBLISHED
    run.mark_outdated()
    assert run.status == _S.OUTDATED


def test_verify_can_require_review() -> None:
    """VERIFYING → REVIEW_REQUIRED → READY 路径。"""
    run = _make_run()
    run.queue()
    run.start_parsing()
    run.start_extracting()
    run.start_analyzing()
    run.start_verifying()
    run.require_review()
    assert run.status == _S.REVIEW_REQUIRED
    run.mark_ready(completeness=_C.INCOMPLETE)
    assert run.status == _S.READY
    assert run.completeness == _C.INCOMPLETE


def test_draft_cannot_skip_to_parsing() -> None:
    """DRAFT 只能到 QUEUED（及取消/失败）；跳到 PARSING 非法。"""
    run = _make_run()
    with pytest.raises(InvalidTransitionError):
        run.start_parsing()
    # 合法：DRAFT → QUEUED。
    run.queue()
    assert run.status == _S.QUEUED


def test_draft_cannot_jump_to_ready() -> None:
    run = _make_run()
    with pytest.raises(InvalidTransitionError):
        run.mark_ready(completeness=_C.COMPLETE)


def test_publish_only_from_ready() -> None:
    """PUBLISHED 只能从 READY 进入；从 REVIEW_REQUIRED 直接发布非法。"""
    run = _make_run()
    run.queue()
    run.start_parsing()
    run.start_extracting()
    run.start_analyzing()
    run.start_verifying()
    run.require_review()
    with pytest.raises(InvalidTransitionError):
        run.publish()


def test_request_cancel_from_active_states() -> None:
    """活动状态均可请求取消进入 CANCEL_REQUESTED。"""
    for advance in (
        lambda r: None,  # DRAFT
        lambda r: r.queue(),
        lambda r: (r.queue(), r.start_parsing()),
        lambda r: (r.queue(), r.start_parsing(), r.start_extracting()),
    ):
        run = _make_run()
        advance(run)
        run.request_cancel()
        assert run.status == _S.CANCEL_REQUESTED
        run.confirm_cancelled()
        assert run.status == _S.CANCELLED


def test_cancel_requested_only_to_cancelled() -> None:
    """CANCEL_REQUESTED 只能到 CANCELLED，不能恢复到活动状态。"""
    run = _make_run()
    run.queue()
    run.request_cancel()
    with pytest.raises(InvalidTransitionError):
        run.start_parsing()  # 不能从 CANCEL_REQUESTED 继续解析


def test_mark_failed_from_active_states() -> None:
    """活动状态可失败进入 FAILED。"""
    run = _make_run()
    run.queue()
    run.start_parsing()
    run.mark_failed()
    assert run.status == _S.FAILED
    # 终态 FAILED 不可再转换。
    with pytest.raises(InvalidTransitionError):
        run.queue()


def test_terminal_states_cannot_transition() -> None:
    """终态（CANCELLED/FAILED/OUTDATED）不可再流转。"""
    run = _make_run()
    run.queue()
    run.request_cancel()
    run.confirm_cancelled()
    with pytest.raises(InvalidTransitionError):
        run.queue()
    with pytest.raises(InvalidTransitionError):
        run.request_cancel()


def test_published_only_to_outdated() -> None:
    """PUBLISHED 只能到 OUTDATED，不能回到 READY 或其它。"""
    run = _make_run()
    run.queue()
    run.start_parsing()
    run.start_extracting()
    run.start_analyzing()
    run.start_verifying()
    run.mark_ready(completeness=_C.COMPLETE)
    run.publish()
    with pytest.raises(InvalidTransitionError):
        run.mark_ready(completeness=_C.COMPLETE)
    run.mark_outdated()
    with pytest.raises(InvalidTransitionError):
        run.publish()


def test_completeness_independent_of_status() -> None:
    """完整性独立字段：可在未到 READY 时设置，不改变状态。"""
    run = _make_run()
    run.queue()
    run.start_parsing()
    run.set_completeness(_C.INCOMPLETE)
    assert run.completeness == _C.INCOMPLETE
    assert run.status == _S.PARSING  # 状态未变


def test_empty_fingerprint_rejected() -> None:
    with pytest.raises(ValueError):
        AnalysisRun.create(
            project_id=Uuid.new(),
            input_fingerprint="  ",
            input_version_ids=(Uuid.new(),),
        )


def test_empty_input_versions_rejected() -> None:
    with pytest.raises(ValueError):
        AnalysisRun.create(
            project_id=Uuid.new(),
            input_fingerprint="a" * 64,
            input_version_ids=(),
        )


def test_input_versions_immutable_tuple() -> None:
    """输入版本集合以元组保存（不可变）。"""
    v = Uuid.new()
    run = AnalysisRun.create(
        project_id=Uuid.new(),
        input_fingerprint="a" * 64,
        input_version_ids=[v],
    )
    assert run.input_version_ids == (v,)

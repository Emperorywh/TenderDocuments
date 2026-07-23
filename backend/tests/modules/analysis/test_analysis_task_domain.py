"""AnalysisTask 状态机领域测试（D-006 独立验证）。

验证任务状态转换的合法路径与非法跳转，覆盖重试、失败与取消边界。
"""

from __future__ import annotations

import pytest

from tender_insight.modules.analysis.domain.analysis_task import AnalysisTask
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import InvalidTransitionError
from tender_insight.shared.states import AnalysisTaskStatus as _S


def _make_task() -> AnalysisTask:
    return AnalysisTask.create(
        analysis_run_id=Uuid.new(),
        project_id=Uuid.new(),
        task_type="parse",
        idempotency_key="k1",
    )


def test_create_is_pending() -> None:
    task = _make_task()
    assert task.status == _S.PENDING


def test_happy_path_to_succeeded() -> None:
    """PENDING → DISPATCHED → RUNNING → SUCCEEDED。"""
    task = _make_task()
    task.dispatch()
    task.start()
    task.succeed()
    assert task.status == _S.SUCCEEDED


def test_retry_path() -> None:
    """重试路径：RUNNING → RETRY_SCHEDULED → DISPATCHED → RUNNING → SUCCEEDED。"""
    task = _make_task()
    task.dispatch()
    task.start()
    task.schedule_retry()
    assert task.status == _S.RETRY_SCHEDULED
    task.dispatch()  # 重新投递
    task.start()
    task.succeed()
    assert task.status == _S.SUCCEEDED


def test_retry_scheduled_can_fail_directly() -> None:
    """RETRY_SCHEDULED 也可直接失败（不再重试）。"""
    task = _make_task()
    task.dispatch()
    task.start()
    task.schedule_retry()
    task.fail()
    assert task.status == _S.FAILED


@pytest.mark.parametrize("from_method", ["dispatch", "start"])
def test_fail_from_dispatched_or_running(from_method: str) -> None:
    """DISPATCHED 与 RUNNING 均可失败。"""
    task = _make_task()
    task.dispatch()
    if from_method == "start":
        task.start()
    task.fail()
    assert task.status == _S.FAILED


def test_cancel_from_each_active_state() -> None:
    """PENDING/DISPATCHED/RUNNING/RETRY_SCHEDULED 均可取消。"""
    for advance in (
        lambda t: None,
        lambda t: t.dispatch(),
        lambda t: (t.dispatch(), t.start()),
        lambda t: (t.dispatch(), t.start(), t.schedule_retry()),
    ):
        task = _make_task()
        advance(task)
        task.cancel()
        assert task.status == _S.CANCELLED


def test_pending_cannot_skip_to_running() -> None:
    """PENDING 只能到 DISPATCHED（或取消）；跳到 RUNNING 非法。"""
    task = _make_task()
    with pytest.raises(InvalidTransitionError):
        task.start()


def test_running_cannot_go_back_to_pending() -> None:
    task = _make_task()
    task.dispatch()
    task.start()
    with pytest.raises(InvalidTransitionError):
        task.dispatch()


def test_succeeded_is_terminal() -> None:
    """SUCCEEDED 为终态，不可再转换。"""
    task = _make_task()
    task.dispatch()
    task.start()
    task.succeed()
    for action in (task.dispatch, task.start, task.succeed, task.fail, task.cancel):
        with pytest.raises(InvalidTransitionError):
            action()


def test_failed_is_terminal() -> None:
    """FAILED 为终态，不可再转换。"""
    task = _make_task()
    task.dispatch()
    task.start()
    task.fail()
    with pytest.raises(InvalidTransitionError):
        task.schedule_retry()


def test_cancelled_is_terminal() -> None:
    """CANCELLED 为终态，不可再转换。"""
    task = _make_task()
    task.dispatch()
    task.cancel()
    with pytest.raises(InvalidTransitionError):
        task.start()


def test_succeed_only_from_running() -> None:
    """SUCCEEDED 只能从 RUNNING 进入。"""
    task = _make_task()
    task.dispatch()
    with pytest.raises(InvalidTransitionError):
        task.succeed()


def test_schedule_retry_only_from_running() -> None:
    """RETRY_SCHEDULED 只能从 RUNNING 进入。"""
    task = _make_task()
    task.dispatch()
    with pytest.raises(InvalidTransitionError):
        task.schedule_retry()


def test_empty_task_type_or_key_rejected() -> None:
    with pytest.raises(ValueError):
        AnalysisTask.create(
            analysis_run_id=Uuid.new(),
            project_id=Uuid.new(),
            task_type="  ",
            idempotency_key="k",
        )
    with pytest.raises(ValueError):
        AnalysisTask.create(
            analysis_run_id=Uuid.new(),
            project_id=Uuid.new(),
            task_type="parse",
            idempotency_key="",
        )

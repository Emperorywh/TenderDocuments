"""Celery 资源队列路由测试（D-012 独立验证）。

验证各 task_type 进入唯一预期队列（convert/parse/ocr/extract/risk/report），OCR 独立
队列，未知 task_type 不被静默错路由，以及 Celery 应用工厂正确声明队列与路由。
"""

from __future__ import annotations

import pytest
from celery import Celery
from kombu import Queue

from tender_insight.workers.celery_app import create_celery_app
from tender_insight.workers.queues import (
    ALL_QUEUE_NAMES,
    DEFAULT_QUEUE,
    DEFAULT_WORKER_QUEUE_NAMES,
    OCR_QUEUE_NAME,
    QUEUE_NAMES,
    TASK_TYPE_QUEUE,
    AnalysisTaskType,
    UnknownTaskTypeError,
    extract_task_type,
    queue_for_task_type,
    route_for_task,
    route_message,
)

# 各 task_type 的预期队列（唯一映射）。
_EXPECTED_QUEUES = {
    AnalysisTaskType.CONVERT: "convert",
    AnalysisTaskType.PARSE: "parse",
    AnalysisTaskType.OCR: "ocr",
    AnalysisTaskType.EXTRACT: "extract",
    AnalysisTaskType.RISK: "risk",
    AnalysisTaskType.REPORT: "report",
}


def test_each_task_type_enters_unique_expected_queue() -> None:
    """核心验证：各 task_type 进入唯一预期队列。"""
    for task_type, expected_queue in _EXPECTED_QUEUES.items():
        assert queue_for_task_type(task_type.value) == expected_queue
    # 路由表与预期完全一致。
    assert {k.value: v for k, v in TASK_TYPE_QUEUE.items()} == _EXPECTED_QUEUES


def test_queue_mapping_is_bijective() -> None:
    """task_type → 队列 一一对应：无两个 task_type 共享队列。"""
    queues = [queue_for_task_type(t.value) for t in AnalysisTaskType]
    assert len(queues) == len(set(queues)) == len(list(AnalysisTaskType))


def test_unknown_task_type_rejected() -> None:
    """未知 task_type 不被静默错路由（避免任务丢失或进错 worker）。"""
    with pytest.raises(UnknownTaskTypeError):
        queue_for_task_type("nonexistent")


def test_route_message_unknown_task_type_raises() -> None:
    """route_message 对未知 task_type 抛错（不静默走默认队列）。"""
    with pytest.raises(UnknownTaskTypeError):
        route_message(task_type="bogus")


def test_route_message_without_task_type_uses_default() -> None:
    """无 task_type 的非任务事件走默认队列（如 report.outdated）。"""
    assert route_message(task_type=None) == {"queue": DEFAULT_QUEUE}


def test_ocr_is_distinct_queue() -> None:
    """OCR 独立队列（供 worker-ocr），不与普通任务队列混用（SPEC.md 第 12.1 节）。"""
    assert OCR_QUEUE_NAME == "ocr"
    assert OCR_QUEUE_NAME not in DEFAULT_WORKER_QUEUE_NAMES
    # worker-default 消费其余 5 个队列。
    assert set(DEFAULT_WORKER_QUEUE_NAMES) == {
        "convert",
        "parse",
        "extract",
        "risk",
        "report",
    }
    assert len(DEFAULT_WORKER_QUEUE_NAMES) == 5


def test_extract_task_type_from_top_level_or_payload() -> None:
    """提取 task_type 支持顶层 kwargs 与 payload 内嵌两种约定。"""
    assert extract_task_type({"task_type": "ocr"}) == "ocr"
    assert extract_task_type({"payload": {"task_type": "parse"}}) == "parse"
    assert extract_task_type({"payload": {"event": "x"}}) is None
    assert extract_task_type(None) is None


def test_route_for_task_routes_by_kwargs() -> None:
    """Celery callable router 按消息 kwargs 路由到唯一队列。"""
    assert route_for_task("worker.any", kwargs={"task_type": "ocr"}) == {"queue": "ocr"}
    assert route_for_task("worker.any", kwargs={"payload": {"task_type": "risk"}}) == {
        "queue": "risk"
    }
    # 无 task_type 走默认队列。
    assert route_for_task("worker.any", kwargs={"payload": {"event": "x"}}) == {
        "queue": DEFAULT_QUEUE
    }


def test_create_celery_app_declares_queues_and_routes() -> None:
    """Celery 应用工厂声明全部队列并注册 task_type 路由。"""
    app = create_celery_app("memory://", backend_url=None)

    assert isinstance(app, Celery)
    # 全部队列被声明（含默认队列）。
    declared = {q.name for q in app.conf.task_queues if isinstance(q, Queue)}
    assert declared == set(ALL_QUEUE_NAMES)
    assert DEFAULT_QUEUE in declared
    # 6 个 task_type 队列全部声明。
    assert set(QUEUE_NAMES) <= declared
    # 注册了 callable 路由。
    assert route_for_task in tuple(app.conf.task_routes)
    assert app.conf.task_default_queue == DEFAULT_QUEUE

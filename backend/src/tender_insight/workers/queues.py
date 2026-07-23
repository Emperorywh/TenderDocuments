"""Celery 资源队列路由配置（D-012）。

定义分析任务类型（task_type）到 Celery 队列的权威路由表：每个 task_type 进入唯一
预期队列（验证：各 task_type 进入唯一预期队列）。队列按资源特征分区——OCR 独立队列
供 worker-ocr 消费（PaddleOCR CPU/GPU 密集，SPEC.md 第 12.1 节、PLAN.md 第 13.1
节），convert/parse/extract/risk/report 由 worker-default 消费。

路由表是 task_type→队列的唯一权威来源（PLAN.md 第 14 节“无重复逻辑”）；具体 task
名称、队列消费者（-Q）与并发度由部署配置（阶段 K）与各 worker 任务（后续 D 任务）
绑定，不在本模块硬编码。
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum


class AnalysisTaskType(StrEnum):
    """分析任务类型，值同时作为 AnalysisTask.task_type 与队列名（D-012）。

    对应 SPEC.md 第 5 章主流程的原子阶段：DOCX 转换、解析、OCR、抽取、风险、报告。
    """

    CONVERT = "convert"  # DOCX→标准化 PDF
    PARSE = "parse"  # PDF 原生文本与坐标提取
    OCR = "ocr"  # OCR（独立 worker-ocr）
    EXTRACT = "extract"  # 知识与候选抽取
    RISK = "risk"  # 规则与风险分析
    REPORT = "report"  # 报告快照与 PDF 渲染


# task_type → 队列名 的权威路由表（单一来源）。
# 每个 task_type 进入唯一队列；值与 task_type 一致，使路由可由 task_type 唯一确定。
TASK_TYPE_QUEUE: dict[AnalysisTaskType, str] = {
    AnalysisTaskType.CONVERT: "convert",
    AnalysisTaskType.PARSE: "parse",
    AnalysisTaskType.OCR: "ocr",
    AnalysisTaskType.EXTRACT: "extract",
    AnalysisTaskType.RISK: "risk",
    AnalysisTaskType.REPORT: "report",
}

# 全部任务队列名（按 task_type 声明，供 Celery task_queues 与 worker -Q 消费）。
QUEUE_NAMES: tuple[str, ...] = tuple(TASK_TYPE_QUEUE.values())

# OCR 独立队列（worker-ocr 消费）；其余归 worker-default（SPEC.md 第 12.1 节）。
OCR_QUEUE_NAME: str = TASK_TYPE_QUEUE[AnalysisTaskType.OCR]
DEFAULT_WORKER_QUEUE_NAMES: tuple[str, ...] = tuple(
    queue for queue in QUEUE_NAMES if queue != OCR_QUEUE_NAME
)

# 非 task 事件（如 report.outdated 等无 task_type 的事件）投递的默认队列。
DEFAULT_QUEUE: str = "default"
# 含默认队列在内的全部队列（供 Celery 声明）。
ALL_QUEUE_NAMES: tuple[str, ...] = (DEFAULT_QUEUE, *QUEUE_NAMES)


class UnknownTaskTypeError(ValueError):
    """未知 task_type：不应静默错路由到任意队列（避免任务丢失或错 worker）。"""


def queue_for_task_type(task_type: str) -> str:
    """返回 task_type 对应的唯一队列名；未知 task_type 抛 UnknownTaskTypeError。"""
    try:
        key = AnalysisTaskType(task_type)
    except ValueError as exc:
        raise UnknownTaskTypeError(f"未知 task_type: {task_type!r}") from exc
    return TASK_TYPE_QUEUE[key]


def extract_task_type(kwargs: dict | None) -> str | None:
    """从消息 kwargs 提取 task_type（支持顶层或 payload 内嵌两种约定）。

    outbox 投递的 analysis task 事件 payload 含 task_type；部分非 outbox 直发任务
    也可在顶层携带 task_type。无 task_type 返回 None（走默认队列）。
    """
    if not kwargs:
        return None
    top_level = kwargs.get("task_type")
    if isinstance(top_level, str):
        return top_level
    payload = kwargs.get("payload")
    if isinstance(payload, dict):
        nested = payload.get("task_type")
        if isinstance(nested, str):
            return nested
    return None


def route_message(*, task_type: str | None) -> dict[str, str]:
    """根据 task_type 返回 Celery 路由 {"queue": ...}；无 task_type 走默认队列。

    有 task_type 时经 queue_for_task_type 路由到唯一队列（未知抛 UnknownTaskTypeError，
    不静默错路由）；无 task_type 的事件（非任务事件）走 default 队列。
    """
    if task_type is None:
        return {"queue": DEFAULT_QUEUE}
    return {"queue": queue_for_task_type(task_type)}


def route_for_task(  # noqa: ANN201 - Celery callable router 约定签名，返回路由字典。
    name: str,
    args: tuple | list | None = None,
    kwargs: dict | None = None,
    options: dict | None = None,
    task: object | None = None,
    **kw: object,
) -> dict[str, str]:
    """Celery 自定义路由（callable router）。

    Celery 在 send_task/apply_async 时调用本函数，按消息 kwargs 中的 task_type 路由
    到唯一队列。与 route_message 共用同一权威逻辑（无重复实现）。
    """
    _ = (name, args, options, task, kw)  # 签名占位：Celery 约定参数，本路由不使用。
    return route_message(task_type=extract_task_type(kwargs))


# Celery task_routes 接受 callable 路由；显式标注类型便于阅读与静态检查。
CELERY_TASK_ROUTES: tuple[Callable[..., dict[str, str]]] = (route_for_task,)

"""operation_log 应用层端口（B-015）。

定义 OperationRecorder 端口与 OperationRecord 数据结构。端口刻意保持纯
（仅标准库），使任意模块的应用用例可在不依赖日志库或 ORM 的情况下记录关键
操作（SPEC.md 第 6.2 节、PLAN.md 第 3.3 节“operation_log 通过应用端口接收
关键操作事件”）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OperationRecord:
    """一次关键操作的不可变记录数据。

    不含用户身份字段（ADR-014）。result 为 success/failure；error_code 仅失败时
    填写稳定错误码。request_id 关联请求追踪上下文（可为空）。
    """

    action: str
    resource_type: str
    resource_id: str
    result: str
    error_code: str | None = None
    request_id: str | None = None


class OperationRecorder(Protocol):
    """操作记录端口：由基础设施实现（如写入 append-only 表）。"""

    def record(self, operation: OperationRecord) -> None:
        """记录一次关键操作。"""
        ...

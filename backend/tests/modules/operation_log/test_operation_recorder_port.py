"""操作记录端口测试（B-015 独立验证）。

验证 OperationRecorder 端口为纯接口，领域/应用层不依赖日志库或 ORM。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tender_insight.modules.operation_log.application import (
    OperationRecord,
    OperationRecorder,
)


def test_port_module_is_framework_free() -> None:
    """端口模块仅依赖标准库，不导入 ORM/日志库/Web 框架。"""
    port_file = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "tender_insight"
        / "modules"
        / "operation_log"
        / "application"
        / "__init__.py"
    )
    tree = ast.parse(port_file.read_text(encoding="utf-8"))
    forbidden = {"sqlalchemy", "fastapi", "starlette", "celery", "redis", "structlog", "logging"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & forbidden), f"端口模块依赖了框架：{imported & forbidden}"


def test_operation_record_is_immutable_dataclass() -> None:
    record = OperationRecord(
        action="project.create",
        resource_type="project",
        resource_id="abc",
        result="success",
    )
    assert record.error_code is None
    assert record.request_id is None
    # frozen：不可变。
    try:
        record.result = "failure"  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("OperationRecord 应为不可变")


def test_recorder_protocol_is_implementable() -> None:
    """端口可被任意实现满足（结构化类型）。"""

    class RecordingRecorder:
        def __init__(self) -> None:
            self.calls: list[OperationRecord] = []

        def record(self, operation: OperationRecord) -> None:
            self.calls.append(operation)

    recorder: OperationRecorder = RecordingRecorder()
    recorder.record(
        OperationRecord(
            action="project.delete",
            resource_type="project",
            resource_id="x",
            result="failure",
            error_code="NOT_FOUND",
        )
    )
    assert len(recorder.calls) == 1  # type: ignore[attr-defined]
    assert recorder.calls[0].error_code == "NOT_FOUND"  # type: ignore[attr-defined]

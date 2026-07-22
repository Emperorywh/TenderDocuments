"""操作记录写入适配器测试（B-016 独立验证）。

验证固定请求能记录动作、资源、时间、结果与错误码。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from tender_insight.modules.operation_log.application import OperationRecord
from tender_insight.modules.operation_log.infrastructure.models import OperationLogModel
from tender_insight.modules.operation_log.infrastructure.recorder import (
    SqlAlchemyOperationRecorder,
)


def test_record_success_persists_all_fields(db_session: Session) -> None:
    """成功操作记录动作/资源/时间/结果齐全。"""
    recorder = SqlAlchemyOperationRecorder(db_session)
    recorder.record(
        OperationRecord(
            action="project.create",
            resource_type="project",
            resource_id="proj-1",
            result="success",
            request_id="req-1",
        )
    )
    db_session.commit()

    rows = db_session.query(OperationLogModel).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "project.create"
    assert row.resource_type == "project"
    assert row.resource_id == "proj-1"
    assert row.result == "success"
    assert row.request_id == "req-1"
    assert row.error_code is None
    # 时间由数据库默认填充。
    assert row.occurred_at is not None


def test_record_failure_includes_error_code(db_session: Session) -> None:
    """失败操作记录稳定错误码。"""
    recorder = SqlAlchemyOperationRecorder(db_session)
    recorder.record(
        OperationRecord(
            action="project.create",
            resource_type="project",
            resource_id="proj-2",
            result="failure",
            error_code="INVALID_PROJECT_DATA",
            request_id="req-2",
        )
    )
    db_session.commit()

    row = db_session.query(OperationLogModel).one()
    assert row.result == "failure"
    assert row.error_code == "INVALID_PROJECT_DATA"


def test_recorder_does_not_commit_internally(db_session: Session, session_factory) -> None:
    """适配器不在内部提交；未提交前新会话查询不到。"""
    recorder = SqlAlchemyOperationRecorder(db_session)
    recorder.record(
        OperationRecord(
            action="project.archive",
            resource_type="project",
            resource_id="proj-3",
            result="success",
        )
    )
    # 未提交：另起会话查询应看不到。
    other = session_factory()
    try:
        assert other.query(OperationLogModel).count() == 0
    finally:
        other.close()

    # 提交后即可见。
    db_session.commit()
    other2 = session_factory()
    try:
        assert other2.query(OperationLogModel).count() == 1
    finally:
        other2.close()

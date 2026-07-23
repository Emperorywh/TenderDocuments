"""事务 Outbox 写入测试（D-008 独立验证）。

验证事件在业务事务内写入，业务事务提交时事件持久化、回滚时事件同步回滚（不留孤儿）。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from tender_insight.modules.outbox.application import OutboxEvent, OutboxWriter
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel
from tender_insight.modules.outbox.infrastructure.outbox_writer import (
    SqlAlchemyOutboxWriter,
)


def _event(event_id: str = "evt-1") -> OutboxEvent:
    return OutboxEvent(
        event_id=event_id,
        event_type="analysis.task.dispatched",
        aggregate_type="analysis_task",
        aggregate_id="task-1",
        payload={"task_id": "task-1", "queue": "parse"},
    )


def test_port_is_pure_protocol() -> None:
    """端口模块不依赖 ORM/队列 SDK（A-006 守护：application 不导入 sqlalchemy）。"""
    from pathlib import Path

    import tender_insight.modules.outbox.application as app_mod

    source = Path(app_mod.__file__).read_text(encoding="utf-8")
    assert "sqlalchemy" not in source
    # OutboxEvent 不可变；OutboxWriter 为 Protocol（结构性满足由下面的用例验证）。
    event = _event()
    assert event.event_id == "evt-1"
    assert isinstance(event.payload, dict)


def test_writer_implements_protocol(db_session: Session) -> None:
    """SqlAlchemyOutboxWriter 满足 OutboxWriter 端口（结构性）。"""
    writer: OutboxWriter = SqlAlchemyOutboxWriter(db_session)  # type: ignore[assignment]
    writer.write(_event())
    db_session.commit()
    assert db_session.query(OutboxEventModel).count() == 1


def test_event_persisted_on_commit(db_session: Session) -> None:
    """业务事务提交时事件持久化，字段正确。"""
    SqlAlchemyOutboxWriter(db_session).write(_event("evt-commit"))
    db_session.commit()
    row = db_session.query(OutboxEventModel).filter_by(event_id="evt-commit").one()
    assert row.event_type == "analysis.task.dispatched"
    assert row.delivery_status == "PENDING"
    assert row.attempts == 0
    assert row.payload == {"task_id": "task-1", "queue": "parse"}


def test_event_rolled_back_with_business_transaction(db_session: Session) -> None:
    """业务事务回滚时事件同步回滚，不留孤儿事件。"""
    SqlAlchemyOutboxWriter(db_session).write(_event("evt-rollback"))
    # 回滚业务事务（模拟业务变更失败）。
    db_session.rollback()
    assert db_session.query(OutboxEventModel).filter_by(event_id="evt-rollback").count() == 0


def test_writer_does_not_commit_internally(session_factory) -> None:
    """写入不在内部提交：新会话在提交前查不到事件。"""
    event = _event("evt-no-commit")
    session = session_factory()
    try:
        SqlAlchemyOutboxWriter(session).write(event)
        # 未提交前，新会话查不到。
        other = session_factory()
        try:
            assert other.query(OutboxEventModel).filter_by(event_id="evt-no-commit").count() == 0
        finally:
            other.close()
        session.commit()
        # 提交后新会话可见。
        other2 = session_factory()
        try:
            assert other2.query(OutboxEventModel).filter_by(event_id="evt-no-commit").count() == 1
        finally:
            other2.close()
    finally:
        session.close()

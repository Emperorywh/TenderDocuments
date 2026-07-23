"""OutboxEvent 迁移测试（D-007 独立验证）。

验证事务事件表结构、无身份字段，唯一业务事件 ID 约束可阻止重复事件。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_outbox_events_table_structure(engine) -> None:
    """outbox_events 表存在且含核心列，无身份字段。"""
    inspector = inspect(engine)
    assert "outbox_events" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("outbox_events")}
    required = {
        "id",
        "event_id",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "payload",
        "delivery_status",
        "attempts",
    }
    assert required <= cols
    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by"}
    assert not (forbidden & cols)


def test_event_id_unique_constraint_exists(engine) -> None:
    """event_id 唯一约束存在。"""
    inspector = inspect(engine)
    uniques = inspector.get_unique_constraints("outbox_events")
    assert any(
        col == "event_id" for u in uniques for col in u["column_names"]
    ), f"未找到 event_id 唯一约束：{uniques}"


def test_duplicate_event_id_rejected(session_factory) -> None:
    """相同业务事件 ID 不产生重复行（幂等投递基础）。"""
    from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel

    session = session_factory()
    try:
        event_id = "evt-0001"
        session.execute(
            OutboxEventModel.__table__.insert().values(
                id=uuid4(),
                event_id=event_id,
                event_type="analysis.task.dispatched",
                aggregate_type="analysis_task",
                aggregate_id=str(uuid4()),
                payload={"task_id": "t1"},
                delivery_status="PENDING",
                attempts=0,
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(
                OutboxEventModel.__table__.insert().values(
                    id=uuid4(),
                    event_id=event_id,  # 相同业务事件 ID
                    event_type="analysis.task.dispatched",
                    aggregate_type="analysis_task",
                    aggregate_id=str(uuid4()),
                    payload={"task_id": "t2"},
                    delivery_status="PENDING",
                    attempts=0,
                )
            )
            session.commit()
    finally:
        session.close()


def test_distinct_event_ids_allowed(session_factory) -> None:
    """不同业务事件 ID 可并存。"""
    from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel

    session = session_factory()
    try:
        for n in range(3):
            session.execute(
                OutboxEventModel.__table__.insert().values(
                    id=uuid4(),
                    event_id=f"evt-{n}",
                    event_type="analysis.task.dispatched",
                    aggregate_type="analysis_task",
                    aggregate_id=str(uuid4()),
                    payload={"n": n},
                    delivery_status="PENDING",
                    attempts=0,
                )
            )
        session.commit()
    finally:
        session.close()


def test_payload_json_roundtrip(session_factory) -> None:
    """payload 以 JSON 承载消息信封，可完整回读。"""
    from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel

    session = session_factory()
    try:
        row_id = uuid4()
        payload = {"task_id": "t1", "queue": "parse", "trace_id": "tr-1"}
        session.execute(
            OutboxEventModel.__table__.insert().values(
                id=row_id,
                event_id="evt-payload",
                event_type="analysis.task.dispatched",
                aggregate_type="analysis_task",
                aggregate_id="agg-1",
                payload=payload,
                delivery_status="PENDING",
                attempts=0,
            )
        )
        session.commit()
        row = session.execute(
            OutboxEventModel.__table__.select().where(
                OutboxEventModel.__table__.c.id == row_id
            )
        ).one()
        assert row.payload == payload
    finally:
        session.close()

"""operation_log 迁移与 append-only 约束测试（B-014 独立验证）。

验证 operation_logs 表存在、结构正确、无身份字段，且既有记录无法被
UPDATE/DELETE（数据库触发器强制只追加）。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, update
from sqlalchemy.exc import IntegrityError

from tender_insight.modules.operation_log.infrastructure.models import OperationLogModel


def _insert_one(session) -> None:
    session.execute(
        insert(OperationLogModel).values(
            id=uuid4(),
            action="project.create",
            resource_type="project",
            resource_id=str(uuid4()),
            result="success",
        )
    )
    session.commit()


def test_operation_logs_table_exists(engine) -> None:
    from sqlalchemy import inspect

    inspector = inspect(engine)
    assert "operation_logs" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("operation_logs")}
    required = {
        "id",
        "request_id",
        "action",
        "resource_type",
        "resource_id",
        "result",
        "error_code",
        "occurred_at",
    }
    assert required <= cols
    # 不含身份字段。
    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by", "tenant_id"}
    assert not (cols & forbidden)


def test_append_succeeds(session_factory) -> None:
    """新增记录成功。"""
    session = session_factory()
    try:
        _insert_one(session)
        assert session.query(OperationLogModel).count() == 1
    finally:
        session.close()


def test_update_is_forbidden(session_factory) -> None:
    """既有记录无法被 UPDATE（触发器阻止）。"""
    log_id = uuid4()
    session = session_factory()
    try:
        session.execute(
            insert(OperationLogModel).values(
                id=log_id,
                action="project.create",
                resource_type="project",
                resource_id=str(uuid4()),
                result="success",
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(
                update(OperationLogModel)
                .where(OperationLogModel.id == log_id)
                .values(result="failure")
            )
            session.commit()
    finally:
        session.close()


def test_delete_is_forbidden(session_factory) -> None:
    """既有记录无法被 DELETE（触发器阻止）。"""
    log_id = uuid4()
    session = session_factory()
    try:
        session.execute(
            insert(OperationLogModel).values(
                id=log_id,
                action="project.create",
                resource_type="project",
                resource_id=str(uuid4()),
                result="success",
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(delete(OperationLogModel).where(OperationLogModel.id == log_id))
            session.commit()
    finally:
        session.close()

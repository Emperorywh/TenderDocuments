"""UploadSession 迁移测试（C-006 独立验证）。

验证 upload_sessions 表存在、归属项目外键、过期时间字段；过期会话的接入约束在
完成用例（C-017）中由应用层强制，本测试覆盖表结构与迁移可运行。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import inspect


def test_upload_sessions_table_structure(engine) -> None:
    inspector = inspect(engine)
    assert "upload_sessions" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("upload_sessions")}
    required = {
        "id",
        "project_id",
        "declared_filename",
        "declared_size_bytes",
        "declared_mime",
        "object_key",
        "status",
        "created_at",
        "expires_at",
        "completed_at",
    }
    assert required <= cols
    # 不含身份字段。
    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by", "tenant_id"}
    assert not (cols & forbidden)


def test_project_fk_present(engine) -> None:
    """upload_sessions.project_id 引用 projects(id)。"""
    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("upload_sessions")
    assert any(
        fk["referred_table"] == "projects" and "project_id" in (fk["constrained_columns"] or [])
        for fk in fks
    ), f"未找到 project_id -> projects 外键：{fks}"


def test_can_persist_session_with_expiry(session_factory) -> None:
    """可写入带过期时间的会话；过期字段为必填。"""
    from tender_insight.modules.document.infrastructure.models import UploadSessionModel

    session = session_factory()
    try:
        now = datetime(2026, 7, 23, tzinfo=UTC)
        session.execute(
            UploadSessionModel.__table__.insert().values(
                id=uuid4(),
                project_id=uuid4(),
                declared_filename="tender.pdf",
                declared_size_bytes=1024,
                declared_mime="application/pdf",
                object_key="quarantine/abc",
                status="PENDING",
                expires_at=now + timedelta(minutes=15),
            )
        )
        session.commit()
    finally:
        session.close()

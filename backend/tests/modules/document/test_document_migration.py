"""Document 迁移测试（C-014 独立验证）。

验证 documents 表存在、必须归属 project_id（外键非空）、无身份字段。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_documents_table_structure(engine) -> None:
    inspector = inspect(engine)
    assert "documents" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("documents")}
    required = {"id", "project_id", "business_type", "name", "created_at", "updated_at"}
    assert required <= cols
    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by", "tenant_id"}
    assert not (cols & forbidden)


def test_project_id_fk_to_projects(engine) -> None:
    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("documents")
    assert any(
        fk["referred_table"] == "projects" and "project_id" in (fk["constrained_columns"] or [])
        for fk in fks
    ), f"未找到 project_id -> projects 外键：{fks}"


def test_document_requires_existing_project(session_factory) -> None:
    """Document 必须归属一个存在的 project_id（外键约束）。"""
    from tender_insight.modules.document.infrastructure.models import DocumentModel

    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            session.execute(
                DocumentModel.__table__.insert().values(
                    id=uuid4(),
                    project_id=uuid4(),  # 不存在的项目
                    business_type="TENDER_DOC",
                    name="tender.pdf",
                )
            )
            session.commit()
    finally:
        session.close()

"""DocumentRelation 迁移测试（C-016 独立验证）。

验证关系表存在、自引用被约束拒绝；跨项目非法关系由应用用例（C-024）校验。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_relations_table_structure(engine) -> None:
    inspector = inspect(engine)
    assert "document_relations" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("document_relations")}
    required = {
        "id",
        "project_id",
        "source_document_id",
        "target_document_id",
        "relation_type",
    }
    assert required <= cols


def test_self_reference_check_constraint(engine) -> None:
    """CHECK 约束拒绝 source == target 的自引用。"""
    inspector = inspect(engine)
    constraints = inspector.get_check_constraints("document_relations")
    assert any(
        "source_document_id" in c["sqltext"] and "target_document_id" in c["sqltext"]
        for c in constraints
    ), f"未找到禁止自引用 CHECK：{constraints}"


def test_self_reference_insert_rejected(session_factory) -> None:
    """插入自引用关系被数据库拒绝。"""
    from tender_insight.modules.document.infrastructure.models import (
        DocumentModel,
        DocumentRelationModel,
    )
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    session = session_factory()
    try:
        project_id = uuid4()
        doc_id = uuid4()
        session.execute(
            ProjectModel.__table__.insert().values(
                id=project_id,
                name="p",
                region="成都",
                industry="房建",
                project_type="施工",
                lifecycle_state="ACTIVE",
                version=1,
            )
        )
        session.execute(
            DocumentModel.__table__.insert().values(
                id=doc_id, project_id=project_id, business_type="TENDER_DOC", name="t.pdf"
            )
        )
        with pytest.raises(IntegrityError):
            session.execute(
                DocumentRelationModel.__table__.insert().values(
                    id=uuid4(),
                    project_id=project_id,
                    source_document_id=doc_id,
                    target_document_id=doc_id,  # 自引用
                    relation_type="REPLACES",
                )
            )
            session.commit()
    finally:
        session.close()

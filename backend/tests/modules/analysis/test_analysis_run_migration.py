"""AnalysisRun 迁移测试（D-001 独立验证）。

验证分析运行表与输入集合关系表结构正确、无身份字段，且一个运行可保存不可变
输入指纹与有序输入版本集合。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from tender_insight.modules.document.domain.input_fingerprint import compute_input_fingerprint


def test_analysis_runs_table_structure(engine) -> None:
    """analysis_runs 表存在且含核心列，无身份字段。"""
    inspector = inspect(engine)
    assert "analysis_runs" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("analysis_runs")}
    required = {"id", "project_id", "status", "completeness", "input_fingerprint"}
    assert required <= cols
    # 无身份字段（organization_id/user_id/created_by 等）。
    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by"}
    assert not (forbidden & cols)


def test_status_and_completeness_independent_columns(engine) -> None:
    """status 与 completeness 为两个独立列（ADR-011，禁止单字段混合）。"""
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("analysis_runs")}
    assert "status" in cols
    assert "completeness" in cols
    # completeness 可空（运行完成前未计算）。
    completeness = next(c for c in inspector.get_columns("analysis_runs") if c["name"] == "completeness")
    assert completeness.get("nullable") is True


def test_analysis_run_inputs_table_structure(engine) -> None:
    """输入集合关系表存在且含运行与版本外键。"""
    inspector = inspect(engine)
    assert "analysis_run_inputs" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("analysis_run_inputs")}
    assert {"analysis_run_id", "document_version_id", "position"} <= cols


def test_project_id_references_projects(session_factory) -> None:
    """analysis_runs.project_id 外键引用 projects。"""
    from tender_insight.modules.analysis.infrastructure.models import AnalysisRunModel

    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            session.execute(
                AnalysisRunModel.__table__.insert().values(
                    id=uuid4(),
                    project_id=uuid4(),  # 不存在的项目
                    status="DRAFT",
                    input_fingerprint="a" * 64,
                )
            )
            session.commit()
    finally:
        session.close()


def test_run_persists_immutable_input_fingerprint(session_factory) -> None:
    """一个运行保存不可变输入指纹与输入版本集合关系。"""
    from tender_insight.modules.analysis.infrastructure.models import (
        AnalysisRunInputModel,
        AnalysisRunModel,
    )
    from tender_insight.modules.document.infrastructure.models import (
        DocumentModel,
        DocumentVersionModel,
    )
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    session = session_factory()
    try:
        project_id = uuid4()
        doc_id = uuid4()
        v1 = uuid4()
        v2 = uuid4()
        session.execute(
            ProjectModel.__table__.insert().values(
                id=project_id, name="p", region="成都", industry="房建",
                project_type="施工", lifecycle_state="ACTIVE", version=1,
            )
        )
        session.execute(
            DocumentModel.__table__.insert().values(
                id=doc_id, project_id=project_id, business_type="TENDER_DOC", name="t.pdf"
            )
        )
        for vid, num in ((v1, 1), (v2, 2)):
            session.execute(
                DocumentVersionModel.__table__.insert().values(
                    id=vid, document_id=doc_id, version_number=num,
                    original_object_key=f"original/{vid}", sha256=f"{vid}" * 4,
                    size_bytes=10, mime="application/pdf", status="READY",
                )
            )

        # 用 C-026 算法计算真实指纹。
        fingerprint = compute_input_fingerprint(
            [(str(v1), f"{v1}" * 4), (str(v2), f"{v2}" * 4)]
        )
        run_id = uuid4()
        session.execute(
            AnalysisRunModel.__table__.insert().values(
                id=run_id, project_id=project_id, status="DRAFT",
                input_fingerprint=fingerprint,
            )
        )
        # 输入版本集合关系（保留生效顺序）。
        for pos, vid in enumerate((v1, v2), start=1):
            session.execute(
                AnalysisRunInputModel.__table__.insert().values(
                    id=uuid4(), analysis_run_id=run_id,
                    document_version_id=vid, position=pos,
                )
            )
        session.commit()

        # 回读：指纹不可变地保存，输入集合有序。
        run = session.execute(
            AnalysisRunModel.__table__.select().where(
                AnalysisRunModel.__table__.c.id == run_id
            )
        ).one()
        assert run.input_fingerprint == fingerprint
        assert run.status == "DRAFT"
        assert run.completeness is None

        inputs = (
            session.execute(
                AnalysisRunInputModel.__table__.select()
                .where(AnalysisRunInputModel.__table__.c.analysis_run_id == run_id)
                .order_by(AnalysisRunInputModel.__table__.c.position)
            )
            .all()
        )
        assert [row.document_version_id for row in inputs] == [v1, v2]
    finally:
        session.close()


def test_unique_run_version_constraint(session_factory) -> None:
    """同一版本在同一运行中只能计入一次。"""
    from tender_insight.modules.analysis.infrastructure.models import (
        AnalysisRunInputModel,
        AnalysisRunModel,
    )
    from tender_insight.modules.document.infrastructure.models import (
        DocumentModel,
        DocumentVersionModel,
    )
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    session = session_factory()
    try:
        project_id = uuid4()
        doc_id = uuid4()
        vid = uuid4()
        run_id = uuid4()
        session.execute(
            ProjectModel.__table__.insert().values(
                id=project_id, name="p", region="成都", industry="房建",
                project_type="施工", lifecycle_state="ACTIVE", version=1,
            )
        )
        session.execute(
            DocumentModel.__table__.insert().values(
                id=doc_id, project_id=project_id, business_type="TENDER_DOC", name="t.pdf"
            )
        )
        session.execute(
            DocumentVersionModel.__table__.insert().values(
                id=vid, document_id=doc_id, version_number=1,
                original_object_key=f"original/{vid}", sha256="a" * 64,
                size_bytes=10, mime="application/pdf", status="READY",
            )
        )
        session.execute(
            AnalysisRunModel.__table__.insert().values(
                id=run_id, project_id=project_id, status="DRAFT", input_fingerprint="a" * 64,
            )
        )
        session.execute(
            AnalysisRunInputModel.__table__.insert().values(
                id=uuid4(), analysis_run_id=run_id, document_version_id=vid, position=1,
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(
                AnalysisRunInputModel.__table__.insert().values(
                    id=uuid4(), analysis_run_id=run_id, document_version_id=vid, position=2,
                )
            )
            session.commit()
    finally:
        session.close()

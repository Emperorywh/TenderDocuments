"""创建项目用例测试（B-004 独立验证）。

验证最小合法输入成功、缺少必填字段失败。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectUseCase,
)
from tender_insight.modules.project.domain.exceptions import InvalidProjectDataError
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)


def _use_case(session: Session) -> CreateProjectUseCase:
    return CreateProjectUseCase(SqlAlchemyProjectRepository(session), session)


def test_minimal_legal_input_succeeds(db_session: Session) -> None:
    """最小合法输入创建成功并落库。"""
    result = _use_case(db_session).execute(
        CreateProjectCommand(
            name="天府新区房建",
            region="成都",
            industry="房屋建筑工程",
            project_type="施工",
        )
    )
    assert result.project_id
    assert result.name == "天府新区房建"
    # 已提交，回读存在。
    from tender_insight.shared.identifiers import Uuid

    fetched = SqlAlchemyProjectRepository(db_session).get(Uuid.from_str(result.project_id))
    assert fetched is not None
    assert fetched.name == "天府新区房建"


@pytest.mark.parametrize("payload_override", [
    {"name": ""},
    {"region": ""},
    {"industry": ""},
    {"project_type": ""},
])
def test_missing_required_field_fails(db_session: Session, payload_override) -> None:
    """必填字段为空被拒绝（Pydantic min_length 或领域非空校验）。"""
    base = {"name": "p", "region": "成都", "industry": "房建", "project_type": "施工"}
    base.update(payload_override)
    # Pydantic min_length=1 拒绝空串。
    with pytest.raises(ValidationError):
        CreateProjectCommand(**base)


def test_whitespace_only_rejected_by_domain(db_session: Session) -> None:
    """空白字符串通过 Pydantic 但被领域非空不变量拒绝，且不提交。"""
    # 用空格绕过 min_length（空格长度>=1），构造命令后由领域拒绝。
    command = CreateProjectCommand(
        name="   ",
        region="成都",
        industry="房建",
        project_type="施工",
    )
    with pytest.raises(InvalidProjectDataError):
        _use_case(db_session).execute(command)
    # 失败不落库：项目表无任何记录。
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    assert db_session.query(ProjectModel).count() == 0

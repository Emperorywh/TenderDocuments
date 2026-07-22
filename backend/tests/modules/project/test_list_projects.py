"""项目列表投影测试（B-008 独立验证）。

验证排序与翻页稳定，且查询不写领域表。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectUseCase,
)
from tender_insight.modules.project.application.list_projects import list_projects
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.pagination import PageRequest, SortDirection, SortField


def _seed(session: Session, names: list[str]) -> None:
    use_case = CreateProjectUseCase(SqlAlchemyProjectRepository(session), session)
    for name in names:
        use_case.execute(
            CreateProjectCommand(name=name, region="成都", industry="房建", project_type="施工")
        )


def test_pagination_is_stable(db_session: Session) -> None:
    """翻页稳定：跨页无重叠、无遗漏。"""
    _seed(db_session, ["A", "B", "C", "D", "E"])
    seen: list[str] = []
    for page in (1, 2):
        result = list_projects(db_session, PageRequest(page=page, page_size=2))
        seen.extend(item.name for item in result.items)
    # 5 条，每页 2，共 3 页；取前两页 4 条应互不重复。
    assert len(seen) == len(set(seen)) == 4
    assert result.total == 5


def test_sort_by_name_ascending(db_session: Session) -> None:
    _seed(db_session, ["Charlie", "Alpha", "Bravo"])
    result = list_projects(
        db_session,
        PageRequest(page=1, page_size=10, sort=[SortField(field="name")]),
    )
    assert [i.name for i in result.items] == ["Alpha", "Bravo", "Charlie"]


def test_sort_by_name_descending(db_session: Session) -> None:
    _seed(db_session, ["Charlie", "Alpha", "Bravo"])
    result = list_projects(
        db_session,
        PageRequest(
            page=1,
            page_size=10,
            sort=[SortField(field="name", direction=SortDirection.DESC)],
        ),
    )
    assert [i.name for i in result.items] == ["Charlie", "Bravo", "Alpha"]


def test_default_excludes_archived(db_session: Session) -> None:
    """归档项目默认不出现在活动列表。"""
    _seed(db_session, ["Active1", "Active2"])
    repo = SqlAlchemyProjectRepository(db_session)
    from tender_insight.shared.identifiers import Uuid

    first = list_projects(db_session, PageRequest(page=1, page_size=10)).items[0]
    project = repo.get(Uuid.from_str(first.project_id))
    assert project is not None
    project.archive(clock=_fixed_clock())
    repo.save(project)
    db_session.commit()

    result = list_projects(db_session, PageRequest(page=1, page_size=10))
    # 归档后活动列表只剩 1 个，且是被归档项目之外的另一个。
    assert result.total == 1
    assert result.items[0].name != first.name


def _fixed_clock():
    class _Clock:
        def now(self) -> datetime:
            return datetime(2026, 7, 23, tzinfo=UTC)

    return _Clock()


def test_projection_does_not_write(db_session: Session) -> None:
    """只读投影不写领域表：调用前后记录数不变。"""
    _seed(db_session, ["X", "Y"])
    before = db_session.query(ProjectModel).count()
    list_projects(db_session, PageRequest(page=1, page_size=10))
    list_projects(db_session, PageRequest(page=1, page_size=2, sort=[SortField(field="name")]))
    after = db_session.query(ProjectModel).count()
    assert before == after == 2

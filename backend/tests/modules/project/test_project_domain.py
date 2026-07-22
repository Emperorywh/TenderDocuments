"""Project 聚合领域测试（B-002 独立验证）。

验证非法字段与非法状态转换被领域层拒绝。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tender_insight.modules.project.domain.exceptions import InvalidProjectDataError
from tender_insight.modules.project.domain.project import Project
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import InvalidTransitionError
from tender_insight.shared.states import ProjectLifecycleStatus


def _fixed_clock(at: datetime):
    class _Clock:
        def now(self) -> datetime:
            return at

    return _Clock()


def test_create_active_project() -> None:
    project = Project.create(
        name="天府新区房建项目",
        region="成都",
        industry="房屋建筑工程",
        project_type="施工",
    )
    assert project.lifecycle_state == ProjectLifecycleStatus.ACTIVE
    assert project.version == 1
    assert isinstance(project.id, Uuid)


@pytest.mark.parametrize(
    "kwargs,field_hint",
    [
        ({"name": " ", "region": "成都", "industry": "房建", "project_type": "施工"}, "名称"),
        ({"name": "x", "region": " ", "industry": "房建", "project_type": "施工"}, "地区"),
        ({"name": "x", "region": "成都", "industry": " ", "project_type": "施工"}, "行业"),
        ({"name": "x", "region": "成都", "industry": "房建", "project_type": " "}, "类型"),
    ],
)
def test_invalid_fields_rejected(kwargs: dict, field_hint: str) -> None:
    """非法（空）字段在创建时被拒绝。"""
    with pytest.raises(InvalidProjectDataError) as info:
        Project.create(**kwargs)
    assert field_hint in str(info.value)


def test_archive_and_restore() -> None:
    project = Project.create(name="p", region="成都", industry="房建", project_type="施工")
    project.archive(clock=_fixed_clock(datetime(2026, 7, 23, tzinfo=UTC)))
    assert project.lifecycle_state == ProjectLifecycleStatus.ARCHIVED
    assert project.archived_at is not None
    assert project.version == 2

    project.restore_from_archive()
    assert project.lifecycle_state == ProjectLifecycleStatus.ACTIVE
    assert project.version == 3


def test_request_deletion_recover_and_purge() -> None:
    project = Project.create(name="p", region="成都", industry="房建", project_type="施工")
    project.request_deletion(clock=_fixed_clock(datetime(2026, 7, 23, tzinfo=UTC)))
    assert project.lifecycle_state == ProjectLifecycleStatus.PENDING_DELETION
    assert project.pending_deletion_at is not None

    project.recover_from_deletion()
    assert project.lifecycle_state == ProjectLifecycleStatus.ACTIVE
    assert project.pending_deletion_at is None

    project.request_deletion(clock=_fixed_clock(datetime(2026, 7, 23, tzinfo=UTC)))
    project.purge(clock=_fixed_clock(datetime(2026, 8, 25, tzinfo=UTC)))
    assert project.lifecycle_state == ProjectLifecycleStatus.DELETED
    assert project.deleted_at is not None


def test_illegal_transition_purge_from_active_rejected() -> None:
    """未请求删除不能直接清除。"""
    project = Project.create(name="p", region="成都", industry="房建", project_type="施工")
    with pytest.raises(InvalidTransitionError):
        project.purge()


def test_illegal_transition_archive_from_deleted_rejected() -> None:
    project = Project.create(name="p", region="成都", industry="房建", project_type="施工")
    project.request_deletion(clock=_fixed_clock(datetime(2026, 7, 23, tzinfo=UTC)))
    project.purge(clock=_fixed_clock(datetime(2026, 8, 25, tzinfo=UTC)))
    with pytest.raises(InvalidTransitionError):
        project.archive()


def test_update_details_increments_version_and_validates() -> None:
    project = Project.create(name="p", region="成都", industry="房建", project_type="施工")
    project.update_details(name="新名称")
    assert project.name == "新名称"
    assert project.version == 2

    # 非法字段在编辑时同样被拒绝。
    with pytest.raises(InvalidProjectDataError):
        project.update_details(name="   ")
    # 部分更新失败不应改变 version 或字段。
    assert project.name == "新名称"
    assert project.version == 2

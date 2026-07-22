"""project 模块应用层。

承载用例编排与端口声明。ProjectRepository 端口在此声明，由 infrastructure
实现；application 不依赖具体 ORM。
"""

from __future__ import annotations

from typing import Protocol

from tender_insight.modules.project.domain.project import Project
from tender_insight.shared.identifiers import Uuid


class ProjectRepository(Protocol):
    """项目仓储端口。

    application 只依赖该抽象；具体实现（SQLAlchemy）在 infrastructure 层。
    所有读取均按 project_id 范围进行，不提供无归属范围的扫描接口（SPEC.md
    第 5.3 节：项目内查询显式接收 project_id）。
    """

    def add(self, project: Project) -> None:
        """新增项目。"""
        ...

    def get(self, project_id: Uuid) -> Project | None:
        """按项目 ID 读取；不存在返回 None。"""
        ...

    def save(self, project: Project) -> None:
        """保存项目变更（乐观并发在 B-006 强化）。"""
        ...

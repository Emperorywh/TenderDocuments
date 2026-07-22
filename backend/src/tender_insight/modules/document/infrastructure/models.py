"""document 模块 ORM Model（C-006 起）。

upload_sessions 表：上传完成前的暂态会话（SPEC.md 第 8.3 节）。会话过期后不能
完成正式接入（成为 DocumentVersion）。表通过 project_id 显式归属项目，无身份字段。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from tender_insight.shared.orm import Base, TimestampMixin


class UploadSessionModel(Base):
    """upload_sessions 表 ORM Model。"""

    __tablename__ = "upload_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # 显式归属项目；外键确保只允许引用已存在项目。
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id"), nullable=False
    )
    declared_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_mime: Mapped[str] = mapped_column(String(128), nullable=False)
    # 暂存对象键（quarantine 分区），不含可猜测原始文件名。
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 过期时间：超过则不能完成正式接入。
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DocumentModel(Base, TimestampMixin):
    """documents 表：逻辑文件（招标文件/澄清/补遗/附件等）。

    一个项目下有多个逻辑文件；每个逻辑文件有多个不可变版本（DocumentVersion，
    C-015）。逻辑文件必须归属一个 project_id（SPEC.md 第 4.3、6.4 节）。
    """

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id"),
        nullable=False,
    )
    # 业务类型（DocumentBusinessType 取值）。
    business_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class DocumentVersionModel(Base, TimestampMixin):
    """document_versions 表：不可变文件版本（C-015）。

    核心原始元数据（original_object_key/sha256/size_bytes/mime/version_number/
    document_id）一经创建不可覆盖更新；仅 status、canonical_object_key、page_count
    等处理态字段可演进（SPEC.md 第 5.2、6.4 节）。
    """

    __tablename__ = "document_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # 原始对象键（original 分区），不可变。
    original_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    # 处理态字段（可演进）。
    canonical_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effect_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


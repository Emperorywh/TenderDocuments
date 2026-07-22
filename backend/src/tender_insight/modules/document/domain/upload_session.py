"""UploadSession 领域实体（C-007 支撑）。

上传会话是“上传完成前”的暂态：记录声明元数据与暂存对象键，带过期时间；过期
会话不能完成正式接入（SPEC.md 第 8.3 节）。状态转换经集中校验，非法转换被拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import validate_transition
from tender_insight.shared.states import UploadSessionStatus


@dataclass
class UploadSession:
    """上传会话聚合。"""

    id: Uuid
    project_id: Uuid
    declared_filename: str
    declared_size_bytes: int
    declared_mime: str
    object_key: str
    status: UploadSessionStatus
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        project_id: Uuid,
        declared_filename: str,
        declared_size_bytes: int,
        declared_mime: str,
        object_key: str,
        created_at: datetime,
        expires_at: datetime,
        session_id: Uuid | None = None,
    ) -> UploadSession:
        """创建 PENDING 会话；校验声明元数据基本合法性。"""
        if not declared_filename.strip():
            raise ValueError("声明文件名不能为空")
        if declared_size_bytes <= 0:
            raise ValueError("声明大小必须为正")
        if not declared_mime.strip():
            raise ValueError("声明 MIME 不能为空")
        if expires_at <= created_at:
            raise ValueError("过期时间必须晚于创建时间")
        return cls(
            id=session_id if session_id is not None else Uuid.new(),
            project_id=project_id,
            declared_filename=declared_filename,
            declared_size_bytes=declared_size_bytes,
            declared_mime=declared_mime,
            object_key=object_key,
            status=UploadSessionStatus.PENDING,
            created_at=created_at,
            expires_at=expires_at,
        )

    def is_expired(self, now: datetime) -> bool:
        """当前是否已过期。"""
        return now >= self.expires_at

    def can_complete(self, now: datetime) -> bool:
        """能否完成正式接入：必须 PENDING 且未过期。"""
        return self.status == UploadSessionStatus.PENDING and not self.is_expired(now)

    def _transition(self, target: UploadSessionStatus) -> None:
        validate_transition(UploadSessionStatus, self.status, target)
        self.status = target

    def complete(self, *, now: datetime) -> None:
        """完成接入；过期会话被拒绝。"""
        if self.is_expired(now):
            raise PermissionError("上传会话已过期，不能完成正式接入")
        self._transition(UploadSessionStatus.COMPLETED)
        self.completed_at = now

    def expire(self) -> None:
        self._transition(UploadSessionStatus.EXPIRED)

    def cancel(self) -> None:
        self._transition(UploadSessionStatus.CANCELLED)

    @property
    def project_uuid(self) -> UUID:
        return self.project_id.value

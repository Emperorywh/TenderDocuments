"""MinIO/S3 对象存储适配器（C-002 写入；C-003/004/005 扩展读取/授权/移动删除）。

实现 ObjectStorage 端口。客户端可注入以便用 mock 做单元测试；默认按配置创建
minio.Minio 客户端。真实 MinIO 集成验证依赖 Docker（阶段 A-018）就绪后补充。

对象键经 ObjectKey.as_path() 组织为 分类/键，不含可猜测的原始文件名。
"""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO

from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error

from tender_insight.modules.document.application import ObjectKey


class MinioObjectStorage:
    """ObjectStorage 端口的 MinIO 实现。

    C-002 实现写入（put）与存在性（exists）；get/presigned/move/delete 在后续
    任务补充。客户端可经 client 参数注入以支持 mock 单元测试。
    """

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        region: str = "us-east-1",
        client: Minio | None = None,
    ) -> None:
        self._bucket = bucket
        # client 注入优先；否则按配置创建真实客户端。
        self._client = client if client is not None else Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )

    def put(self, key: ObjectKey, data: bytes, *, content_type: str) -> None:
        """写入对象；以流式上传固定字节。"""
        self._client.put_object(
            self._bucket,
            key.as_path(),
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def exists(self, key: ObjectKey) -> bool:
        """对象是否存在；NoSuchKey 视为不存在，其它错误向上抛。"""
        try:
            self._client.stat_object(self._bucket, key.as_path())
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise

    def get(self, key: ObjectKey) -> bytes:
        """私有读取对象全部字节。

        get_object 依赖客户端凭据（服务端处理用），不经后端授权无法直接读取，
        对象默认私有（SPEC.md 第 4.2 节）。
        """
        response = self._client.get_object(self._bucket, key.as_path())
        try:
            return response.read()
        finally:
            # 释放底层连接，避免连接泄漏。
            response.close()
            release_conn = getattr(response, "release_conn", None)
            if release_conn is not None:
                release_conn()

    def presigned_get_url(self, key: ObjectKey, *, expires_in_seconds: int) -> str:
        """生成短期授权读取地址。

        到期后地址失效（由 MinIO 按 expires 校验）。注意：日志不得记录完整签名
        URL，该脱敏在可观测性层（J-003）实现；本方法只返回地址。
        """
        return self._client.presigned_get_object(
            self._bucket,
            key.as_path(),
            expires=timedelta(seconds=expires_in_seconds),
        )

    def move(self, source: ObjectKey, destination: ObjectKey) -> None:
        """移动对象：复制到目标键后删除源键，使源键失效。"""
        self._client.copy_object(
            self._bucket,
            destination.as_path(),
            CopySource(self._bucket, source.as_path()),
        )
        self._client.remove_object(self._bucket, source.as_path())

    def delete(self, key: ObjectKey) -> None:
        """删除对象（幂等）；MinIO remove_object 对不存在的键不报错。"""
        self._client.remove_object(self._bucket, key.as_path())

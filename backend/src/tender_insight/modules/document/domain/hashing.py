"""SHA-256 流式哈希服务（C-013）。

按 SPEC.md 第 6.4、9.3 节，原始文件计算 SHA-256（确定性规则，不依赖模型）。
提供一次性与分片（流式）两种接口，结果一致，便于大文件分块读取时仍可计算。
纯逻辑（仅标准库）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

# 流式读取分片大小（默认 64KB），与 hashlib 内部块大小对齐，效率与确定性兼顾。
DEFAULT_CHUNK_SIZE = 64 * 1024


def sha256_hex(data: bytes) -> str:
    """一次性计算并返回十六进制 SHA-256。"""
    return hashlib.sha256(data).hexdigest()


def sha256_streaming(chunks: Iterable[bytes]) -> str:
    """分片流式计算 SHA-256；与一次性结果一致。"""
    hasher = hashlib.sha256()
    for chunk in chunks:
        hasher.update(chunk)
    return hasher.hexdigest()


def iter_chunks(data: bytes, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Iterable[bytes]:
    """把整块数据切成指定大小的分片，便于流式哈希与测试。"""
    for start in range(0, len(data), chunk_size):
        yield data[start : start + chunk_size]

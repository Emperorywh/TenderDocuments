"""SHA-256 哈希服务测试（C-013 独立验证）。

验证大文件分片与一次性计算结果一致。
"""

from __future__ import annotations

import hashlib

from tender_insight.modules.document.domain.hashing import (
    DEFAULT_CHUNK_SIZE,
    iter_chunks,
    sha256_hex,
    sha256_streaming,
)


def test_known_value() -> None:
    assert sha256_hex(b"") == hashlib.sha256(b"").hexdigest()
    assert sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_streaming_matches_one_shot() -> None:
    """大文件分片哈希与一次性哈希一致。"""
    data = bytes(range(256)) * 1000  # 256KB
    assert sha256_hex(data) == sha256_streaming(iter_chunks(data))


def test_chunk_size_does_not_change_result() -> None:
    """不同分片大小结果一致。"""
    data = b"x" * (DEFAULT_CHUNK_SIZE * 3 + 7)
    same = sha256_hex(data)
    assert sha256_streaming(iter_chunks(data, chunk_size=1)) == same
    assert sha256_streaming(iter_chunks(data, chunk_size=17)) == same
    assert sha256_streaming(iter_chunks(data, chunk_size=DEFAULT_CHUNK_SIZE)) == same


def test_empty_streaming() -> None:
    assert sha256_streaming([]) == hashlib.sha256(b"").hexdigest()

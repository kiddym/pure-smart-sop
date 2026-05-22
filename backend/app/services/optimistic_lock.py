"""乐观锁工具（Q18 / data-model §4.6）。

所有 PUT/PATCH 请求携带 `If-Match: <revision>`。缺失 → 412 IF_MATCH_REQUIRED；
不匹配 → 409 VERSION_CONFLICT。写成功后 revision 自增。
"""

from __future__ import annotations

from typing import Protocol

from app.errors import conflict, precondition_failed


class _HasRevision(Protocol):
    revision: int


def ensure_if_match(if_match: str | None) -> int:
    """解析并校验 If-Match 头，返回期望的 revision。缺失 / 非法 → 412。"""
    if if_match is None or not if_match.strip():
        raise precondition_failed("IF_MATCH_REQUIRED", "修改类请求缺少 If-Match 标头")
    value = if_match.strip()
    if value.startswith("W/"):  # 弱 ETag 前缀
        value = value[2:].strip()
    value = value.strip('"')
    try:
        return int(value)
    except ValueError:
        raise precondition_failed("IF_MATCH_REQUIRED", "If-Match 标头格式无效") from None


def verify_revision(current: int, expected: int) -> None:
    """当前 revision 与期望不符 → 409 VERSION_CONFLICT。"""
    if current != expected:
        raise conflict("VERSION_CONFLICT", "远程版本已变更，请加载最新版本后重试")


def bump(obj: _HasRevision) -> None:
    """写成功后递增乐观锁版本号。"""
    obj.revision += 1

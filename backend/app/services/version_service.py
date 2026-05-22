"""版本号与变更日志封装（data-model §3.3 / testing-standards §6.4）。

负责向 `version_change_log` 追加条目、推进版本号、以及 max_version_number 守卫。
完整的版本流转（fork / rollback / deprecate）在 Phase 7 实现，本模块是其基础工具。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.errors import bad_request
from app.models.procedure import Procedure
from app.models.settings import ProcedureSettings

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """变更日志时间戳，形如 2026-05-19T10:00:00Z。"""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_change(
    proc: Procedure,
    change_type: str,
    *,
    description: str = "",
    previous_version: int | None = None,
    reason: str | None = None,
    rollback_from_version: int | None = None,
) -> None:
    """向 version_change_log 追加一条变更记录。

    JSON 列需整体重新赋值才能被 SQLAlchemy 标记为脏（不可原地 append）。
    """
    entry: dict[str, object] = {
        "version": proc.version,
        "previous_version": previous_version,
        "changed_at": _now_iso(),
        "change_type": change_type,
        "description": description,
    }
    if reason is not None:
        entry["reason"] = reason
    if rollback_from_version is not None:
        entry["rollback_from_version"] = rollback_from_version

    proc.version_change_log = [*proc.version_change_log, entry]


def record_create(proc: Procedure, description: str = "") -> None:
    """创建程序时写入首条 create 记录。"""
    record_change(proc, "create", description=description)


def next_version_number(proc: Procedure) -> int:
    """下一版本号。"""
    return proc.version + 1


def assert_can_upgrade(proc: Procedure, settings: ProcedureSettings) -> None:
    """达到 max_version_number 上限时拒绝升级（Q222）。"""
    if proc.version >= settings.max_version_number:
        raise bad_request(
            "PROCEDURE_VERSION_MAX",
            "已达版本上限，请「复制为新程序」另起版本族",
        )

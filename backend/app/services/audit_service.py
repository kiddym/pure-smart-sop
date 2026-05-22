"""审计日志写入封装（data-model §3.9 / Q122-Q128 / Q324）。

追加式写日志：folder / procedure 两表。字段级 diff（Q123）；rollback/deprecate/
restore/delete 必填 reason（Q128，由调用方保证）。IP/UA 来自请求元信息（真实
客户端 IP 解析见 deps.get_request_meta + utils.net，Q324）。
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models.audit import FolderAuditLog, ProcedureAuditLog

logger = logging.getLogger(__name__)


class AuditMeta(Protocol):
    """审计所需的请求元信息（结构化匹配 deps.RequestMeta，避免层间耦合）。

    用只读 property 声明，使 frozen dataclass（RequestMeta）也满足该协议。
    """

    @property
    def ip_address(self) -> str: ...

    @property
    def user_agent(self) -> str: ...


def compute_diff(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """计算字段级 diff，仅保留发生变化的键（Q123）。

    取 before/after 键的并集，使「被移除的键」也能被记录到 diff。
    """
    old_value: dict[str, Any] = {}
    new_value: dict[str, Any] = {}
    for key in before.keys() | after.keys():
        if before.get(key) != after.get(key):
            old_value[key] = before.get(key)
            new_value[key] = after.get(key)
    return old_value, new_value


def log_folder_action(
    db: Session,
    *,
    target_id: str,
    action: str,
    meta: AuditMeta,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str = "",
) -> FolderAuditLog:
    """写一条文件夹审计日志（不 commit，由调用方提交）。"""
    entry = FolderAuditLog(
        target_id=target_id,
        action=action,
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )
    db.add(entry)
    logger.info("folder audit action=%s target=%s", action, target_id)
    return entry


def log_procedure_action(
    db: Session,
    *,
    target_id: str,
    procedure_group_id: str | None,
    action: str,
    meta: AuditMeta,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str = "",
) -> ProcedureAuditLog:
    """写一条程序审计日志（冗存 procedure_group_id，Q127）。不 commit。"""
    entry = ProcedureAuditLog(
        target_id=target_id,
        procedure_group_id=procedure_group_id,
        action=action,
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )
    db.add(entry)
    logger.info(
        "procedure audit action=%s target=%s group=%s",
        action,
        target_id,
        procedure_group_id,
    )
    return entry

"""邮件 outbox 入队 + 投递（Phase 5B）。

enqueue_transactional：事务邮件直发入队（邀请/密码重置/邮箱验证），不过偏好。
deliver_pending：投递某租户 pending 行（由调度 tick 调用）。
渲染在入队时完成并落库（subject/body 快照）。所有查询显式按 company_id 过滤。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.email.templates import render
from app.models.email_outbox import EmailOutbox


def enqueue_transactional(
    db: Session,
    *,
    company_id: str,
    recipient_email: str,
    type: str,
    params: dict[str, Any],
    recipient_user_id: str | None = None,
) -> EmailOutbox:
    """事务邮件直发入队（密码重置/邀请）：不过通知偏好、recipient_user_id 可空。不 commit。"""
    subject, body = render(type, params)
    row = EmailOutbox(
        company_id=company_id,
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        type=type,
        subject=subject,
        body=body,
        status="pending",
    )
    db.add(row)
    db.flush()
    return row


def deliver_pending(
    db: Session, *, backend: Any, max_attempts: int, company_id: str
) -> dict[str, int]:
    """投递某租户 pending 行（不 commit；由 tick 统一 commit）。"""
    from app.models.base import utcnow

    rows = (
        db.execute(
            select(EmailOutbox).where(
                EmailOutbox.company_id == company_id,
                EmailOutbox.status == "pending",
                EmailOutbox.attempts < max_attempts,
            )
        )
        .scalars()
        .all()
    )
    sent = failed = 0
    for row in rows:
        try:
            backend.send(row.recipient_email, row.subject, row.body, from_addr=_from_addr())
            row.status = "sent"
            row.sent_at = utcnow()
            sent += 1
        except Exception as e:
            row.attempts += 1
            row.last_error = str(e)
            if row.attempts >= max_attempts:
                row.status = "failed"
            failed += 1
    return {"sent": sent, "failed_attempt": failed}


def _from_addr() -> str:
    from app.config import settings

    return settings.email_from

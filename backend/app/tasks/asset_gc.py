"""asset GC 任务（§53.2 / §53.3 / Q197 / Q333）。

每日删除 ``ref_count=0`` 且 ``updated_at`` 早于 grace（默认 24h）的 asset：行锁
重核 + 先删文件再硬删行 + **逐项提交**（一个坏文件不拖垮整批）。
CLI：``python -m app.tasks.asset_gc --once``。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models.base import utcnow
from app.services import asset_service

logger = logging.getLogger(__name__)
TASK_NAME = "asset_gc"


def run(
    db: Session,
    *,
    now: datetime | None = None,
    grace_hours: int | None = None,
    commit: bool = True,
) -> dict[str, int]:
    """执行一次 GC（逐项提交）。返回 ``{scanned, deleted, errors}`` 摘要。"""
    started = now or utcnow()
    grace = grace_hours if grace_hours is not None else settings.asset_gc_grace_hours
    candidates = asset_service.gc_candidates(db, grace_hours=grace, now=started)
    deleted = 0
    errors = 0
    for asset_id in candidates:
        try:
            if asset_service.delete_asset_locked(db, asset_id, grace_hours=grace, now=started):
                if commit:
                    db.commit()
                deleted += 1
            elif commit:
                db.rollback()
        except Exception:  # 单项失败记日志并继续（§53.2 逐项提交）
            if commit:
                db.rollback()
            errors += 1
            logger.exception("asset_gc 删除失败 asset_id=%s", asset_id)

    summary = {"scanned": len(candidates), "deleted": deleted, "errors": errors}
    logger.info(
        json.dumps(
            {"task": TASK_NAME, "started_at": started.isoformat(), **summary}, ensure_ascii=False
        )
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="asset 垃圾回收（一次性）")
    parser.add_argument("--once", action="store_true", help="执行一次后退出（默认行为）")
    parser.parse_args(argv)
    configure_logging()
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

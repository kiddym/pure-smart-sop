"""临时上传清理任务（§53.2 / Q141 / Q341）。

每 1h 扫 ``tmp/uploads/*``，删除 ``expires_at`` 过期的 token 目录（纯文件系统，
无 DB）。CLI：``python -m app.tasks.cleanup_uploads --once``。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime

from app.logging_config import configure_logging
from app.models.base import utcnow
from app.services import upload_service

logger = logging.getLogger(__name__)
TASK_NAME = "cleanup_uploads"


def run(*, now: datetime | None = None) -> dict[str, int]:
    """执行一次清理，返回 run 摘要。"""
    started = now or utcnow()
    removed = upload_service.cleanup_expired(started)
    summary = {"removed": removed}
    logger.info(
        json.dumps(
            {"task": TASK_NAME, "started_at": started.isoformat(), **summary},
            ensure_ascii=False,
        )
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="临时上传清理（一次性）")
    parser.add_argument("--once", action="store_true", help="执行一次后退出（默认行为）")
    parser.parse_args(argv)
    configure_logging()
    run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

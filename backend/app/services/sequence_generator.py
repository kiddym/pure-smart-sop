"""编号序列生成器（data-model §3.2）。

生成叶子文件夹下程序编码的序号部分（零填充）。prefix 拼接在 procedure_service。
`reset_period` 固定 never（Q251），序列只增不重置；溢出时回绕到 1 并记 WARN。

注：本函数 **不 commit**——它应在 procedure_service 的事务内调用，由调用方提交。
SELECT ... FOR UPDATE 行锁在该事务结束前持有，串行化同 folder 的并发取号。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.folder import FolderSequence

logger = logging.getLogger(__name__)


def next_sequence_value(db: Session, folder_id: str) -> str:
    """取下一个序号字符串（如 "00001"）。folder 必须是有 sequence 的叶子。"""
    seq = db.execute(
        select(FolderSequence)
        .where(FolderSequence.folder_id == folder_id)
        .where(FolderSequence.is_active.is_(True))
        .with_for_update()
    ).scalar_one_or_none()

    if seq is None:
        raise not_found(
            "FOLDER_SEQUENCE_NOT_FOUND",
            "该文件夹没有编号序列（仅叶子文件夹可生成程序编码）",
        )

    digits = max(seq.sequence_digits, 1)  # 防御：位数配置异常时回落到至少 1 位
    max_value = 10**digits - 1
    next_value = seq.current_value + 1
    if next_value > max_value:
        logger.warning(
            "sequence overflow folder_id=%s digits=%s, reset to 1",
            folder_id,
            digits,
        )
        next_value = 1

    seq.current_value = next_value
    db.flush()
    return f"{next_value:0{digits}d}"

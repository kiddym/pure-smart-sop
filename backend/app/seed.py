"""启动种子数据（data-model §6）。

幂等：可重复运行不产生重复行。首次启动创建系统文件夹、设置单例与示例字段。

注：模板库及三套样板程序已废除（feature-clarifications §56/Q340）——不建模板库
文件夹，唯一系统文件夹为「废止」；模板需求由"复制现有程序"满足。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.field import ProcedureField
from app.models.folder import Folder
from app.models.settings import ProcedureSettings

logger = logging.getLogger(__name__)

DEPRECATED_FOLDER_NAME = "废止"
SAMPLE_FIELD_KEY = "example_risk_grade"


def _get_root_folder(db: Session, name: str) -> Folder | None:
    return db.execute(
        select(Folder).where(
            Folder.name == name,
            Folder.parent_id.is_(None),
            Folder.is_active.is_(True),
        )
    ).scalar_one_or_none()


def seed_system_folders(db: Session) -> None:
    """创建「废止」系统文件夹（唯一系统文件夹；模板库已废，§56/Q340）。"""
    if _get_root_folder(db, DEPRECATED_FOLDER_NAME) is None:
        # 废止：接收被废止程序（保留原 code，不生成新号），故无 prefix / 序列
        db.add(
            Folder(
                name=DEPRECATED_FOLDER_NAME,
                system=True,
                parent_id=None,
                prefix="",
                full_path=DEPRECATED_FOLDER_NAME,
            )
        )
        logger.info("seed: created system folder %s", DEPRECATED_FOLDER_NAME)


def seed_settings(db: Session) -> None:
    """创建全局设置单例。"""
    exists = db.execute(
        select(ProcedureSettings.id).where(ProcedureSettings.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if exists is None:
        db.add(ProcedureSettings())
        logger.info("seed: created settings singleton")


def seed_sample_field(db: Session) -> None:
    """创建示例自定义字段（可后续删除）。"""
    exists = db.execute(
        select(ProcedureField.id).where(
            ProcedureField.key == SAMPLE_FIELD_KEY,
            ProcedureField.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(
            ProcedureField(
                name="示例-风险等级",
                key=SAMPLE_FIELD_KEY,
                field_type="select",
                description="示例自定义字段，可删除",
                options=[
                    {"value": "low", "label": "低"},
                    {"value": "medium", "label": "中"},
                    {"value": "high", "label": "高"},
                ],
            )
        )
        logger.info("seed: created sample field %s", SAMPLE_FIELD_KEY)


def run_seed(db: Session) -> None:
    """执行全部种子（幂等）。"""
    seed_system_folders(db)
    seed_settings(db)
    seed_sample_field(db)
    db.commit()

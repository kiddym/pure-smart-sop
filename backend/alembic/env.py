"""Alembic environment configuration.

读取 app.config 的 DATABASE_URL，并以 app.models.base.Base 的 metadata 作为
迁移目标。include_object 忽略 MySQL 生成列（partial-unique 模拟），避免
`alembic check` 把它们误报为漂移（生成列只存在于迁移、不在 ORM metadata）。
"""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any

from sqlalchemy import engine_from_config, pool

# 触发全部模型导入以填充 metadata
import app.models  # noqa: F401
from alembic import context
from app.config import settings
from app.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata

# 仅存在于迁移的 MySQL 生成列 / partial-unique 索引名，autogenerate / check 时忽略
_GENERATED_ONLY_OBJECTS = {
    "active_unique_key",
    "active_code_version",
    "current_guard",
    "draft_guard",
    "uq_tb_folder_active_parent_name",
    "uq_tb_procedure_active_code_version",
    "uq_tb_procedure_current_guard",
    "uq_tb_procedure_draft_guard",
}


def include_object(
    object_: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    return name not in _GENERATED_ONLY_OBJECTS


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

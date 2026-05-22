"""文件夹相关 schema（api-specification §5.1 / data-model §3.1）。

字段命名 snake_case；时间用 ISO 8601 UTC。文件夹**不走乐观锁**（Q18 仅绑定
tb_procedure.revision），故响应无 revision 字段。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BatchDeleteFailure, BatchDeleteResult

__all__ = [
    "BatchDeleteFailure",
    "BatchDeleteIn",
    "BatchDeleteResult",
    "CheckResult",
    "FolderCreate",
    "FolderOption",
    "FolderOut",
    "FolderTreeNode",
    "FolderUpdate",
]


class FolderOut(BaseModel):
    """文件夹详情 / 列表行（裸 JSON 业务对象）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prefix: str
    parent_id: str | None
    system: bool
    full_path: str
    created_at: datetime
    updated_at: datetime


class FolderTreeNode(FolderOut):
    """树形节点（含程序计数与子节点，GET /folders/tree）。"""

    procedure_count: int
    children: list[FolderTreeNode]


class FolderOption(BaseModel):
    """下拉选项（GET /folders/options）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    full_path: str


class FolderCreate(BaseModel):
    """创建文件夹。prefix 非空 = 叶子（建序列）；空 = 中间容器（Q247/Q248）。"""

    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    prefix: str = Field(default="", max_length=20)
    # 仅叶子（prefix 非空）创建序列时使用；默认 5（Q250）
    sequence_digits: int = Field(default=5, ge=1, le=9)


class FolderUpdate(BaseModel):
    """全量更新（PUT 语义）。改 parent_id = 移动；系统文件夹禁改。"""

    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    prefix: str = Field(default="", max_length=20)
    sequence_digits: int | None = Field(default=None, ge=1, le=9)


class BatchDeleteIn(BaseModel):
    """批量软删入参（原子，≤100 项，Q325/Q20）。"""

    ids: list[str] = Field(min_length=1, max_length=100)


class CheckResult(BaseModel):
    """唯一性校验结果（check-name / check-prefix）。"""

    available: bool
    message: str | None = None


# 递归模型前向引用解析（PEP 563 注解需显式 rebuild）。
FolderTreeNode.model_rebuild()

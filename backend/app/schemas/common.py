"""通用响应 schema（分页等，api-specification §4.2）。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """统一分页响应。"""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class BatchDeleteFailure(BaseModel):
    """批量操作中单项失败详情。"""

    id: str
    code: str
    message: str


class BatchDeleteResult(BaseModel):
    """批量操作结果：成功 ID 列表 + 错误详情（Q20）。任一失败则全部回滚。"""

    deleted_ids: list[str]
    failed: list[BatchDeleteFailure]

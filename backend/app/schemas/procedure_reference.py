"""SOP 参考关系 API schema（设计 spec D22、§6）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 5 类（spec D22）：编写参考/执行参考/上游/下游/相关。
RelationType = Literal["authoring_ref", "exec_ref", "upstream", "downstream", "related"]


class ReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_procedure_id: str
    target_procedure_group_id: str
    relation_type: str
    note: str
    sort_order: int
    # 目标当前版本快照（service 解析填充；group 无当前版本时为 null）。
    target_procedure_id: str | None = None
    target_code: str | None = None
    target_name: str | None = None
    target_version: int | None = None


class ReferenceCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_procedure_group_id: str = Field(min_length=1)
    relation_type: RelationType
    note: str = ""
    sort_order: int | None = None


class ReferencePatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_type: RelationType | None = None
    note: str | None = None
    sort_order: int | None = None

"""SOP 参考关系模型 tb_procedure_reference。

一份程序（源=所编辑版本 source_procedure_id）可挂 0..N 条指向其它 SOP 的类型化引用。
目标用逻辑 SOP（target_procedure_group_id，消费时解析当前版本，版本健壮）。
对应设计 spec D22、§6 编写侧、§13.1（Copilot 上下文边界）。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class ProcedureReference(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """SOP 参考关系（编写/执行参考、上下游、相关）。"""

    __tablename__ = "tb_procedure_reference"

    # 源 = 所编辑的程序版本（与 nodes/checks 一致，受 assert_node_host_editable 守卫）。
    source_procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="CASCADE")
    )
    # 目标 = 逻辑 SOP（procedure_group_id）；非外键（group 不是表），消费时解析当前版本。
    target_procedure_group_id: Mapped[str] = mapped_column(String(36), index=True)
    relation_type: Mapped[str] = mapped_column(String(20))  # authoring_ref|exec_ref|upstream|downstream|related
    note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        # 复合索引覆盖按源列出（左前缀也覆盖 source_procedure_id 单列查找，故源列不再单独 index=True）。
        Index(
            "ix_tb_procedure_reference_source_sort",
            "source_procedure_id",
            "sort_order",
        ),
    )

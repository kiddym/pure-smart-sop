"""步骤监护期望（核查点）模型 tb_procedure_node_check。

一个步骤节点(kind='step')可挂 0..N 个核查点。类型专属字段存 JSON params。
对应设计 spec §6 编写侧、D2/D3。第一期 check_type ∈ {ocr, safety}。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)

class ProcedureNodeCheck(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """步骤核查点（监护期望）。"""

    __tablename__ = "tb_procedure_node_check"

    node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure_node.id", ondelete="CASCADE")
    )
    # 冗余存储便于按程序列出所有核查点（上下文/预览）。
    procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="RESTRICT"), index=True
    )
    check_type: Mapped[str] = mapped_column(String(20))  # ocr|safety|(预留 object|action|semantic)
    modality: Mapped[str] = mapped_column(String(20), default="visual", server_default="visual")
    severity: Mapped[str] = mapped_column(String(20), default="warn", server_default="warn")
    trigger: Mapped[str] = mapped_column(String(20), default="on_enter", server_default="on_enter")
    prompt: Mapped[str] = mapped_column(String(500), default="", server_default="")
    keep_evidence: Mapped[bool] = mapped_column(default=True, server_default="1")
    confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        Index("ix_tb_procedure_node_check_node_id_sort_order", "node_id", "sort_order"),
    )

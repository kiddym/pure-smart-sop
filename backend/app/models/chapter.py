"""程序章节模型（自引用树，data-model §3.4）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import LONGTEXT, Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.procedure import Procedure
    from app.models.step import ProcedureStep


class ProcedureChapter(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """章节节点。content_type=chapter（标题容器）或 content（叶子正文）。"""

    __tablename__ = "tb_procedure_chapter"

    procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="RESTRICT")
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_procedure_chapter.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(500))
    code: Mapped[str] = mapped_column(String(50), default="", server_default="")
    # chapter / content（§3.4.1）
    content_type: Mapped[str] = mapped_column(
        String(20), default="chapter", server_default="chapter"
    )
    # 仅 content 节点使用；chapter 节点恒为空字符串（应用层校验）
    rich_content: Mapped[str] = mapped_column(LONGTEXT, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # 1-3（Q190 二次修订回 3）
    level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # unmarked / step / content / review
    mark_status: Mapped[str] = mapped_column(
        String(20), default="unmarked", server_default="unmarked"
    )
    skip_numbering: Mapped[bool] = mapped_column(default=False, server_default="0")
    # 解析期临时态：pending / applied
    conversion_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )

    procedure: Mapped[Procedure] = relationship(back_populates="chapters")
    parent: Mapped[ProcedureChapter | None] = relationship(
        remote_side="ProcedureChapter.id", back_populates="children"
    )
    children: Mapped[list[ProcedureChapter]] = relationship(back_populates="parent")
    steps: Mapped[list[ProcedureStep]] = relationship(back_populates="chapter")

    __table_args__ = (
        Index("ix_tb_procedure_chapter_procedure_id_sort_order", "procedure_id", "sort_order"),
        Index("ix_tb_procedure_chapter_parent_id", "parent_id"),
        Index("ix_tb_procedure_chapter_mark_status", "mark_status"),
        Index("ix_tb_procedure_chapter_content_type", "content_type"),
    )

"""完整性对账（移植蓝本 §五 C001-C006 子集，Q348）。

C001 图片数 / C002 表格数 / C004 章节数≥1 / C006 body_start 非 None。
C003（段落 95%）/ C005（XML child order 同构）本期不实现（Q348）。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.parser.ir import Block


def image_count_match(body_blocks: Sequence[Block]) -> tuple[bool, int, int]:
    """C001：正文范围原始 blip 数 vs 抽取 image 数。"""
    raw = sum(b.raw_image_count for b in body_blocks)
    extracted = sum(len(b.images) for b in body_blocks)
    return raw == extracted, raw, extracted


def table_count_match(body_blocks: Sequence[Block]) -> tuple[bool, int, int]:
    """C002：正文范围原始 w:tbl 数（含嵌套）vs 序列化 <table> 数。"""
    raw = sum(b.raw_table_count for b in body_blocks if b.kind == "table")
    serialized = sum(b.html.count("<table") for b in body_blocks if b.kind == "table")
    return raw == serialized, raw, serialized

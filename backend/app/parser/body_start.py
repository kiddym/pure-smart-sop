"""正文起点判定（§25.4 / Q191）—— 取代 Q37「最后 section break」。

兜底链：first_styled_heading（TOC 防陷阱：取值须 ≥ toc_field_end）→ TOC field end
→ 启发式首个高分标题 → 跳封面兜底。删除 word-parser-solution 初版的 bookmark
``_Toc`` 信号（遍布正文标题，会误判到末尾）。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.parser.ir import Block


def _has_content(block: Block) -> bool:
    return bool(block.text.strip()) or bool(block.images) or block.kind == "table"


def find_body_start(
    blocks: Sequence[Block],
    *,
    toc_field_end: int | None = None,
    heuristic_heading_indices: Sequence[int] = (),
) -> tuple[int, str]:
    """返回 ``(body_start_index, detected_by)``。

    ``detected_by`` ∈ {first_styled_heading, toc_field_end, heuristic_heading, cover_skip}。
    总返回非 None（cover_skip 兜底返首个有内容块或 0），满足完整性校验 C006。
    """
    # TOC 防陷阱：first_styled_heading 必须 ≥ toc_field_end（先跳过目录区）
    toc_floor = (toc_field_end + 1) if toc_field_end is not None else 0

    # 1. first_styled_heading
    for block in blocks:
        if (
            block.source_index >= toc_floor
            and block.style_level is not None
            and not block.is_toc_field
        ):
            return block.source_index, "first_styled_heading"

    # 2. TOC field end：扫过目录后的首个非目录、有内容块
    if toc_field_end is not None:
        for block in blocks:
            if (
                block.source_index > toc_field_end
                and not block.is_toc_field
                and _has_content(block)
            ):
                return block.source_index, "toc_field_end"

    # 3. 启发式首个高分标题（caller 用 heading_detector 预算，standard 模式为空）
    for idx in sorted(heuristic_heading_indices):
        if idx >= toc_floor:
            return idx, "heuristic_heading"

    # 4. 跳封面兜底：首个有内容块
    for block in blocks:
        if _has_content(block):
            return block.source_index, "cover_skip"
    return 0, "cover_skip"

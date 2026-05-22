"""standard 模式模板校验（Q347 最小可用规则集）。

H001（error）：至少 1 个样式标题 → 否则 PARSE_TEMPLATE_INVALID。
H002（warning）：标题层级不跳级（无 L1 直接 L3）。
C001（warning）：图片数对账。C002（warning）：表格数对账。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.parser.ir import Block
from app.parser.result import ParsedNode, ValidationReport, ValidationRule
from app.parser.validators import completeness

_LEVEL_ORDER = {"pass": 0, "warning": 1, "error": 2}


def _flatten(nodes: Sequence[ParsedNode]) -> list[ParsedNode]:
    out: list[ParsedNode] = []

    def walk(items: Sequence[ParsedNode]) -> None:
        for n in items:
            out.append(n)
            walk(n.children)

    walk(nodes)
    return out


def validate(chapters: Sequence[ParsedNode], body_blocks: Sequence[Block]) -> ValidationReport:
    rules: list[ValidationRule] = []
    all_nodes = _flatten(chapters)
    heading_nodes = [n for n in all_nodes if n.content_type == "chapter"]

    # H001：至少一个样式标题（error）
    has_heading = len(heading_nodes) > 0
    rules.append(
        ValidationRule(
            code="H001",
            level="pass" if has_heading else "error",
            passed=has_heading,
            message="识别到样式标题" if has_heading else "未识别到任何样式标题（模板不规范）",
        )
    )

    # H002：层级不跳级（warning）
    no_skip = _no_level_skip(chapters)
    rules.append(
        ValidationRule(
            code="H002",
            level="pass" if no_skip else "warning",
            passed=no_skip,
            message="标题层级连续" if no_skip else "存在跳级标题（如 L1 直接到 L3）",
        )
    )

    # C001 图片对账 / C002 表格对账（warning）
    img_ok, img_raw, img_ext = completeness.image_count_match(body_blocks)
    rules.append(
        ValidationRule(
            code="C001",
            level="pass" if img_ok else "warning",
            passed=img_ok,
            message="图片数一致" if img_ok else f"图片可能遗漏：原始 {img_raw} / 解析 {img_ext}",
        )
    )
    tbl_ok, tbl_raw, tbl_ser = completeness.table_count_match(body_blocks)
    rules.append(
        ValidationRule(
            code="C002",
            level="pass" if tbl_ok else "warning",
            passed=tbl_ok,
            message="表格数一致" if tbl_ok else f"表格可能遗漏：原始 {tbl_raw} / 解析 {tbl_ser}",
        )
    )

    level = max((r.level for r in rules), key=lambda x: _LEVEL_ORDER[x])
    passed = level != "error"
    summary = {"pass": "校验通过", "warning": "校验通过（含警告）", "error": "模板校验未通过"}[
        level
    ]
    return ValidationReport(passed=passed, level=level, rules=rules, summary=summary)


def _no_level_skip(chapters: Sequence[ParsedNode]) -> bool:
    """子节点 chapter 层级不应比父跳超过 1 级。"""
    ok = True

    def walk(nodes: Sequence[ParsedNode], parent_level: int) -> None:
        nonlocal ok
        for n in nodes:
            if n.content_type == "chapter":
                if n.level - parent_level > 1:
                    ok = False
                walk(n.children, n.level)
            else:
                walk(n.children, parent_level)

    walk(chapters, 0)
    return ok

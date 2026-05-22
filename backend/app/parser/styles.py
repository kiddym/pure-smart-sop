"""styles.xml 反查 + 标题样式分类（§25.4 Tier1 权威信号）。

body 段落的 ``pStyle`` 是数字 styleId（如 "2"/"13"），**必须先反查 styles.xml**
才能映射到 ``name='heading 1'``——直接拿 styleId 比对会全 miss（初版脚本的 bug，
word-parser-solution §5.1）。

四级反查（按 Q344 优先级）：style_overrides（DB 注入）→ 标准 heading 名 →
中文同义词词典 → 自身 outlineLvl → basedOn 链上溯。返回**原始层级 1-9**（H4-9
的压缩到 L3 + ``<strong>`` 由 structurer 处理，Q35）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import etree

from app.parser.utils.opc import qn

_MAX_DEPTH = 12  # basedOn 链防环

# 标准 heading 名 → 层级。英文 "heading N"、中文 "标题 N"/"标题N"。
_STD_EN = re.compile(r"^heading\s*([1-9])$")
_STD_CN = re.compile(r"^标题\s*([1-9])$")


@dataclass
class StyleInfo:
    """单个段落样式的关键属性。"""

    style_id: str
    name: str | None
    outline_lvl: int | None
    based_on: str | None


class StyleIndex:
    """styleId → StyleInfo 索引。"""

    def __init__(self) -> None:
        self.by_id: dict[str, StyleInfo] = {}

    def get(self, style_id: str | None) -> StyleInfo | None:
        if style_id is None:
            return None
        return self.by_id.get(style_id)

    def all(self) -> list[StyleInfo]:
        return list(self.by_id.values())


def build_style_index(styles_root: etree._Element | None) -> StyleIndex:
    """从 styles.xml 根构建索引。"""
    index = StyleIndex()
    if styles_root is None:
        return index
    for style in styles_root.findall(qn("w:style")):
        style_id = style.get(qn("w:styleId"))
        if not style_id:
            continue
        name_el = style.find(qn("w:name"))
        name = name_el.get(qn("w:val")) if name_el is not None else None
        based_el = style.find(qn("w:basedOn"))
        based_on = based_el.get(qn("w:val")) if based_el is not None else None
        outline_lvl = _read_outline_lvl(style)
        index.by_id[style_id] = StyleInfo(
            style_id=style_id, name=name, outline_lvl=outline_lvl, based_on=based_on
        )
    return index


def _read_outline_lvl(style: etree._Element) -> int | None:
    ppr = style.find(qn("w:pPr"))
    if ppr is None:
        return None
    ol = ppr.find(qn("w:outlineLvl"))
    if ol is None:
        return None
    val = ol.get(qn("w:val"))
    try:
        return int(val) if val is not None else None
    except ValueError:
        return None


def _level_from_standard_name(name: str) -> int | None:
    norm = name.strip().lower()
    m = _STD_EN.match(norm)
    if m:
        return int(m.group(1))
    m = _STD_CN.match(name.strip())
    if m:
        return int(m.group(1))
    return None


def classify_with_source(
    style_id: str | None,
    index: StyleIndex,
    *,
    synonyms: dict[str, int] | None = None,
    style_overrides: dict[str, int] | None = None,
    _depth: int = 0,
) -> tuple[int | None, str | None]:
    """四级反查，返回 ``(原始层级, 来源)``；非标题样式返回 ``(None, None)``。

    来源 ∈ {override, style, synonym, outline, based_on}。``style_overrides``
    （heading_style_map DB 层）优先级最高（Q344 注入缝）。
    """
    info = index.get(style_id)
    if info is None or _depth > _MAX_DEPTH:
        return None, None

    name = (info.name or "").strip()

    # 1. style_overrides（DB 组织级层）——按样式名覆盖
    if style_overrides and name in style_overrides:
        return style_overrides[name], "override"

    # 2. 标准 heading 名
    std = _level_from_standard_name(name) if name else None
    if std is not None:
        return std, "style"

    # 3. 中文/自定义同义词词典
    if synonyms and name in synonyms:
        return synonyms[name], "synonym"

    # 4. 自身 outlineLvl（0-based → 1-based 层级）
    if info.outline_lvl is not None:
        return info.outline_lvl + 1, "outline"

    # 5. 沿 basedOn 链递归上溯
    if info.based_on:
        level, _ = classify_with_source(
            info.based_on,
            index,
            synonyms=synonyms,
            style_overrides=style_overrides,
            _depth=_depth + 1,
        )
        if level is not None:
            return level, "based_on"
    return None, None


def classify_heading_style(
    style_id: str | None,
    index: StyleIndex,
    *,
    synonyms: dict[str, int] | None = None,
    style_overrides: dict[str, int] | None = None,
) -> int | None:
    """四级反查样式标题层级；非标题样式返回 None（仅返回层级，丢弃来源）。"""
    level, _ = classify_with_source(
        style_id, index, synonyms=synonyms, style_overrides=style_overrides
    )
    return level

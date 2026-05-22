"""反查 styles.xml：把数字 pStyle ID 映射到真实样式名 + basedOn 上溯链。

回答：5 份 SOP 里数字样式 ID（13/28/29/32/33/38...）到底是不是 heading？
方案需要怎么改 Tier 1+2 才能识别这些样式？
"""
from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def qn(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def parse_styles(docx_path: Path) -> dict:
    with zipfile.ZipFile(docx_path) as z:
        styles_xml = z.read("word/styles.xml")
    root = etree.fromstring(styles_xml)

    styles: dict[str, dict] = {}
    for style in root.findall(qn("w:style")):
        sid = style.get(qn("w:styleId"))
        if not sid:
            continue
        name_el = style.find(qn("w:name"))
        based_el = style.find(qn("w:basedOn"))
        next_el = style.find(qn("w:next"))
        ppr = style.find(qn("w:pPr"))
        outline = ppr.find(qn("w:outlineLvl")) if ppr is not None else None
        styles[sid] = {
            "type": style.get(qn("w:type")),
            "name": name_el.get(qn("w:val")) if name_el is not None else None,
            "basedOn": based_el.get(qn("w:val")) if based_el is not None else None,
            "next": next_el.get(qn("w:val")) if next_el is not None else None,
            "outlineLvl": outline.get(qn("w:val")) if outline is not None else None,
        }
    return styles


def resolve_chain(sid: str, styles: dict, max_depth: int = 10) -> list[str]:
    """沿 basedOn 链上溯，返回 [当前 name, parent name, ...]。"""
    chain: list[str] = []
    current = sid
    seen: set[str] = set()
    while current and current in styles and current not in seen and len(chain) < max_depth:
        seen.add(current)
        s = styles[current]
        label = f"{current} → {s['name'] or '?'}"
        if s["outlineLvl"] is not None:
            label += f" [outline={s['outlineLvl']}]"
        chain.append(label)
        current = s["basedOn"]
    return chain


def classify_heading(sid: str, styles: dict) -> tuple[int | None, str]:
    """判断样式 sid 是否是 heading；返回 (level, reason)。

    level: 1-9 或 None
    reason: 命中规则
    """
    if sid not in styles:
        return None, "unknown_style"
    s = styles[sid]

    # 规则 1: name 含 "heading N" 或 "标题 N"
    name = (s["name"] or "").lower()
    for i in range(1, 10):
        if f"heading {i}" == name or f"标题 {i}" == s["name"] or f"标题{i}" == s["name"]:
            return i, f"name='{s['name']}'"

    # 规则 2: outlineLvl
    if s["outlineLvl"] is not None:
        try:
            lvl = int(s["outlineLvl"]) + 1
            return lvl, f"outlineLvl={s['outlineLvl']}"
        except ValueError:
            pass

    # 规则 3: basedOn 上溯
    current = s["basedOn"]
    seen: set[str] = {sid}
    while current and current in styles and current not in seen:
        seen.add(current)
        parent = styles[current]
        pname = (parent["name"] or "").lower()
        for i in range(1, 10):
            if f"heading {i}" == pname or f"标题 {i}" == parent["name"] or f"标题{i}" == parent["name"]:
                return i, f"basedOn chain → '{parent['name']}'"
        if parent["outlineLvl"] is not None:
            try:
                lvl = int(parent["outlineLvl"]) + 1
                return lvl, f"basedOn chain → outlineLvl={parent['outlineLvl']}"
            except ValueError:
                pass
        current = parent["basedOn"]

    return None, "not_heading"


def main():
    docs_dir = Path(
        r"d:\project devleoment\Claude code projects\smart sop\smart sop\smart sop"
        r"\docs\reference doc\typical word doc"
    )
    # 5 份文档的 top pStyle（从前一脚本结果手抄）
    top_styles = {
        "1_程序模板.docx": ["28", "18", "2", "31", "21", "14", "3", "4", "5", "6"],
        "TP试验程序.docx": ["13", "14"],
        "公司运营管理.docx": ["29", "32", "19", "2", "22", "3"],
        "公司运营管理_表格图片.docx": ["33", "30", "19", "2", "22", "3"],
        "电厂管理巡视规定.docx": ["38", "25", "3", "36", "22", "2"],
    }

    for docx_path in sorted(docs_dir.glob("*.docx")):
        name = docx_path.name
        print(f"\n{'='*70}")
        print(f"📄 {name}")
        print(f"{'='*70}")
        styles = parse_styles(docx_path)

        # 列出 top pStyle 的解析
        sids = top_styles.get(name, [])
        print(f"  Top pStyle 反查:")
        print(f"  {'sid':<5} {'name':<25} {'basedOn':<10} {'outline':<8} → {'heading?':<25} {'level':>5}")
        for sid in sids:
            if sid not in styles:
                print(f"  {sid:<5} ❌ NOT FOUND")
                continue
            s = styles[sid]
            level, reason = classify_heading(sid, styles)
            mark = f"L{level}" if level else "-"
            print(f"  {sid:<5} {(s['name'] or '?')[:24]:<25} "
                  f"{(s['basedOn'] or '-'):<10} "
                  f"{(s['outlineLvl'] or '-'):<8} → "
                  f"{reason[:24]:<25} {mark:>5}")

        # 列出 styles.xml 中所有 heading-like 样式
        print(f"\n  所有命中的 heading 样式:")
        for sid, s in styles.items():
            level, reason = classify_heading(sid, styles)
            if level is not None:
                print(f"    {sid:<10} L{level}  name='{s['name']}'  reason={reason}")


if __name__ == "__main__":
    main()

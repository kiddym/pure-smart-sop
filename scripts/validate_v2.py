"""V2 验证：用 styles.xml 反查 + 中文/自定义 heading 同义词扫描真实的 first_h1。

对 5 份文档做：
  1. 反查每个 pStyle sid → name → heading level（含 basedOn 上溯）
  2. 重新扫描 first_heading 在 body 中的位置（修正 signal_3）
  3. 删除信号 2（bookmark _Toc），重新计算 body_start_idx
  4. 列出前 20 个 body children 的 pStyle + 文本预览，便于人工确认起点
  5. 列出所有识别到的 heading（按出现顺序，含 level / 文本预览）
"""
from __future__ import annotations

import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = f"{{{NS['w']}}}"


def qn(t: str) -> str:
    p, l = t.split(":")
    return f"{{{NS[p]}}}{l}"


def local(tag: str) -> str:
    return etree.QName(tag).localname


def text_of(p) -> str:
    return "".join(p.itertext()).strip()


def load_styles(z: zipfile.ZipFile) -> dict[str, dict]:
    root = etree.fromstring(z.read("word/styles.xml"))
    styles: dict[str, dict] = {}
    for s in root.findall(qn("w:style")):
        sid = s.get(qn("w:styleId"))
        if not sid:
            continue
        name_el = s.find(qn("w:name"))
        based = s.find(qn("w:basedOn"))
        ppr = s.find(qn("w:pPr"))
        outline = ppr.find(qn("w:outlineLvl")) if ppr is not None else None
        styles[sid] = {
            "name": name_el.get(qn("w:val")) if name_el is not None else None,
            "basedOn": based.get(qn("w:val")) if based is not None else None,
            "outlineLvl": outline.get(qn("w:val")) if outline is not None else None,
        }
    return styles


HEADING_NAMES = {f"heading {i}": i for i in range(1, 10)}
HEADING_NAMES.update({f"标题 {i}": i for i in range(1, 10)})
HEADING_NAMES.update({f"标题{i}": i for i in range(1, 10)})
# 中文/自定义同义词（基于 TP试验程序 等观察）
CN_SYNONYM_LEVEL = {
    "章节标题": 1,
    "章标题": 1,
    "节标题": 2,
    "小节标题": 2,
    "条标题": 3,
}


def classify_style(sid: str, styles: dict, depth: int = 0) -> tuple[int | None, str]:
    if sid not in styles or depth > 10:
        return None, "unknown"
    s = styles[sid]
    name = (s["name"] or "").strip()
    # 1. 标准 heading 名
    if name.lower() in HEADING_NAMES:
        return HEADING_NAMES[name.lower()], f"name='{name}'"
    if name in HEADING_NAMES:
        return HEADING_NAMES[name], f"name='{name}'"
    # 2. 中文同义词
    if name in CN_SYNONYM_LEVEL:
        return CN_SYNONYM_LEVEL[name], f"cn_synonym='{name}'"
    # 3. outlineLvl 直接判定
    if s["outlineLvl"] is not None:
        try:
            return int(s["outlineLvl"]) + 1, f"outlineLvl={s['outlineLvl']}"
        except ValueError:
            pass
    # 4. basedOn 上溯
    if s["basedOn"]:
        lvl, why = classify_style(s["basedOn"], styles, depth + 1)
        if lvl is not None:
            return lvl, f"→ {why}"
    return None, "not_heading"


def scan_doc(docx_path: Path) -> dict:
    out: dict = {"name": docx_path.name}
    with zipfile.ZipFile(docx_path) as z:
        styles = load_styles(z)
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find(qn("w:body"))
    children = list(body.iterchildren())

    # 反查所有 pStyle 出现的 sid，标 level
    sid_usage: Counter[str] = Counter()
    for p in body.findall(f".//{qn('w:p')}"):
        ps = p.find(f".//{qn('w:pStyle')}")
        if ps is not None:
            sid_usage[ps.get(qn("w:val"))] += 1
    sid_table = []
    for sid, count in sid_usage.most_common():
        lvl, why = classify_style(sid, styles)
        sid_table.append((sid, styles.get(sid, {}).get("name"), count, lvl, why))
    out["sid_usage"] = sid_table

    # 扫描每个 child（顶层）的 pStyle level + 文本预览
    children_summary = []
    headings_found = []
    first_heading_idx = None
    first_h1_idx = None
    for idx, child in enumerate(children):
        tag = local(child.tag)
        if tag == "p":
            ps = child.find(f".//{qn('w:pStyle')}")
            sid = ps.get(qn("w:val")) if ps is not None else None
            outline = child.find(f".//{qn('w:outlineLvl')}")
            inline_outline = outline.get(qn("w:val")) if outline is not None else None
            txt = text_of(child)[:50]
            level = None
            reason = ""
            if sid:
                level, reason = classify_style(sid, styles)
            if level is None and inline_outline is not None:
                try:
                    level = int(inline_outline) + 1
                    reason = f"inline_outlineLvl={inline_outline}"
                except ValueError:
                    pass
            if level is not None:
                if first_heading_idx is None:
                    first_heading_idx = idx
                if level == 1 and first_h1_idx is None:
                    first_h1_idx = idx
                headings_found.append((idx, level, sid, txt, reason))
            children_summary.append((idx, "p", sid, level, txt))
        elif tag == "tbl":
            children_summary.append((idx, "tbl", None, None, "[table]"))
        else:
            children_summary.append((idx, tag, None, None, ""))

    # 信号 1: TOC fldChar (重跑)
    toc_end_idx = None
    toc_open = False
    for idx, child in enumerate(children):
        if local(child.tag) != "p":
            continue
        for fc in child.findall(f".//{qn('w:fldChar')}"):
            ftype = fc.get(qn("w:fldCharType"))
            if ftype == "begin":
                run = fc.getparent()
                if run is None:
                    continue
                p = run.getparent()
                if p is None:
                    continue
                instr = " ".join(
                    (it.text or "") for it in p.findall(f".//{qn('w:instrText')}")
                )
                if "TOC" in instr.upper():
                    toc_open = True
            elif ftype == "end" and toc_open:
                toc_end_idx = idx + 1
                toc_open = False
                break
        if toc_end_idx is not None:
            break

    # 信号 4: early sectPr (< min(20%, 100))
    n = len(children)
    threshold = min(n // 5 if n > 0 else 1, 100)
    early_sectpr = None
    for idx, child in enumerate(children):
        if idx >= threshold:
            break
        if local(child.tag) == "sectPr":
            early_sectpr = idx + 1
            break
        if local(child.tag) == "p":
            inner = child.find(f".//{qn('w:sectPr')}")
            if inner is not None:
                early_sectpr = idx + 1
                break

    # 融合：信号 1 (TOC end), 信号 3 (first H1 after styles 反查), 信号 4 (early sectPr)
    # 删除信号 2 (bookmark _Toc - 灾难性误判)
    candidates = {
        "signal_1_toc_end": toc_end_idx,
        "signal_3_first_h1_v2": first_h1_idx,
        "signal_3_first_heading_v2": first_heading_idx,
        "signal_4_early_sectpr": early_sectpr,
    }
    valid = [v for v in (toc_end_idx, first_h1_idx, early_sectpr) if v is not None]
    chosen = max(valid) if valid else (first_heading_idx if first_heading_idx is not None else 0)
    out["body_start_v2"] = {
        "candidates": candidates,
        "chosen_max": chosen,
        "skipped": chosen,
        "total_children": n,
    }
    out["first_20_children"] = children_summary[:20]
    out["headings_first_30"] = headings_found[:30]
    out["heading_count"] = len(headings_found)
    return out


def report(r: dict) -> None:
    print(f"\n{'='*72}")
    print(f"📄 {r['name']}")
    print(f"{'='*72}")
    print(f"  pStyle 使用情况 (sid → name, count, level):")
    for sid, name, count, lvl, why in r["sid_usage"][:12]:
        mark = f"L{lvl}" if lvl else "-"
        print(f"    {sid:<5} {(name or '?')[:24]:<26} ×{count:<5} {mark:<3} {why}")

    print(f"\n  前 20 个 body children:")
    print(f"    {'idx':>3} {'tag':<4} {'sid':<5} {'lvl':<4} text")
    for idx, tag, sid, lvl, txt in r["first_20_children"]:
        mark = f"L{lvl}" if lvl else "-"
        print(f"    {idx:>3} {tag:<4} {(sid or '-'):<5} {mark:<4} {txt}")

    print(f"\n  识别到的 heading 块（前 15 个）:")
    for idx, lvl, sid, txt, why in r["headings_found_show"]:
        print(f"    @{idx:>3}  L{lvl}  sid={sid}  '{txt}'   [{why}]")
    print(f"  ➤ 共识别 heading {r['heading_count']} 个")

    bs = r["body_start_v2"]
    print(f"\n  body_start v2:")
    for k, v in bs["candidates"].items():
        print(f"    {k:<28} = {v}")
    print(f"  ➤ chosen (max valid) = {bs['chosen_max']}, 跳过 {bs['skipped']}/{bs['total_children']} 块")


if __name__ == "__main__":
    docs_dir = Path(
        r"d:\project devleoment\Claude code projects\smart sop\smart sop\smart sop"
        r"\docs\reference doc\typical word doc"
    )
    for docx in sorted(docs_dir.glob("*.docx")):
        r = scan_doc(docx)
        # 限制显示前 15 个 heading
        r["headings_found_show"] = r["headings_first_30"][:15]
        report(r)

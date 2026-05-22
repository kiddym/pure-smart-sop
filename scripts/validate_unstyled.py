"""验证方案 C 启发式：针对「无格式标题」文档（形态 ④⑤）。

对每份文档：
  1. 确认 styles.xml 反查命中数（预期 0 或极少）
  2. 逐段提取：text / pStyle / 字号 / 加粗 / 编号模式 / 长度 / 对齐
  3. 跑 heading_score 启发式，分 HIGH/MEDIUM/LOW/NONE
  4. 检测编号模式，模拟「模式批量提升」
  5. 推断层级（编号深度优先）
"""
from __future__ import annotations

import re
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def qn(t: str) -> str:
    p, l = t.split(":")
    return f"{{{NS[p]}}}{l}"


def local(tag: str) -> str:
    return etree.QName(tag).localname


# ── styles.xml 反查（与 validate_v2 一致的精简版）──
HEADING_NAMES = {f"heading {i}": i for i in range(1, 10)}
HEADING_NAMES.update({f"标题 {i}": i for i in range(1, 10)})
HEADING_NAMES.update({f"标题{i}": i for i in range(1, 10)})
CN_SYNONYM = {"章节标题": 1, "章标题": 1, "节标题": 2, "小节标题": 2, "条标题": 3}


def load_styles(z):
    root = etree.fromstring(z.read("word/styles.xml"))
    styles = {}
    for s in root.findall(qn("w:style")):
        sid = s.get(qn("w:styleId"))
        if not sid:
            continue
        name_el = s.find(qn("w:name"))
        based = s.find(qn("w:basedOn"))
        ppr = s.find(qn("w:pPr"))
        outline = ppr.find(qn("w:outlineLvl")) if ppr is not None else None
        rpr = s.find(qn("w:rPr"))
        sz = rpr.find(qn("w:sz")) if rpr is not None else None
        b = rpr.find(qn("w:b")) if rpr is not None else None
        styles[sid] = {
            "name": name_el.get(qn("w:val")) if name_el is not None else None,
            "basedOn": based.get(qn("w:val")) if based is not None else None,
            "outlineLvl": outline.get(qn("w:val")) if outline is not None else None,
            "style_sz": int(sz.get(qn("w:val"))) if sz is not None and sz.get(qn("w:val")) else None,
            "style_bold": b is not None,
        }
    return styles


def classify_style(sid, styles, depth=0):
    if sid not in styles or depth > 10:
        return None
    s = styles[sid]
    name = (s["name"] or "").strip()
    if name.lower() in HEADING_NAMES:
        return HEADING_NAMES[name.lower()]
    if name in HEADING_NAMES:
        return HEADING_NAMES[name]
    if name in CN_SYNONYM:
        return CN_SYNONYM[name]
    if s["outlineLvl"] is not None:
        try:
            return int(s["outlineLvl"]) + 1
        except ValueError:
            pass
    if s["basedOn"]:
        return classify_style(s["basedOn"], styles, depth + 1)
    return None


# ── 编号模式 ──
NUM_PATTERNS = [
    ("L1_中文顿号", re.compile(r"^\s*[一二三四五六七八九十]+\s*[、.]")),
    ("L1_第X章", re.compile(r"^\s*第\s*[一二三四五六七八九十百\d]+\s*[章节条]")),
    ("L1_数字点", re.compile(r"^\s*\d+\s*[、.](?!\d)")),
    ("L2_数字点数字", re.compile(r"^\s*\d+\.\d+(?!\.\d)")),
    ("L3_数字点数字点数字", re.compile(r"^\s*\d+\.\d+\.\d+")),
    ("L2_括号中文", re.compile(r"^\s*[（(][一二三四五六七八九十]+[)）]")),
    ("L2_括号数字", re.compile(r"^\s*[（(]\d+[)）]")),
]
LEVEL_OF_PATTERN = {
    "L1_中文顿号": 1, "L1_第X章": 1, "L1_数字点": 1,
    "L2_数字点数字": 2, "L3_数字点数字点数字": 3,
    "L2_括号中文": 2, "L2_括号数字": 2,
}


def numbering_match(text):
    for name, pat in NUM_PATTERNS:
        if pat.match(text):
            return name
    return None


def para_features(p, styles):
    text = "".join(p.itertext()).strip()
    ps = p.find(f".//{qn('w:pStyle')}")
    sid = ps.get(qn("w:val")) if ps is not None else None
    # 字号：取段内最大 run sz（half-point），无则取样式 sz，再无默认 21(=10.5pt)
    szs = []
    bolds = []
    runs = p.findall(qn("w:r"))
    for r in runs:
        rpr = r.find(qn("w:rPr"))
        if rpr is None:
            continue
        sz = rpr.find(qn("w:sz"))
        if sz is not None and sz.get(qn("w:val")):
            try:
                szs.append(int(sz.get(qn("w:val"))))
            except ValueError:
                pass
        b = rpr.find(qn("w:b"))
        if b is not None:
            val = b.get(qn("w:val"))
            bolds.append(val in (None, "1", "true", "on"))
        else:
            bolds.append(False)
    style_sz = styles.get(sid, {}).get("style_sz") if sid else None
    font_sz = max(szs) if szs else (style_sz if style_sz else 21)
    # 加粗：有 run 且全部加粗，或样式加粗
    has_text_runs = [r for r in runs if "".join(r.itertext()).strip()]
    if has_text_runs and bolds:
        bold_ratio = sum(1 for b in bolds[:len(has_text_runs)] if b) / max(len(has_text_runs), 1)
    else:
        bold_ratio = 1.0 if styles.get(sid, {}).get("style_bold") else 0.0
    jc = p.find(f".//{qn('w:jc')}")
    align = jc.get(qn("w:val")) if jc is not None else None
    return {
        "text": text,
        "sid": sid,
        "font_sz": font_sz,
        "bold_ratio": bold_ratio,
        "num": numbering_match(text),
        "len": len(text),
        "align": align,
    }


def analyze(docx_path: Path):
    print(f"\n{'='*72}")
    print(f"📄 {docx_path.name}  ({docx_path.stat().st_size // 1024} KB)")
    print(f"{'='*72}")
    with zipfile.ZipFile(docx_path) as z:
        styles = load_styles(z)
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find(qn("w:body"))
    paras = body.findall(f".//{qn('w:p')}")

    # 1. styles.xml 命中
    sid_usage = Counter()
    for p in paras:
        ps = p.find(f".//{qn('w:pStyle')}")
        if ps is not None:
            sid_usage[ps.get(qn("w:val"))] += 1
    style_headings = sum(c for sid, c in sid_usage.items() if classify_style(sid, styles))
    print(f"  styles.xml heading 命中段落数: {style_headings}")
    print(f"  pStyle 使用: {[(sid, styles.get(sid, {}).get('name'), c) for sid, c in sid_usage.most_common(6)]}")

    # 2. 逐段特征 + 字号分布
    feats = [para_features(p, styles) for p in paras]
    nonempty = [f for f in feats if f["text"]]
    font_dist = [f["font_sz"] for f in nonempty]
    if font_dist:
        font_p85 = sorted(font_dist)[int(len(font_dist) * 0.85)]
        body_font = statistics.median(font_dist)
    else:
        font_p85 = body_font = 21
    print(f"  非空段落: {len(nonempty)}, 字号中位数: {body_font/2:.1f}pt, p85: {font_p85/2:.1f}pt")

    # 3. heuristic score
    def score(f):
        if f["sid"] and classify_style(f["sid"], styles):
            return 1.0, classify_style(f["sid"], styles), "style"
        s = 0.0
        if f["font_sz"] >= font_p85 and f["font_sz"] > body_font:
            s += 0.25
        if f["bold_ratio"] >= 0.5:
            s += 0.20
        if f["num"]:
            s += 0.25
        if 0 < f["len"] <= 30:
            s += 0.10
        if f["align"] in ("center",):
            s += 0.05
        # standalone 短段
        if 0 < f["len"] <= 20:
            s += 0.05
        return min(s, 0.84), (LEVEL_OF_PATTERN.get(f["num"]) if f["num"] else None), "heuristic"

    tiers = {"HIGH": [], "MEDIUM": [], "LOW": [], "NONE": []}
    for f in nonempty:
        sc, lvl, src = score(f)
        f["score"], f["level"], f["src"] = sc, lvl, src
        if sc >= 0.85:
            tiers["HIGH"].append(f)
        elif sc >= 0.5:
            tiers["MEDIUM"].append(f)
        elif sc >= 0.3:
            tiers["LOW"].append(f)
        else:
            tiers["NONE"].append(f)

    print(f"\n  置信度分档: HIGH={len(tiers['HIGH'])} MEDIUM={len(tiers['MEDIUM'])} "
          f"LOW={len(tiers['LOW'])} NONE={len(tiers['NONE'])}")

    # 4. 模式批量统计（MEDIUM+LOW 候选里编号模式分布）
    candidates = tiers["MEDIUM"] + tiers["LOW"]
    pattern_groups = defaultdict(list)
    for f in candidates:
        if f["num"]:
            pattern_groups[f["num"]].append(f["text"][:24])
    print(f"\n  🔍 候选中的编号模式（可批量提升）:")
    if pattern_groups:
        for pat, items in sorted(pattern_groups.items(), key=lambda x: -len(x[1])):
            lvl = LEVEL_OF_PATTERN.get(pat)
            print(f"    [{pat}] L{lvl} × {len(items)}  例: {items[:4]}")
    else:
        print(f"    （无编号模式，需靠字号/加粗逐个判断）")

    # 5. 展示 MEDIUM 候选前 25
    print(f"\n  MEDIUM 候选（前 25）:")
    for f in tiers["MEDIUM"][:25]:
        lvl = f"L{f['level']}" if f["level"] else "L?"
        print(f"    {f['score']:.2f} {lvl:<3} sz={f['font_sz']/2:.0f}pt b={f['bold_ratio']:.0%} "
              f"num={f['num'] or '-':<16} | {f['text'][:40]}")

    # 模式批量后的"剩余手工量"估算
    batchable = sum(len(v) for v in pattern_groups.values())
    print(f"\n  ➤ 模式可批量覆盖候选: {batchable} / {len(candidates)}  "
          f"(批量操作约 {len(pattern_groups)} 次, 剩余逐个 {len(candidates)-batchable} 个)")


if __name__ == "__main__":
    d = Path(
        r"d:\project devleoment\Claude code projects\smart sop\smart sop\smart sop"
        r"\docs\reference doc\typical word doc\无格式标题word"
    )
    for docx in sorted(d.glob("*.docx")):
        analyze(docx)

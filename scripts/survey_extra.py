"""规模化 survey：对一个文件夹下所有 docx 跑完整识别管线，找新失败模式。

每份报告：样式类型 / 正文起点信号 / 标题数(按 tier) / 编号模式 / 前几个标题 / 异常。
不需 ground truth——靠人眼扫前几个标题 + 异常标志定位需要打磨的点。
"""
from __future__ import annotations

import re
import statistics
import sys
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def qn(t):
    p, l = t.split(":")
    return f"{{{NS[p]}}}{l}"


def local(tag):
    return etree.QName(tag).localname


# ── styles.xml 反查（4 级）──
HEADING_NAMES = {f"heading {i}": i for i in range(1, 10)}
HEADING_NAMES.update({f"标题 {i}": i for i in range(1, 10)})
HEADING_NAMES.update({f"标题{i}": i for i in range(1, 10)})
CN_SYNONYM = {"章节标题": 1, "章标题": 1, "节标题": 2, "小节标题": 2, "条标题": 3}


def load_styles(z):
    try:
        root = etree.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return {}
    st = {}
    for s in root.findall(qn("w:style")):
        sid = s.get(qn("w:styleId"))
        if not sid:
            continue
        n = s.find(qn("w:name"))
        b = s.find(qn("w:basedOn"))
        pp = s.find(qn("w:pPr"))
        ol = pp.find(qn("w:outlineLvl")) if pp is not None else None
        st[sid] = {
            "name": n.get(qn("w:val")) if n is not None else None,
            "basedOn": b.get(qn("w:val")) if b is not None else None,
            "outlineLvl": ol.get(qn("w:val")) if ol is not None else None,
        }
    return st


def clf_style(sid, st, d=0):
    if sid not in st or d > 10:
        return None
    s = st[sid]
    nm = (s["name"] or "").strip()
    if nm.lower() in HEADING_NAMES:
        return HEADING_NAMES[nm.lower()]
    if nm in HEADING_NAMES:
        return HEADING_NAMES[nm]
    if nm in CN_SYNONYM:
        return CN_SYNONYM[nm]
    if s["outlineLvl"] is not None:
        try:
            return int(s["outlineLvl"]) + 1
        except ValueError:
            pass
    if s["basedOn"]:
        return clf_style(s["basedOn"], st, d + 1)
    return None


# ── 编号字典 v3 ──
def classify_numbering(text):
    t = text.strip()
    if re.match(r"^[一二三四五六七八九十]+\s*、", t):
        return 1, "heading"
    if re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*[章篇]", t):
        return 1, "heading"
    if re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*节", t):
        return 2, "heading"
    if re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*条", t):
        return 3, "weak_heading"
    if re.match(r"^\d+\.\d+\.\d+", t):
        return 3, "heading"
    if re.match(r"^\d+\.\d+(?!\.\d)", t):
        return 2, "heading"
    if re.match(r"^\d+\.(?!\d)", t):
        return 1, "heading"
    if re.match(r"^\d+\s*、", t):                  # v4: N、→weak_heading（顿号歧义，需粗体）
        return 1, "weak_heading"
    if re.match(r"^\d+\s+(?![/\d])\S", t):
        return 1, "heading"
    if re.match(r"^\d{1,2}(?=[一-鿿])", t):         # v4: N+中文直接（6相关文件）→weak_heading
        return 1, "weak_heading"
    if re.match(r"^[（(][一二三四五六七八九十]+[)）]", t):
        return 2, "list"
    if re.match(r"^[（(]\d+[)）]", t):
        return 2, "list"
    if re.match(r"^\d+\s*[)）]", t):               # N) / N） → 子列表项
        return 1, "list"
    return None, "none"


def is_page_number(t):
    return bool(re.match(r"^\d+\s*/\s*\d+$", t.strip()))


def para_features(p):
    text = "".join(p.itertext()).strip()
    szs, bolds = [], []
    runs = [r for r in p.findall(qn("w:r")) if "".join(r.itertext()).strip()]
    for r in runs:
        rpr = r.find(qn("w:rPr"))
        if rpr is None:
            bolds.append(False)
            continue
        sz = rpr.find(qn("w:sz"))
        if sz is not None and sz.get(qn("w:val")):
            try:
                szs.append(int(sz.get(qn("w:val"))))
            except ValueError:
                pass
        bb = rpr.find(qn("w:b"))
        bolds.append(bb is not None and bb.get(qn("w:val")) in (None, "1", "true", "on"))
    ps = p.find(f".//{qn('w:pStyle')}")
    return {
        "text": text,
        "sid": ps.get(qn("w:val")) if ps is not None else None,
        "font_sz": max(szs) if szs else 21,
        "bold_ratio": (sum(bolds) / len(bolds)) if bolds else 0.0,
        "len": len(text),
        "align": (p.find(f".//{qn('w:jc')}").get(qn("w:val"))
                  if p.find(f".//{qn('w:jc')}") is not None else None),
    }


def score(f, font_p85, body_font, font_disc, num_kind):
    s = 0.0
    if font_disc and f["font_sz"] >= font_p85 and f["font_sz"] > body_font:
        s += 0.25
    if f["bold_ratio"] >= 0.5:
        s += 0.20
    if num_kind == "heading":
        s += 0.30 if f["len"] <= 35 else 0.12
        if not font_disc:
            s += 0.10
    elif num_kind == "weak_heading":
        s += 0.15 if f["len"] <= 35 else 0.05
        if not font_disc:
            s += 0.05
    elif num_kind == "list":
        s -= 0.10
    if 0 < f["len"] <= 30:
        s += 0.10
    if f["align"] == "center":
        s += 0.05
    return max(0.0, min(s, 0.84))


def survey(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        st = load_styles(z)
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find(qn("w:body"))
    feats = [para_features(p) for p in body.findall(f".//{qn('w:p')}")
             if "".join(p.itertext()).strip()]

    # 样式标题命中
    style_headings = sum(1 for f in feats if f["sid"] and clf_style(f["sid"], st))
    styled = style_headings >= 2

    # 重复块
    tc = Counter(f["text"] for f in feats)
    repeated = {t for t, c in tc.items() if c >= 3}

    fonts = [f["font_sz"] for f in feats]
    font_p85 = sorted(fonts)[int(len(fonts) * 0.85)] if fonts else 21
    body_font = statistics.median(fonts) if fonts else 21
    font_disc = font_p85 > body_font * 1.05

    # find_body_start：styled→首样式标题；否则首个编号标题（跳重复/页码/封面）
    body_start, bs_sig = 0, "none"
    if styled:
        for i, f in enumerate(feats):
            if f["sid"] and clf_style(f["sid"], st):
                body_start, bs_sig = i, "styled_heading"
                break
    else:
        for i, f in enumerate(feats):
            if f["text"] in repeated or is_page_number(f["text"]):
                continue
            _, kind = classify_numbering(f["text"])
            if kind in ("heading", "weak_heading"):
                body_start, bs_sig = i, "first_numbered"
                break

    # 标题识别
    tiers = {"HIGH": [], "MEDIUM": [], "LOW": []}
    pattern_groups = Counter()
    for i, f in enumerate(feats):
        if i < body_start or f["text"] in repeated or is_page_number(f["text"]):
            continue
        lvl = clf_style(f["sid"], st) if f["sid"] else None
        if lvl is not None:
            tiers["HIGH"].append((i, lvl, f["text"]))
            continue
        num_lvl, kind = classify_numbering(f["text"])
        if kind in ("heading", "weak_heading"):
            pattern_groups[kind_label(f["text"])] += 1
        sc = score(f, font_p85, body_font, font_disc, kind)
        if sc >= 0.85:
            tiers["HIGH"].append((i, num_lvl, f["text"]))
        elif sc >= 0.5:
            tiers["MEDIUM"].append((i, num_lvl, f["text"]))
        elif sc >= 0.3:
            tiers["LOW"].append((i, num_lvl, f["text"]))

    return {
        "name": docx_path.name, "paras": len(feats), "styled": styled,
        "style_headings": style_headings, "body_start": body_start, "bs_sig": bs_sig,
        "repeated": len(repeated), "font_disc": font_disc,
        "tiers": tiers, "patterns": pattern_groups,
        "auto_total": len(tiers["HIGH"]) + len(tiers["MEDIUM"]),
        "low": len(tiers["LOW"]),
    }


def kind_label(text):
    t = text.strip()
    for pat, lab in [
        (r"^[一二三四五六七八九十]+\s*、", "中文顿号"),
        (r"^第\s*[\d一二三四五六七八九十百]+\s*[章篇]", "第X章"),
        (r"^第\s*[\d一二三四五六七八九十百]+\s*条", "第X条"),
        (r"^\d+\.\d+\.\d+", "N.N.N"),
        (r"^\d+\.\d+", "N.N"),
        (r"^\d+\.", "N."),
        (r"^\d+\s+(?![/\d])", "N+空格"),
    ]:
        if re.match(pat, t):
            return lab
    return "其他"


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else (
        r"d:\project devleoment\Claude code projects\smart sop\smart sop\smart sop"
        r"\docs\reference doc\typical word doc\extra doc"
    )
    d = Path(folder)
    rows = [survey(p) for p in sorted(d.glob("*.docx"))]

    print(f"{'文件':<42}{'段':>4}{'样式':>5}{'起点':>5}{'信号':>14}{'HIGH':>5}{'MED':>4}{'LOW':>4}")
    flagged = []
    for r in rows:
        sty = "是" if r["styled"] else "零"
        print(f"{r['name'][:40]:<42}{r['paras']:>4}{sty:>5}{r['body_start']:>5}"
              f"{r['bs_sig']:>14}{len(r['tiers']['HIGH']):>5}"
              f"{len(r['tiers']['MEDIUM']):>4}{r['low']:>4}")
        if r["auto_total"] == 0 or r["body_start"] > r["paras"] * 0.6:
            flagged.append(r)

    print("\n=== 模式分布（合计）===")
    allpat = Counter()
    for r in rows:
        allpat.update(r["patterns"])
    for k, c in allpat.most_common():
        print(f"  {k}: {c}")

    print(f"\n=== 异常文档（0 自动标题 或 起点过深）: {len(flagged)} ===")
    for r in flagged:
        print(f"  ⚠ {r['name']}: auto={r['auto_total']}, body_start={r['body_start']}/{r['paras']}")

    # 抽样：前 3 份的前 8 个识别标题，人眼核对
    print("\n=== 抽样（前 3 份的识别标题前 10）===")
    for r in rows[:3]:
        print(f"\n📄 {r['name']} (起点={r['body_start']}, 信号={r['bs_sig']})")
        merged = sorted(r["tiers"]["HIGH"] + r["tiers"]["MEDIUM"])[:10]
        for i, lvl, txt in merged:
            print(f"   @{i:>3} L{lvl}  {txt[:48]}")

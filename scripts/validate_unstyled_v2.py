"""方案 C 启发式 v2：分级编号字典 + 误报抑制 + 等字号自适应。

对两份零样式文档，用人工 ground truth 算 precision / recall，
对比 naive 基线（v1：粗粒度编号正则 + 固定权重）。
"""
from __future__ import annotations

import re
import statistics
import zipfile
from pathlib import Path

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def qn(t: str) -> str:
    p, l = t.split(":")
    return f"{{{NS[p]}}}{l}"


# ── 人工 ground truth（真标题文本前缀，level）──
GROUND_TRUTH = {
    "3.危险源监控措施.docx": [
        ("一、危险源：火灾", 1), ("二、危险源：触电", 1), ("三、危险源：机械伤害", 1),
        ("四、危险源：受限空间", 1), ("五、危险源：高处坠落", 1),
    ],
    "有限空间作业管理办法.docx": [
        ("第一章", 1), ("第二章", 1), ("第三章", 1),
        ("第四章", 1), ("第五章", 1), ("第九章", 1),
    ],
}


# ── 分级编号字典：返回 (level, kind) kind∈{heading,list,none} ──
def classify_numbering(text: str):
    t = text.strip()
    # 中文顿号 一、二、三、 → L1 heading（章节）
    if re.match(r"^[一二三四五六七八九十]+\s*、", t):
        return 1, "heading"
    # 第X章 / 第X篇 → L1
    if re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*[章篇]", t):
        return 1, "heading"
    # 第X节 → L2
    if re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*节", t):
        return 2, "heading"
    # 第X条 → L3 弱标题（语义模糊：可能是子标题，也可能是行内条款）→ 仅建议级
    if re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*条", t):
        return 3, "weak_heading"
    # 数字点深度 1.1.1 / 1.1 / 1.（注意 1. 不能后跟数字，避免吃 1.1）
    if re.match(r"^\d+\.\d+\.\d+", t):
        return 3, "heading"
    if re.match(r"^\d+\.\d+(?!\.\d)", t):
        return 2, "heading"
    if re.match(r"^\d+\.(?!\d)", t):
        return 1, "heading"
    # 列表项：括号编号 (一)/(1) → list（默认不升标题）
    if re.match(r"^[（(][一二三四五六七八九十]+[)）]", t):
        return 2, "list"
    if re.match(r"^[（(]\d+[)）]", t):
        return 2, "list"
    # 阿拉伯+顿号 1、2、 → list（中文 SOP 常用作条款列表）
    if re.match(r"^\d+\s*、", t):
        return 1, "list"
    return None, "none"


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
        b = rpr.find(qn("w:b"))
        bolds.append(b is not None and b.get(qn("w:val")) in (None, "1", "true", "on"))
    font_sz = max(szs) if szs else 21
    bold_ratio = (sum(bolds) / len(bolds)) if bolds else 0.0
    jc = p.find(f".//{qn('w:jc')}")
    return {
        "text": text,
        "font_sz": font_sz,
        "bold_ratio": bold_ratio,
        "len": len(text),
        "align": jc.get(qn("w:val")) if jc is not None else None,
    }


def score_v1(f, font_p85, body_font):
    """naive 基线：粗粒度（任何编号都 +0.25）+ 固定权重。"""
    s = 0.0
    if f["font_sz"] >= font_p85 and f["font_sz"] > body_font:
        s += 0.25
    if f["bold_ratio"] >= 0.5:
        s += 0.20
    # v1 把所有编号一视同仁
    if classify_numbering(f["text"])[1] != "none":
        s += 0.25
    if 0 < f["len"] <= 30:
        s += 0.10
    if f["align"] == "center":
        s += 0.05
    if 0 < f["len"] <= 20:
        s += 0.05
    return min(s, 0.84)


def score_v2(f, font_p85, body_font, font_discriminative):
    """v2：分级字典 + 误报抑制 + 等字号自适应。"""
    s = 0.0
    level, kind = classify_numbering(f["text"])

    # 等字号自适应：有区分度才用字号信号
    if font_discriminative and f["font_sz"] >= font_p85 and f["font_sz"] > body_font:
        s += 0.25

    if f["bold_ratio"] >= 0.5:
        s += 0.20

    if kind == "heading":
        # 误报抑制：标题型编号 + 短段 才给满额
        if f["len"] <= 35:
            s += 0.30
        else:
            s += 0.12  # 长段（号+正文同段，如"第一条 为加强…"）大幅降权
        if not font_discriminative:
            s += 0.10  # 等字号自适应：编号信号补偿
    elif kind == "weak_heading":
        # 弱标题（第X条）：仅给建议级分数，落 LOW 而非 MEDIUM
        if f["len"] <= 35:
            s += 0.15
        else:
            s += 0.05
        if not font_discriminative:
            s += 0.05
    elif kind == "list":
        s -= 0.10  # 列表项主动压制（1、/(一)/(1)）

    if 0 < f["len"] <= 30:
        s += 0.10
    if f["align"] == "center":
        s += 0.05
    out_level = level if kind in ("heading", "weak_heading") else None
    return max(0.0, min(s, 0.84)), out_level


def is_gt(text, gt_list):
    for prefix, lvl in gt_list:
        if text.startswith(prefix):
            return True, lvl
    return False, None


def metrics(preds: set, gts: set):
    tp = len(preds & gts)
    fp = len(preds - gts)
    fn = len(gts - preds)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return tp, fp, fn, prec, rec, f1


def analyze(docx_path: Path):
    name = docx_path.name
    print(f"\n{'='*72}\n📄 {name}\n{'='*72}")
    with zipfile.ZipFile(docx_path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find(qn("w:body"))
    paras = [p for p in body.findall(f".//{qn('w:p')}") if "".join(p.itertext()).strip()]
    feats = [para_features(p) for p in paras]

    fonts = [f["font_sz"] for f in feats]
    font_p85 = sorted(fonts)[int(len(fonts) * 0.85)] if fonts else 21
    body_font = statistics.median(fonts) if fonts else 21
    font_discriminative = font_p85 > body_font * 1.05
    print(f"  非空段 {len(feats)}, 字号中位 {body_font/2:.1f}pt p85 {font_p85/2:.1f}pt, "
          f"区分度={'有' if font_discriminative else '无（触发自适应）'}")

    gt_list = GROUND_TRUTH[name]
    gt_idx = {i for i, f in enumerate(feats) if is_gt(f["text"], gt_list)[0]}

    # v1 / v2 预测（MEDIUM+ = 预标 ≥0.5；LOW = 建议 0.3-0.49）
    pred_v1, pred_v2, low_v2 = set(), set(), set()
    v2_levels = {}
    for i, f in enumerate(feats):
        if score_v1(f, font_p85, body_font) >= 0.5:
            pred_v1.add(i)
        sc2, lvl2 = score_v2(f, font_p85, body_font, font_discriminative)
        v2_levels[i] = lvl2
        if sc2 >= 0.5:
            pred_v2.add(i)
        elif sc2 >= 0.3:
            low_v2.add(i)

    print(f"\n  Ground truth 标题: {len(gt_idx)} 个")
    print(f"  {'':16} {'TP':>3} {'FP':>3} {'FN':>3} {'Prec':>6} {'Rec':>6} {'F1':>6}")
    for tag, pred in (("v1 baseline", pred_v1), ("v2 改进(预标≥0.5)", pred_v2)):
        tp, fp, fn, pr, rc, f1 = metrics(pred, gt_idx)
        print(f"  {tag:16} {tp:>3} {fp:>3} {fn:>3} {pr:>6.2f} {rc:>6.2f} {f1:>6.2f}")
    print(f"  v2 LOW 建议级: {len(low_v2)} 个（不自动预标，浮现给用户确认）")

    # v2 误报/漏报明细
    fps = sorted(pred_v2 - gt_idx)
    fns = sorted(gt_idx - pred_v2)
    if fps:
        print(f"\n  v2 误报 (FP) {len(fps)} 个:")
        for i in fps[:10]:
            print(f"    @{i} L{v2_levels.get(i)}  {feats[i]['text'][:46]}")
    if fns:
        print(f"\n  v2 漏报 (FN) {len(fns)} 个:")
        for i in fns[:10]:
            print(f"    @{i}  {feats[i]['text'][:46]}")

    # v1 误报明细（看改进消除了什么）
    v1_only_fp = sorted((pred_v1 - gt_idx) - (pred_v2 - gt_idx))
    if v1_only_fp:
        print(f"\n  ✅ v2 相比 v1 新消除的误报 {len(v1_only_fp)} 个:")
        for i in v1_only_fp[:10]:
            print(f"    @{i}  {feats[i]['text'][:46]}")


if __name__ == "__main__":
    d = Path(
        r"d:\project devleoment\Claude code projects\smart sop\smart sop\smart sop"
        r"\docs\reference doc\typical word doc\无格式标题word"
    )
    for docx in sorted(d.glob("*.docx")):
        analyze(docx)

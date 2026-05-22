"""方案 C 启发式 v3：5 份零样式 fixture 的泛化验证。

3 份新 fixture（02记录控制/05人力资源/CW-WI外发）暴露三个泛化缺口，v3 修正：
  1. 「数字+空格+标题」编号（`1 目的`）—— v2 只认 `1.`/`1、`
  2. 页眉表格重复块混入正文 —— 出现≥3 次的相同文本 + `N / M` 页码 → 剔除
  3. 封面/签名块 —— find_body_start 跳到首个「带编号或样式」的标题，跳过纯粗体短块

对 5 份文档算 precision/recall，对比 v2（无三项修正）vs v3。
"""
from __future__ import annotations

import re
import statistics
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def qn(t: str) -> str:
    p, l = t.split(":")
    return f"{{{NS[p]}}}{l}"


# ── Ground truth：真标题文本前缀（不含页眉重复、列表项 1)/1）、封面块）──
GT = {
    "3.危险源监控措施.docx": [
        "一、危险源", "二、危险源", "三、危险源", "四、危险源", "五、危险源",
    ],
    "有限空间作业管理办法.docx": [
        "第一章", "第二章", "第三章", "第四章", "第五章", "第九章",
    ],
    "02记录控制程序.docx": [
        "1 目的", "2 范围", "3 职责和权限", "4 工作程序", "5 记录",
        "3.1 ", "3.2 ", "3.3 ", "3.4 ", "4.1 记录", "4.2记录", "4.3 记录",
        "4.4 记录的保管", "4.4 记录的查阅", "4.5 记录",
        "4.1.1", "4.1.2", "4.2.1", "4.3.2", "4.4.1", "4.4.2",
    ],
    "05人力资源控制程序.docx": [
        "1 目的", "2 范围", "3 职责", "4 工作程序", "5记录",
        "3.1 质量部", "3.2 各部门", "3.3 总经理", "4.1 人员安排", "4.2 能力",
        "4.3 培训计划", "4.4 培训实施", "4.5评价", "5.1", "5.2 ",
        "4.2.1 ", "4.2.2", "4.2.3", "4.2.4", "4.2.5", "4.2.6", "4.2.7",
    ],
    "CW-WI-7.4-01外发作业指导书及质量控制程序.docx": [
        "1.目的", "2.适用范围", "3.管理单位", "4.权责", "5.作业程序",
        "4.1 物控", "4.2 品质", "4.3工程", "5.9外发", "5.9.1",
        "6.2 ", "6.3 ", "6.4 ", "6.5 ", "6.6", "6.7 ", "6.8 ", "6.9 ", "6.10", "6.11",
    ],
}


# ── 编号分级字典 v3（新增「数字+空格」）──
def classify_numbering(text: str):
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
    # v4：「数字+顿号」（1、目的）→ weak_heading（顿号歧义大：QMS 章节 vs 危险源条款，需粗体才升）
    if re.match(r"^\d+\s*、", t):
        return 1, "weak_heading"
    # 「数字 + 空格 + 标题」（1 目的）→ heading（空格分隔少用于正文条款），排除页码 "1 / 2"
    if re.match(r"^\d+\s+(?![/\d])\S", t):
        return 1, "heading"
    # v4：「数字直接接中文」（6相关文件）→ weak_heading，1-2 位数字，排除年份 2017年
    if re.match(r"^\d{1,2}(?=[一-鿿])", t):
        return 1, "weak_heading"
    if re.match(r"^[（(][一二三四五六七八九十]+[)）]", t):
        return 2, "list"
    if re.match(r"^[（(]\d+[)）]", t):
        return 2, "list"
    if re.match(r"^\d+\s*[)）]", t):  # 1) / 1） → 子列表项
        return 1, "list"
    return None, "none"


def is_page_number(t: str) -> bool:
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
        b = rpr.find(qn("w:b"))
        bolds.append(b is not None and b.get(qn("w:val")) in (None, "1", "true", "on"))
    return {
        "text": text,
        "font_sz": max(szs) if szs else 21,
        "bold_ratio": (sum(bolds) / len(bolds)) if bolds else 0.0,
        "len": len(text),
        "align": (p.find(f".//{qn('w:jc')}").get(qn("w:val"))
                  if p.find(f".//{qn('w:jc')}") is not None else None),
    }


def score(f, font_p85, body_font, font_disc, use_v3, num_kind, num_level):
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


def find_body_start_idx(feats, repeated, use_v3):
    """v3：跳到首个『带 heading 编号』的块（跳过封面/签名/页眉）。"""
    if not use_v3:
        return 0
    for i, f in enumerate(feats):
        if f["text"] in repeated or is_page_number(f["text"]):
            continue
        _, kind = classify_numbering(f["text"])
        if kind in ("heading", "weak_heading"):
            return i
    return 0


def analyze(docx_path: Path, use_v3: bool):
    with zipfile.ZipFile(docx_path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    body = root.find(qn("w:body"))
    feats = [para_features(p) for p in body.findall(f".//{qn('w:p')}")
             if "".join(p.itertext()).strip()]

    # 重复块（≥3 次）→ 页眉表格 artifact
    text_counts = Counter(f["text"] for f in feats)
    repeated = {t for t, c in text_counts.items() if c >= 3}

    fonts = [f["font_sz"] for f in feats]
    font_p85 = sorted(fonts)[int(len(fonts) * 0.85)] if fonts else 21
    body_font = statistics.median(fonts) if fonts else 21
    font_disc = font_p85 > body_font * 1.05

    body_start = find_body_start_idx(feats, repeated, use_v3)

    preds = set()
    for i, f in enumerate(feats):
        if use_v3:
            if i < body_start:
                continue
            if f["text"] in repeated or is_page_number(f["text"]):
                continue
        lvl, kind = classify_numbering(f["text"])
        sc = score(f, font_p85, body_font, font_disc, use_v3, kind, lvl)
        if sc >= 0.5:
            preds.add(i)

    # 模式批量（Q200）：扫描全部正文段（含 NONE 档长段）按编号前缀归组，
    # 模拟「用户一键提升所有 N.N / N.N.N / 数字+空格 段为标题」
    batch_preds = set(preds)
    if use_v3:
        for i, f in enumerate(feats):
            if i < body_start or f["text"] in repeated or is_page_number(f["text"]):
                continue
            _, kind = classify_numbering(f["text"])
            if kind in ("heading", "weak_heading"):
                batch_preds.add(i)

    gt_idx = set()
    for i, f in enumerate(feats):
        if any(f["text"].startswith(pre) for pre in GT[docx_path.name]):
            gt_idx.add(i)

    def prf(pred):
        tp = len(pred & gt_idx); fp = len(pred - gt_idx); fn = len(gt_idx - pred)
        P = tp / (tp + fp) if (tp + fp) else 0.0
        R = tp / (tp + fn) if (tp + fn) else 0.0
        return tp, fp, fn, P, R, (2 * P * R / (P + R) if (P + R) else 0.0)

    tp, fp, fn, prec, rec, f1 = prf(preds)
    btp, bfp, bfn, bprec, brec, bf1 = prf(batch_preds)
    return {
        "feats": feats, "preds": preds, "batch_preds": batch_preds, "gt": gt_idx,
        "repeated": repeated, "body_start": body_start,
        "tp": tp, "fp": fp, "fn": fn, "prec": prec, "rec": rec, "f1": f1,
        "btp": btp, "bfp": bfp, "bfn": bfn, "bprec": bprec, "brec": brec, "bf1": bf1,
    }


if __name__ == "__main__":
    d = Path(
        r"d:\project devleoment\Claude code projects\smart sop\smart sop\smart sop"
        r"\docs\reference doc\typical word doc\无格式标题word"
    )
    files = sorted(d.glob("*.docx"))
    print(f"{'文件':<40}{'GT':>4}  {'v2 自动':>15}  {'v3 自动':>15}  {'v3+模式批量':>15}")
    agg = {"v2": [0, 0, 0], "v3": [0, 0, 0], "batch": [0, 0, 0]}
    details = []
    for docx in files:
        r2 = analyze(docx, use_v3=False)
        r3 = analyze(docx, use_v3=True)
        agg["v2"][0] += r2["tp"]; agg["v2"][1] += r2["fp"]; agg["v2"][2] += r2["fn"]
        agg["v3"][0] += r3["tp"]; agg["v3"][1] += r3["fp"]; agg["v3"][2] += r3["fn"]
        agg["batch"][0] += r3["btp"]; agg["batch"][1] += r3["bfp"]; agg["batch"][2] += r3["bfn"]
        name = docx.name[:38]
        print(f"{name:<40}{len(r3['gt']):>4}  "
              f"{r2['prec']:.2f}/{r2['rec']:.2f}/{r2['f1']:.2f}  "
              f"{r3['prec']:.2f}/{r3['rec']:.2f}/{r3['f1']:.2f}  "
              f"{r3['bprec']:.2f}/{r3['brec']:.2f}/{r3['bf1']:.2f}")
        details.append((docx.name, r3))

    print("-" * 95)
    labels = {"v2": "v2 自动", "v3": "v3 自动", "batch": "v3+模式批量"}
    for k in ("v2", "v3", "batch"):
        tp, fp, fn = agg[k]
        P = tp / (tp + fp) if (tp + fp) else 0
        R = tp / (tp + fn) if (tp + fn) else 0
        F = 2 * P * R / (P + R) if (P + R) else 0
        print(f"  {labels[k]:<12} micro: TP={tp} FP={fp} FN={fn}  P={P:.3f} R={R:.3f} F1={F:.3f}")

    # v3 残留 FP/FN 明细（看还差什么）
    print("\n=== v3 残留误报/漏报 ===")
    for name, r in details:
        feats = r["feats"]
        fps = sorted(r["preds"] - r["gt"])
        fns = sorted(r["gt"] - r["preds"])
        if fps or fns:
            print(f"\n📄 {name}  (body_start={r['body_start']}, 重复块剔除 {len(r['repeated'])} 种)")
            for i in fps[:8]:
                print(f"   FP @{i}: {feats[i]['text'][:46]}")
            for i in fns[:8]:
                print(f"   FN @{i}: {feats[i]['text'][:46]}")

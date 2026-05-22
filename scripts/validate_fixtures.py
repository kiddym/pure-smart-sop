"""验证 typical word doc 目录下 5 份真实 SOP 对方案约束的命中情况。

跑 4 件事：
  1. OPC parts 清单（验证页眉/页脚/脚注/批注/numbering 是否存在）
  2. 内容统计（segments / 图片 / 表格 / SDT / 文本框 / 公式）
  3. DPMS bug 命中清单（anchor 图 / 同段多图 / 表内图 / 嵌套表 / vMerge）
  4. find_body_start 4 信号在每份文档的命中情况，及融合后的 body_start_idx
"""
from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}
W = f"{{{NS['w']}}}"


def qn(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def local(tag: str) -> str:
    return etree.QName(tag).localname


def analyze(docx_path: Path) -> dict:
    out: dict = {"name": docx_path.name, "size_kb": docx_path.stat().st_size // 1024}

    with zipfile.ZipFile(docx_path) as z:
        names = z.namelist()
        out["opc"] = {
            "headers": [n for n in names if n.startswith("word/header") and n.endswith(".xml")],
            "footers": [n for n in names if n.startswith("word/footer") and n.endswith(".xml")],
            "footnotes": "word/footnotes.xml" in names,
            "comments": "word/comments.xml" in names,
            "numbering": "word/numbering.xml" in names,
            "styles": "word/styles.xml" in names,
            "media": [n for n in names if n.startswith("word/media/")],
            "embeddings": [n for n in names if n.startswith("word/embeddings/")],
        }

        doc_xml = z.read("word/document.xml")
        root = etree.fromstring(doc_xml)
        body = root.find(qn("w:body"))
        if body is None:
            return out

        children = list(body.iterchildren())
        out["body_top_level"] = {
            "count": len(children),
            "tags": dict(Counter(local(c.tag) for c in children)),
        }

        all_p = body.findall(f".//{qn('w:p')}")
        all_tbl = body.findall(f".//{qn('w:tbl')}")
        all_sdt = body.findall(f".//{qn('w:sdt')}")
        all_drawing = body.findall(f".//{qn('w:drawing')}")
        all_pict = body.findall(f".//{qn('w:pict')}")
        all_txbx = body.findall(f".//{qn('w:txbxContent')}")
        all_omath = body.findall(f".//{qn('m:oMath')}")

        non_empty_p = sum(1 for p in all_p if "".join(p.itertext()).strip())

        out["content"] = {
            "p_total": len(all_p),
            "p_non_empty": non_empty_p,
            "tbl_total": len(all_tbl),
            "sdt": len(all_sdt),
            "drawing": len(all_drawing),
            "pict_legacy": len(all_pict),
            "txbxContent": len(all_txbx),
            "oMath": len(all_omath),
        }

        # ── 图片细分（inline vs anchor） ──
        inline_n, anchor_n = 0, 0
        for d in all_drawing:
            if d.find(f".//{qn('wp:inline')}") is not None:
                inline_n += 1
            if d.find(f".//{qn('wp:anchor')}") is not None:
                anchor_n += 1
        out["img_detail"] = {
            "inline": inline_n,
            "anchor": anchor_n,
            "DPMS_anchor_lost": anchor_n,
        }

        # ── 同段多图 ──
        multi_paras, extra_imgs = 0, 0
        for p in all_p:
            blips = p.findall(f".//{qn('a:blip')}")
            if len(blips) > 1:
                multi_paras += 1
                extra_imgs += len(blips) - 1
        out["img_detail"]["multi_image_paragraphs"] = multi_paras
        out["img_detail"]["DPMS_extra_imgs_lost"] = extra_imgs

        # ── 表内图 ──
        table_imgs = sum(
            len(tbl.findall(f".//{qn('w:drawing')}")) for tbl in all_tbl
        )
        out["img_detail"]["table_inner_images"] = table_imgs
        out["img_detail"]["DPMS_table_imgs_lost"] = table_imgs

        # ── 嵌套表 ──
        nested = 0
        for tbl in all_tbl:
            nested += len(tbl.findall(f".//{qn('w:tbl')}"))
        out["table_detail"] = {
            "top_level_tbl": len(all_tbl) - nested,
            "nested_tbl": nested,
            "DPMS_nested_lost": nested,
        }

        # ── 合并单元格 ──
        vmerge_restart, vmerge_continue = 0, 0
        for vm in body.findall(f".//{qn('w:vMerge')}"):
            val = vm.get(qn("w:val"), "continue")
            if val == "restart":
                vmerge_restart += 1
            else:
                vmerge_continue += 1
        grid_spans = body.findall(f".//{qn('w:gridSpan')}")
        out["table_detail"].update(
            {
                "vMerge_restart": vmerge_restart,
                "vMerge_continue": vmerge_continue,
                "DPMS_vmerge_rowspan_wrong": vmerge_continue,
                "gridSpan": len(grid_spans),
            }
        )

        # ── 标题信号 ──
        style_counter: Counter[str] = Counter()
        outline_counter: Counter[str] = Counter()
        for p in all_p:
            pStyle = p.find(f".//{qn('w:pStyle')}")
            if pStyle is not None:
                style_counter[pStyle.get(qn("w:val"), "")] += 1
            outline = p.find(f".//{qn('w:outlineLvl')}")
            if outline is not None:
                outline_counter[outline.get(qn("w:val"), "")] += 1
        out["heading_signals"] = {
            "pStyle_top10": style_counter.most_common(10),
            "outlineLvl": dict(outline_counter),
        }

        # ── find_body_start 4 信号 ──
        body_start = simulate_find_body_start(children)
        out["find_body_start"] = body_start

    return out


def simulate_find_body_start(children: list) -> dict:
    """模拟方案中的 find_body_start 决策树。"""
    n = len(children)
    result: dict = {"total_children": n}

    # 信号 3: 第一个 Heading 1 (pStyle 或 outlineLvl=0)
    h1_aliases = {
        "Heading1", "Heading 1", "1", "标题 1", "标题1", "heading 1", "h1",
    }
    first_h1_idx = None
    for idx, child in enumerate(children):
        if local(child.tag) != "p":
            continue
        pStyle = child.find(f".//{qn('w:pStyle')}")
        if pStyle is not None:
            val = pStyle.get(qn("w:val"), "")
            if val in h1_aliases:
                first_h1_idx = idx
                break
        outline = child.find(f".//{qn('w:outlineLvl')}")
        if outline is not None and outline.get(qn("w:val")) == "0":
            first_h1_idx = idx
            break
    result["signal_3_first_h1"] = first_h1_idx

    # 信号 4: early sectPr (< 20%)
    threshold = max(1, int(n * 0.20))
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
    result["signal_4_early_sectpr_threshold"] = threshold
    result["signal_4_early_sectpr"] = early_sectpr

    # 信号 1: TOC fldChar
    toc_end_idx = None
    toc_open = False
    for idx, child in enumerate(children):
        if local(child.tag) != "p":
            continue
        for fc in child.findall(f".//{qn('w:fldChar')}"):
            ftype = fc.get(qn("w:fldCharType"))
            if ftype == "begin":
                # 找同段的 instrText
                run = fc.getparent()
                if run is None:
                    continue
                p = run.getparent()
                if p is None:
                    continue
                instr_texts = p.findall(f".//{qn('w:instrText')}")
                instr_blob = " ".join((it.text or "") for it in instr_texts)
                if "TOC" in instr_blob.upper():
                    toc_open = True
            elif ftype == "end" and toc_open:
                toc_end_idx = idx + 1
                toc_open = False
                break
        if toc_end_idx is not None:
            break
    result["signal_1_toc_field_end"] = toc_end_idx

    # 信号 2: bookmark _Toc (取最后一个 _Toc bookmarkStart 所在段 +1)
    bookmark_toc_idx = None
    for idx, child in enumerate(children):
        if local(child.tag) != "p":
            continue
        for bm in child.findall(f".//{qn('w:bookmarkStart')}"):
            name = bm.get(qn("w:name"), "")
            if name.startswith("_Toc"):
                bookmark_toc_idx = idx
    if bookmark_toc_idx is not None:
        bookmark_toc_idx += 1
    result["signal_2_bookmark_toc_end"] = bookmark_toc_idx

    # 融合 (max)
    candidates = [
        v for v in (toc_end_idx, bookmark_toc_idx, first_h1_idx, early_sectpr) if v is not None
    ]
    chosen = max(candidates) if candidates else None
    result["candidates"] = candidates
    result["chosen_body_start_idx"] = chosen
    result["skipped_blocks"] = chosen if chosen is not None else 0
    result["skipped_ratio"] = round((chosen or 0) / n, 3) if n else 0
    return result


def print_report(r: dict) -> None:
    print(f"\n{'='*70}")
    print(f"📄 {r['name']}  ({r['size_kb']} KB)")
    print(f"{'='*70}")
    opc = r["opc"]
    print(f"  OPC parts:")
    print(f"    headers={len(opc['headers'])}, footers={len(opc['footers'])}, "
          f"footnotes={opc['footnotes']}, comments={opc['comments']}, "
          f"numbering={opc['numbering']}")
    print(f"    media files: {len(opc['media'])}   embeddings: {len(opc['embeddings'])}")
    c = r["content"]
    print(f"  内容: p_total={c['p_total']} (非空 {c['p_non_empty']}), "
          f"tbl={c['tbl_total']}, sdt={c['sdt']}, drawing={c['drawing']}, "
          f"pict_legacy={c['pict_legacy']}, txbx={c['txbxContent']}, "
          f"oMath={c['oMath']}")
    id_ = r["img_detail"]
    print(f"  图片细分:")
    print(f"    inline={id_['inline']}, anchor={id_['anchor']}, "
          f"同段多图段落={id_['multi_image_paragraphs']} (额外丢失图 {id_['DPMS_extra_imgs_lost']})")
    print(f"    表内图={id_['table_inner_images']}")
    print(f"    ❌ DPMS 会丢: anchor {id_['DPMS_anchor_lost']} + "
          f"同段额外 {id_['DPMS_extra_imgs_lost']} + 表内 {id_['DPMS_table_imgs_lost']} = "
          f"{id_['DPMS_anchor_lost'] + id_['DPMS_extra_imgs_lost'] + id_['DPMS_table_imgs_lost']} 张")
    td = r["table_detail"]
    print(f"  表格细分:")
    print(f"    顶层={td['top_level_tbl']}, 嵌套={td['nested_tbl']}, "
          f"vMerge restart={td['vMerge_restart']}, continue={td['vMerge_continue']}, "
          f"gridSpan={td['gridSpan']}")
    print(f"    ❌ DPMS 会失真: 嵌套表 {td['DPMS_nested_lost']} 个 + "
          f"vMerge 行 {td['DPMS_vmerge_rowspan_wrong']} 个")
    hs = r["heading_signals"]
    print(f"  标题信号:")
    print(f"    pStyle top: {hs['pStyle_top10']}")
    print(f"    outlineLvl: {hs['outlineLvl']}")
    bs = r["find_body_start"]
    print(f"  find_body_start:")
    print(f"    总顶层节点 {bs['total_children']}, 20% 阈值 {bs['signal_4_early_sectpr_threshold']}")
    print(f"    信号1 TOC fld end:      {bs['signal_1_toc_field_end']}")
    print(f"    信号2 bookmark _Toc:    {bs['signal_2_bookmark_toc_end']}")
    print(f"    信号3 first H1:         {bs['signal_3_first_h1']}")
    print(f"    信号4 early sectPr:     {bs['signal_4_early_sectpr']}")
    print(f"    ➤ chosen = max{bs['candidates']} = {bs['chosen_body_start_idx']}")
    print(f"    ➤ 跳过 {bs['skipped_blocks']} 块 ({bs['skipped_ratio']*100:.1f}%)")


if __name__ == "__main__":
    docs_dir = Path(
        r"d:\project devleoment\Claude code projects\smart sop\smart sop\smart sop"
        r"\docs\reference doc\typical word doc"
    )
    results = [analyze(p) for p in sorted(docs_dir.glob("*.docx"))]
    for r in results:
        print_report(r)

    # 汇总
    print(f"\n\n{'='*70}\n📊 汇总（横向对比）\n{'='*70}")
    print(f"{'文件':<35} {'p':>5} {'tbl':>4} {'in':>4} {'anc':>4} {'mul':>4} "
          f"{'tbI':>4} {'nT':>3} {'vMc':>4} {'H1':>4} {'skip':>5}")
    for r in results:
        c = r["content"]
        id_ = r["img_detail"]
        td = r["table_detail"]
        bs = r["find_body_start"]
        name = r["name"][:33]
        print(f"{name:<35} "
              f"{c['p_total']:>5} {c['tbl_total']:>4} "
              f"{id_['inline']:>4} {id_['anchor']:>4} {id_['multi_image_paragraphs']:>4} "
              f"{id_['table_inner_images']:>4} {td['nested_tbl']:>3} "
              f"{td['vMerge_continue']:>4} "
              f"{(bs['signal_3_first_h1'] if bs['signal_3_first_h1'] is not None else -1):>4} "
              f"{bs['skipped_blocks']:>5}")

    out_path = Path(__file__).parent / "validate_fixtures.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  完整 JSON: {out_path}")

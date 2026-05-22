"""styles.xml 反查 + 同义词分类单测（M6.1，§25.4 Tier1）。"""

from __future__ import annotations

from app.parser import styles, synonyms
from app.parser.utils.opc import DocxPackage
from tests.unit.parser._docx_builder import DocxBuilder, styled_sop, synonym_sop


def _index(data: bytes) -> styles.StyleIndex:
    return styles.build_style_index(DocxPackage(data).styles)


def test_standard_heading_names_map_to_levels() -> None:
    idx = _index(styled_sop())
    # 反查：找到 name 含 "heading 1" 的样式 id，分类应得 level 1
    level_for_names = {
        info.name.lower(): styles.classify_heading_style(info.style_id, idx)
        for info in idx.all()
        if info.name
    }
    assert level_for_names.get("heading 1") == 1
    assert level_for_names.get("heading 2") == 2
    assert level_for_names.get("heading 3") == 3


def test_synonym_style_classified_via_dictionary() -> None:
    idx = _index(synonym_sop())
    syn = synonyms.load_default_synonyms()
    # 「章节标题」自定义样式 → L1（靠同义词词典命中）
    target = next(i for i in idx.all() if i.name == "章节标题")
    assert styles.classify_heading_style(target.style_id, idx, synonyms=syn) == 1


def test_non_heading_style_returns_none() -> None:
    idx = _index(styled_sop())
    normal = next((i for i in idx.all() if i.name and i.name.lower() == "normal"), None)
    if normal is not None:
        assert styles.classify_heading_style(normal.style_id, idx) is None
    assert styles.classify_heading_style("does-not-exist", idx) is None


def test_outline_lvl_fallback() -> None:
    data = DocxBuilder().styled_heading("条款", "自定义条款样式", outline_lvl=1).build()
    idx = _index(data)
    target = next(i for i in idx.all() if i.name == "自定义条款样式")
    # 无标准名 / 无同义词命中 → 靠 outlineLvl=1 → level 2
    assert styles.classify_heading_style(target.style_id, idx) == 2


def test_based_on_chain_recurses() -> None:
    # 自定义样式 basedOn Heading 1 → 上溯命中 level 1
    data = synonym_sop()
    pkg = DocxPackage(data)
    idx = styles.build_style_index(pkg.styles)
    # 构造一个 basedOn 指向同义词样式 id 的虚拟样式，验证递归
    syn = synonyms.load_default_synonyms()
    base = next(i for i in idx.all() if i.name == "章节标题")
    idx.by_id["VIRTUAL"] = styles.StyleInfo(
        style_id="VIRTUAL", name="我的派生样式", outline_lvl=None, based_on=base.style_id
    )
    assert styles.classify_heading_style("VIRTUAL", idx, synonyms=syn) == 1


def test_style_overrides_take_priority() -> None:
    idx = _index(synonym_sop())
    target = next(i for i in idx.all() if i.name == "章节标题")
    # heading_style_map（DB 层）注入：把「章节标题」覆盖为 L2（Q344 注入缝）
    overrides = {"章节标题": 2}
    assert styles.classify_heading_style(target.style_id, idx, style_overrides=overrides) == 2


def test_synonyms_default_dictionary_has_expected_levels() -> None:
    syn = synonyms.load_default_synonyms()
    assert syn["章节标题"] == 1
    assert syn["节标题"] == 2
    assert syn["条标题"] == 3

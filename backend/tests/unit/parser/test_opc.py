"""OPC 包遍历层单测（M6.1）。"""

from __future__ import annotations

from app.parser.utils import opc
from tests.unit.parser._docx_builder import styled_sop


def test_sniff_valid_docx() -> None:
    assert opc.is_docx_bytes(styled_sop()) is True


def test_sniff_rejects_non_zip() -> None:
    assert opc.is_docx_bytes(b"not a zip at all") is False


def test_sniff_rejects_plain_zip_without_document() -> None:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "hi")
    assert opc.is_docx_bytes(buf.getvalue()) is False


def test_package_exposes_document_and_body() -> None:
    pkg = opc.DocxPackage(styled_sop())
    assert pkg.document is not None
    assert pkg.body is not None
    # body 直接子元素应含若干 w:p
    paras = [c for c in pkg.body if opc.local(c.tag) == "p"]
    assert len(paras) >= 4


def test_package_exposes_styles() -> None:
    pkg = opc.DocxPackage(styled_sop())
    assert pkg.styles is not None


def test_media_resolves_via_rels() -> None:
    pkg = opc.DocxPackage(styled_sop())
    media = pkg.media_names()
    assert len(media) >= 1  # 内联图至少一张
    # rels 应能解析出图片 rId → media part
    rels = pkg.document_rels()
    image_targets = [t for t in rels.values() if "media/" in t]
    assert len(image_targets) >= 1


def test_qn_and_local() -> None:
    assert opc.qn("w:p") == f"{{{opc.NS['w']}}}p"
    assert opc.local(opc.qn("w:tbl")) == "tbl"

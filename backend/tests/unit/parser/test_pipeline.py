"""端到端管线单测（M6.2）：parse_docx 串联 normalize→structure。"""

from __future__ import annotations

from app.parser import parse_docx
from tests.unit.parser._docx_builder import styled_sop, unstyled_numbered_sop


def test_parse_docx_standard_styled() -> None:
    res = parse_docx(styled_sop(), "standard")
    assert res.parse_method == "standard"
    assert res.metadata.total_chapters >= 3
    assert res.metadata.body_start_detected_by == "first_styled_heading"
    assert any("media:" in r.placeholder for r in res.image_refs)


def test_parse_docx_smart_unstyled_produces_review() -> None:
    res = parse_docx(unstyled_numbered_sop(), "smart")
    assert res.parse_method == "smart"
    assert res.review_required >= 2
    assert len(res.detected_patterns) >= 1

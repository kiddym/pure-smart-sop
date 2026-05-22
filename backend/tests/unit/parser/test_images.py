"""图片工具单测（M6.3）：sha256 / 尺寸 / emf-wmf 优雅降级。"""

from __future__ import annotations

from app.parser.utils import images
from tests.unit.parser._docx_builder import tiny_png


def test_sha256_stable() -> None:
    png = tiny_png()
    assert images.sha256_hex(png) == images.sha256_hex(png)
    assert len(images.sha256_hex(png)) == 64


def test_sha256_distinguishes() -> None:
    assert images.sha256_hex(tiny_png((1, 2, 3))) != images.sha256_hex(tiny_png((9, 9, 9)))


def test_dimensions_png() -> None:
    w, h = images.dimensions(tiny_png(size=16))
    assert (w, h) == (16, 16)


def test_dimensions_invalid_returns_none() -> None:
    assert images.dimensions(b"not an image") == (None, None)


def test_mime_for_ext() -> None:
    assert images.mime_for_ext(".png") == "image/png"
    assert images.mime_for_ext(".jpg") == "image/jpeg"
    assert images.mime_for_ext(".jpeg") == "image/jpeg"


def test_is_supported_format() -> None:
    assert images.is_supported(".png")
    assert images.is_supported(".emf")
    assert not images.is_supported(".tiff")
    assert not images.is_supported(".exe")


def test_convert_degrades_when_soffice_missing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(images.shutil, "which", lambda _name: None)
    assert images.soffice_available() is False
    # emf/wmf 转换在无 soffice 时返回 None（调用方降级为 placeholder + review，Q216）
    assert images.convert_to_png(b"\x01\x00\x00\x00fake-emf", ".emf") is None

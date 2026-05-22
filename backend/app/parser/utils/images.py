"""图片工具：sha256 去重键、像素尺寸、emf/wmf→png（LibreOffice 优雅降级）。

§27.3 / Q207：白名单 png/jpg/jpeg/gif/bmp/webp/emf/wmf；emf/wmf 服务端转 png。
Q216：LibreOffice headless 转换；soffice 缺失或转换失败 → 返回 None，调用方降级
为 placeholder + review，**不阻断整体解析**（测试可 monkeypatch shutil.which）。
"""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

SUPPORTED_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".emf", ".wmf"})
VECTOR_EXTS = frozenset({".emf", ".wmf"})

_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dimensions(data: bytes) -> tuple[int | None, int | None]:
    """返回 (width, height)；无法识别（如 emf/wmf 或损坏）返回 (None, None)。"""
    try:
        with Image.open(io.BytesIO(data)) as img:
            return int(img.width), int(img.height)
    except Exception:
        return None, None


def is_supported(ext: str) -> bool:
    return _norm_ext(ext) in SUPPORTED_EXTS


def mime_for_ext(ext: str) -> str:
    return _MIME.get(_norm_ext(ext), "application/octet-stream")


def soffice_available() -> bool:
    return _soffice_path() is not None


def convert_to_png(data: bytes, ext: str) -> bytes | None:
    """emf/wmf → png（LibreOffice headless）。失败 / soffice 缺失返回 None。"""
    soffice = _soffice_path()
    if soffice is None:
        return None
    ext = _norm_ext(ext)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{ext}"
        src.write_bytes(data)
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "png", "--outdir", tmp, str(src)],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        out = Path(tmp) / "input.png"
        if out.exists():
            return out.read_bytes()
    return None


def _soffice_path() -> str | None:
    for name in ("soffice", "soffice.exe", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _norm_ext(ext: str) -> str:
    ext = ext.lower()
    return ext if ext.startswith(".") else f".{ext}"

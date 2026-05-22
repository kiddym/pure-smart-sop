"""存储路径助手（Q342）。

集中派生永久 asset 目录与临时上传目录，运行时从 settings 读取（测试可
monkeypatch ``settings.storage_dir``）。永久 asset 落 ``{storage}/asset/{sha[:2]}/{sha}.{ext}``，
临时上传落 ``{storage}/tmp/uploads/{token}/``。
"""

from __future__ import annotations

from pathlib import Path

from app.config import settings


def storage_root() -> Path:
    return Path(settings.storage_dir)


def asset_root() -> Path:
    return storage_root() / "asset"


def tmp_upload_root() -> Path:
    return storage_root() / "tmp" / "uploads"


def asset_path(sha256: str, ext: str) -> Path:
    """永久 asset 物理路径：按 sha256 前 2 位分桶。"""
    ext = ext if ext.startswith(".") else f".{ext}"
    return asset_root() / sha256[:2] / f"{sha256}{ext}"


def token_dir(token: str) -> Path:
    return tmp_upload_root() / token


def token_media_dir(token: str) -> Path:
    return token_dir(token) / "media"

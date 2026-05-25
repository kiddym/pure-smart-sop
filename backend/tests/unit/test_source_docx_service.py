"""P1 源 docx：存储路径 + 模型登记 + 服务存取删。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app import storage
from app.models import Base
from app.services import source_docx_service, upload_service
from tests.unit.parser._docx_builder import styled_sop


def test_source_docx_path_under_group(storage_tmp: Path) -> None:
    p = storage.source_docx_path("grp-1")
    assert p == storage_tmp / "source_docx" / "grp-1" / "source.docx"


def test_model_registered_in_metadata() -> None:
    assert "tb_procedure_source_docx" in Base.metadata.tables


def test_store_from_token_writes_row_and_file(db: Session, storage_tmp: Path) -> None:
    up = upload_service.save_upload(styled_sop(), "原文.docx")
    row = source_docx_service.store_from_token(db, procedure_group_id="grp-1", upload_token=up.upload_token)
    assert row is not None
    assert row.filename == "原文.docx"
    assert row.size_bytes > 0 and len(row.sha256) == 64
    assert storage.source_docx_path("grp-1").exists()


def test_store_from_token_degrades_without_token(db: Session, storage_tmp: Path) -> None:
    assert source_docx_service.store_from_token(db, procedure_group_id="g", upload_token=None) is None
    assert source_docx_service.store_from_token(db, procedure_group_id="g", upload_token="ghost") is None


def test_delete_for_group_removes_row_and_file(db: Session, storage_tmp: Path) -> None:
    up = upload_service.save_upload(styled_sop(), "a.docx")
    source_docx_service.store_from_token(db, procedure_group_id="grp-9", upload_token=up.upload_token)
    assert storage.source_docx_path("grp-9").exists()
    source_docx_service.delete_for_group(db, "grp-9")
    assert not storage.source_docx_path("grp-9").exists()

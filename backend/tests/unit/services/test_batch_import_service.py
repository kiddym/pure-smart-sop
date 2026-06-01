"""批次暂存路径 + 创建/查询 service 测试。"""

from __future__ import annotations

from app import storage


def test_batch_paths_are_nested_under_storage_root(monkeypatch) -> None:
    import app.config as config_mod

    monkeypatch.setattr(config_mod.settings, "storage_dir", "/tmp/sop-test-store")
    docx = storage.batch_docx_path("job1", "item1")
    blob = storage.batch_blob_path("job1", "item1")
    media = storage.batch_media_dir("job1", "item1")
    assert docx.as_posix().endswith("batch/job1/item1/source.docx")
    assert blob.as_posix().endswith("batch/job1/item1/parse.json")
    assert media.as_posix().endswith("batch/job1/item1/media")

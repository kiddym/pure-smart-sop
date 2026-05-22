"""optimistic_lock 单测（Q18 / data-model §4.6）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services import optimistic_lock


def test_ensure_if_match_missing_raises_412() -> None:
    with pytest.raises(HTTPException) as exc:
        optimistic_lock.ensure_if_match(None)
    assert exc.value.status_code == 412
    assert exc.value.detail["code"] == "IF_MATCH_REQUIRED"


def test_ensure_if_match_blank_raises_412() -> None:
    with pytest.raises(HTTPException) as exc:
        optimistic_lock.ensure_if_match("   ")
    assert exc.value.status_code == 412


def test_ensure_if_match_invalid_raises_412() -> None:
    with pytest.raises(HTTPException) as exc:
        optimistic_lock.ensure_if_match("not-a-number")
    assert exc.value.status_code == 412


def test_ensure_if_match_parses_quoted_and_weak_etag() -> None:
    assert optimistic_lock.ensure_if_match("7") == 7
    assert optimistic_lock.ensure_if_match('"7"') == 7
    assert optimistic_lock.ensure_if_match('W/"7"') == 7


def test_verify_revision_match_ok() -> None:
    optimistic_lock.verify_revision(current=3, expected=3)  # 不抛


def test_verify_revision_mismatch_raises_409() -> None:
    with pytest.raises(HTTPException) as exc:
        optimistic_lock.verify_revision(current=4, expected=3)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "VERSION_CONFLICT"


def test_bump_increments_revision() -> None:
    class _Obj:
        revision = 5

    obj = _Obj()
    optimistic_lock.bump(obj)
    assert obj.revision == 6

"""健康检查与 request-id 中间件集成测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import Engine


def test_healthz_returns_ok(client) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_ok_when_db_reachable(
    client, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.engine", engine)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["db"] == "up"


def test_readyz_503_when_db_down(client, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import create_engine

    broken = create_engine("sqlite:///file:nonexistent?mode=ro&uri=true")
    monkeypatch.setattr("app.main.engine", broken)
    resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["db"] == "down"


def test_request_id_echoed_when_provided(client) -> None:
    resp = client.get("/healthz", headers={"X-Request-Id": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"


def test_request_id_generated_when_absent(client) -> None:
    resp = client.get("/healthz")
    assert resp.headers.get("x-request-id")

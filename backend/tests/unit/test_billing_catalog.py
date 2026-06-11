"""三档 catalog 纯函数：SOP 为各档位基础能力（含 free / 失效状态均可用）。"""

from app.billing.catalog import (
    PLAN_CATALOG,
    Feature,
    Plan,
    effective_features,
    effective_seat_limit,
)


def test_catalog_shape():
    assert PLAN_CATALOG[Plan.free].seat_limit == 3
    # SOP 为基础能力：所有档位（含 free）均含。
    assert PLAN_CATALOG[Plan.free].features == {Feature.sop}
    assert PLAN_CATALOG[Plan.pro].seat_limit == 15
    assert PLAN_CATALOG[Plan.enterprise].seat_limit is None
    assert PLAN_CATALOG[Plan.pro].features == {Feature.sop}
    assert PLAN_CATALOG[Plan.enterprise].features == {Feature.sop}


def test_effective_features_active_unlocks_plan():
    assert effective_features("pro", "active") == {Feature.sop}
    assert effective_features("free", "active") == {Feature.sop}
    assert effective_features("enterprise", "trialing") == {Feature.sop}


def test_effective_features_inactive_downgrades_to_free():
    # 失效降级到 free，而 free 仍含 SOP —— SOP 永不被订阅状态门控。
    for status in ("past_due", "canceled", "suspended"):
        assert effective_features("pro", status) == {Feature.sop}
        assert effective_features("enterprise", status) == {Feature.sop}


def test_effective_seat_limit():
    assert effective_seat_limit("free", "active") == 3
    assert effective_seat_limit("pro", "active") == 15
    assert effective_seat_limit("enterprise", "active") is None
    # 失效降到 free=3
    assert effective_seat_limit("pro", "canceled") == 3
    assert effective_seat_limit("enterprise", "suspended") == 3


def test_unknown_or_null_plan_treated_as_free():
    assert effective_features(None, "active") == {Feature.sop}
    assert effective_features("bogus", "active") == {Feature.sop}
    assert effective_seat_limit(None, "active") == 3

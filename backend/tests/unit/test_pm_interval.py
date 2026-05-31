from datetime import date

from app.models.pm_frequency import PMFrequencyUnit as U
from app.services.pm_service import _add_interval, _advance_due


def test_add_interval_day_week():
    assert _add_interval(date(2026, 6, 1), U.DAY, 5) == date(2026, 6, 6)
    assert _add_interval(date(2026, 6, 1), U.WEEK, 2) == date(2026, 6, 15)


def test_add_interval_month_clamps_end_of_month():
    assert _add_interval(date(2026, 1, 31), U.MONTH, 1) == date(2026, 2, 28)
    assert _add_interval(date(2026, 1, 31), U.MONTH, 13) == date(2027, 2, 28)
    assert _add_interval(date(2024, 1, 31), U.MONTH, 1) == date(2024, 2, 29)  # 闰年


def test_add_interval_month_crosses_year():
    assert _add_interval(date(2026, 11, 15), U.MONTH, 3) == date(2027, 2, 15)


def test_advance_due_skips_missed_periods_to_future():
    # next_due 远在过去，today 在多期之后：应一路跳到 today 之后第一个点
    nd = _advance_due(date(2026, 1, 1), U.DAY, 7, today=date(2026, 2, 1))
    assert nd > date(2026, 2, 1)
    # 锚定计划日历：从 1/1 起每 7 天的格点
    assert (nd - date(2026, 1, 1)).days % 7 == 0


def test_advance_due_no_op_when_future():
    # next_due 已在未来：不推进
    assert _advance_due(date(2026, 6, 1), U.DAY, 7, today=date(2026, 5, 1)) == date(2026, 6, 1)

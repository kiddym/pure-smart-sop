"""PM 服务：CRUD、customId、enable/disable、生单+锥摆推进、活动时间线。

调度任务与手动端点共用 generate_once。工单服务在函数内 import 避免循环依赖。
"""
from __future__ import annotations

import calendar
from datetime import date

from app.models.pm_frequency import PMFrequencyUnit


def _add_interval(d: date, unit: PMFrequencyUnit, value: int) -> date:
    """在 d 上加 value 个 unit。MONTH 钳制到目标月最后一天。"""
    if unit == PMFrequencyUnit.DAY:
        from datetime import timedelta
        return d + timedelta(days=value)
    if unit == PMFrequencyUnit.WEEK:
        from datetime import timedelta
        return d + timedelta(days=value * 7)
    # MONTH
    total = (d.year * 12 + (d.month - 1)) + value
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _advance_due(next_due: date, unit: PMFrequencyUnit, value: int, *, today: date) -> date:
    """锥摆推进：从 next_due 连加周期直到 > today（一期一单、不补单）。
    next_due 已在未来时为 no-op。value>=1 保证严格递增、不死循环。"""
    nd = next_due
    while nd <= today:
        nd = _add_interval(nd, unit, value)
    return nd

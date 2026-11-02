"""The days Ginnie Mae's disclosures keep, and each factor's dates.

**A factor's dates** (contract v29, W10.4; the fixtures' convention). Ginnie
Mae names its factor files by the month the factor reflects, which is the
contract's `factor_month` (`factorA2_202609` states the factors as of 30
September 2026, published in October), so a fill settling in October takes
the row of September (991). Its header states the as-of date, the factor
month's last day, which is the pool's record date, and the day the file was
published. A pool pays on the 15th (Ginnie I, a 45-day delay) or the 20th
(Ginnie II, 50 days) of the month after the factor month (the Ginnie Mae MBS
Guide, chapter 15; contract v29's research note), moved to the next business
day. A REMIC tranche's payment date and record date are the REMIC factor
file's own.

The business days are the Federal Reserve's: Ginnie Mae publishes on its
business days, and a payment due on a holiday or a weekend is made on the
next. Factor A is published on the fourth business day after the factor
month, Factor B on the sixth.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

#: Each program's payment delay and the day of the month after the factor
#: month it pays on.
PROGRAMS: dict[str, tuple[int, int]] = {"I": (45, 15), "II": (50, 20)}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def holidays(year: int) -> frozenset[date]:
    """The Federal Reserve's holidays of a year, as observed: a Sunday's on
    the Monday after, a Saturday's not moved."""
    fixed = [date(year, 1, 1), date(year, 7, 4), date(year, 11, 11), date(year, 12, 25)]
    if year >= 2022:
        fixed.append(date(year, 6, 19))
    observed = {d + timedelta(days=1) if d.weekday() == 6 else d for d in fixed}
    observed |= {
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _nth_weekday(year, 5, 0, -1),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 10, 0, 2),
        _nth_weekday(year, 11, 3, 4),
    }
    return frozenset(observed)


def on_or_after(day: date) -> date:
    while day.weekday() >= 5 or day in holidays(day.year):
        day += timedelta(days=1)
    return day


def nth_business_day(year: int, month: int, n: int) -> date:
    day = on_or_after(date(year, month, 1))
    for _ in range(n - 1):
        day = on_or_after(day + timedelta(days=1))
    return day


def add_months(month: str, count: int) -> str:
    """A month YYYYMM moved by `count` months."""
    if len(month) != 6 or not month.isdigit():
        raise ValueError(f"a month is YYYYMM, not {month!r}")
    index = int(month[:4]) * 12 + int(month[4:]) - 1 + count
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def payment_date(month: str, program: str) -> date | None:
    """When a pool of a program pays a factor month's distribution."""
    if program not in PROGRAMS:
        return None
    after = add_months(month, 1)
    return on_or_after(date(int(after[:4]), int(after[4:]), PROGRAMS[program][1]))


def latest_month(today: date) -> str:
    """The latest factor month whose Factor A is published by `today`: last
    month's from this month's fourth business day, else the month before."""
    this = f"{today.year:04d}{today.month:02d}"
    back = 1 if today >= nth_business_day(today.year, today.month, 4) else 2
    return add_months(this, -back)

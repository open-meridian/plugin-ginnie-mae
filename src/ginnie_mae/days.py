"""A Ginnie Mae factor's dates.

Ginnie Mae names its factor files by the month the factor reflects, which is
the contract's `factor_month` (`factorA2_202609` states the factors as of 30
September 2026, published in October), so a fill settling in October takes
the row of September (991). Its header states the as-of date, the factor
month's last day, which is the pool's record date, and the day the file was
published. A pool pays on the 15th (Ginnie I, a 45-day delay) or the 20th
(Ginnie II, 50 days) of the month after the factor month (the Ginnie Mae MBS
Guide, chapter 15; contract v29's research note), moved to the next business
day by the record's payment calendar, else the deployment's US dollar
calendar (`agency.Days`), and unset where the calendar does not answer. A
REMIC tranche's payment date and record date are the REMIC factor file's own.
Factor A is published on the fourth business day after the factor month.
"""

from __future__ import annotations

from datetime import date

from .agency import Days, add_months

#: Each program's payment delay and the day of the month after the factor
#: month it pays on.
PROGRAMS: dict[str, tuple[int, int]] = {"I": (45, 15), "II": (50, 20)}

__all__ = ["PROGRAMS", "add_months", "latest_month", "payment_date"]


async def payment_date(month: str, program: str, days: Days, calendar_id: str = "") -> date | None:
    """When a pool of a program pays a factor month's distribution; None for
    a program not known, or a day the calendar does not answer for."""
    if program not in PROGRAMS:
        return None
    after = add_months(month, 1)
    nominal = date(int(after[:4]), int(after[4:]), PROGRAMS[program][1])
    return await days.on_or_after(nominal, calendar_id)


async def latest_month(today: date, days: Days) -> str:
    """The latest factor month whose Factor A is published by `today`: last
    month's from this month's fourth business day, else the month before
    (and the month before where the calendar does not say)."""
    this = f"{today.year:04d}{today.month:02d}"
    fourth = await days.nth_business_day(today.year, today.month, 4)
    back = 1 if fourth is not None and today >= fourth else 2
    return add_months(this, -back)

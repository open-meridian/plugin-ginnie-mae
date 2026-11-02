"""Ginnie Mae's disclosure layouts, read: a factor file's header and pool
records, and a REMIC factor file's header and tranche records.

Ginnie Mae publishes its own fixed-width formats, each with a layout and a
sample file on its Disclosure Data Download (`factorA1_layout.pdf`,
`factorA2_layout.pdf`, `factorB1_layout.pdf`, `factorB2_layout.pdf`,
`remic1_layout.pdf`).

**Factor file** (Factor A, preliminary, and Factor B, final; Ginnie I and
Ginnie II pools, one 171-character record a pool), after a header: the
transmission's (`HDR...`) and the file's own, naming its program and update
and two dates, YYMMDD -- the factor's as-of date, the factor month's last
day, and the day it was published (`GNMA II  UPDATE 01     120331  120405`).
A pool's record: pool number (1-6), pool indicator (7), issuer number
(8-11), issuer name (13-72), original aggregate amount (73-87, 13.2),
remaining security RPB (88-102, 13.2), RPB factor (103-111, 1.8), pool
interest rate (112-116, 2.3), pool type (117-118), issue and maturity dates
(119-124, 125-130, MMDDYY), and the CUSIP (163-171); a Ginnie II record also
its margin and adjustment dates (131-162), not read.

**REMIC factor file** (`remic1`, `remic2`): a header record (indicator 1)
with its run date and record date (MM/DD/YYYY, the record date the last day
of the month before the run), a record per tranche (indicator 2): series
(`GNMA-2002-005O`), tranche name, CUSIP, tranche factor (`##.00000000`),
coupon rate, final distribution date, original and current balance, payment
date and first accrual date (YYYYMMDD); and a footer of totals (indicator 3).

Every number is read from its text as a `Decimal`, exactly; implied
decimals placed as the layout says. A record that does not read is returned
as not read, with why.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

_HEADER = re.compile(r"GNMA\s+(I{1,2})\s+UPDATE\s+(\d+)\s+(\d{6})\s+(\d{6})")
_REMIC_HEADER = re.compile(r"^1\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})")


@dataclass(frozen=True)
class FactorHeader:
    """A factor file's own header: its program, update, as-of and
    publication dates."""

    program: str
    update: int
    as_of: date
    published: date


@dataclass(frozen=True)
class PoolRow:
    """One pool's record of a factor file."""

    line: int
    pool: str
    indicator: str
    issuer: str
    original: Decimal
    remaining: Decimal
    factor: Decimal
    rate: Decimal
    pool_type: str
    issue_date: date | None
    maturity_date: date | None
    cusip: str


@dataclass(frozen=True)
class RemicHeader:
    run_date: date
    record_date: date


@dataclass(frozen=True)
class TrancheRow:
    """One tranche's record of a REMIC factor file."""

    line: int
    series: str
    tranche: str
    cusip: str
    factor: Decimal
    coupon: Decimal | None
    final_distribution: date | None
    original: Decimal | None
    current: Decimal | None
    payment_date: date | None
    first_accrual: date | None


@dataclass(frozen=True)
class Unread:
    line: int
    why: str


def text_of(body: bytes) -> str:
    """A file's text: the first member of a zip, else the bytes as text."""
    if body[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = [m for m in archive.namelist() if not m.endswith("/")]
            return archive.read(members[0]).decode("latin-1") if members else ""
    return body.decode("latin-1")


def lines(text: str) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(io.StringIO(text), start=1):
        yield number, line.rstrip("\r\n")


def _implied(text: str, places: int) -> Decimal | None:
    digits = text.strip()
    if not digits.isdigit():
        return None
    return Decimal(digits).scaleb(-places)


def _yymmdd(text: str) -> date | None:
    if len(text) != 6 or not text.isdigit():
        return None
    year = int(text[:2])
    try:
        return date(2000 + year if year < 70 else 1900 + year, int(text[2:4]), int(text[4:]))
    except ValueError:
        return None


def _mmddyy(text: str) -> date | None:
    if len(text) != 6 or not text.isdigit() or text == "000000":
        return None
    return _yymmdd(text[4:] + text[:4])


def _yyyymmdd(text: str) -> date | None:
    text = text.strip()
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        return None


def _slashed(text: str) -> date | None:
    try:
        month, day, year = (int(part) for part in text.split("/"))
        return date(year, month, day)
    except ValueError:
        return None


def _decimal(text: str) -> Decimal | None:
    text = text.strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def factor_header(text: str) -> FactorHeader | None:
    """A factor file's own header, from its first lines; None where none."""
    for _, line in list(lines(text))[:6]:
        found = _HEADER.search(line)
        if found:
            as_of, published = _yymmdd(found.group(3)), _yymmdd(found.group(4))
            if as_of is not None and published is not None:
                return FactorHeader(found.group(1), int(found.group(2)), as_of, published)
    return None


def pool_row(number: int, line: str) -> PoolRow | Unread | None:
    """A pool's record, None for a line that is no pool record (a header,
    a sample's caption, a blank), or why it did not read."""
    if len(line) < 130 or line.startswith(("HDR", "GNMA")) or not line[:6].strip():
        return None
    factor = _implied(line[102:111], 8)
    original = _implied(line[72:87], 2)
    remaining = _implied(line[87:102], 2)
    rate = _implied(line[111:116], 3)
    if factor is None:
        return Unread(number, f"RPB factor (103-111) {line[102:111]!r} is not a number")
    if original is None or remaining is None or rate is None:
        return Unread(number, "an amount or the interest rate (73-116) is not a number")
    return PoolRow(
        line=number,
        pool=line[:6].strip(),
        indicator=line[6:7],
        issuer=line[12:72].strip(),
        original=original,
        remaining=remaining,
        factor=factor,
        rate=rate,
        pool_type=line[116:118].strip(),
        issue_date=_mmddyy(line[118:124]),
        maturity_date=_mmddyy(line[124:130]),
        cusip=line[162:171].strip(),
    )


def remic_header(text: str) -> RemicHeader | None:
    for _, line in list(lines(text))[:3]:
        found = _REMIC_HEADER.match(line)
        if found:
            run, record = _slashed(found.group(1)), _slashed(found.group(2))
            if run is not None and record is not None:
                return RemicHeader(run, record)
    return None


def tranche_row(number: int, line: str) -> TrancheRow | Unread | None:
    """A tranche's record (indicator 2), None for any other, or why it did
    not read."""
    if not line.startswith("2") or len(line) < 99:
        return None
    factor = _decimal(line[34:45])
    if factor is None or factor < 0:
        return Unread(number, f"tranche factor (35-45) {line[34:45]!r} is not a number")
    return TrancheRow(
        line=number,
        series=line[1:16].strip(),
        tranche=line[16:25].strip(),
        cusip=line[25:34].strip(),
        factor=factor,
        coupon=_decimal(line[45:56]),
        final_distribution=_yyyymmdd(line[56:65]),
        original=_decimal(line[65:82]),
        current=_decimal(line[82:99]),
        payment_date=_yyyymmdd(line[99:108]),
        first_accrual=_yyyymmdd(line[108:117]),
    )


def same_pool(one: str, other: str) -> bool:
    """Whether two writings of a pool number name one: alike ignoring case,
    and a number's leading zeros (`000004` and `4`)."""

    def plain(text: str) -> str:
        text = text.strip().upper()
        return text.lstrip("0") or "0" if text.isdigit() else text

    return bool(one.strip()) and plain(one) == plain(other)


def same_series(one: str, other: str) -> bool:
    """Whether two writings of a REMIC series name one: letters and digits
    alike, ignoring case, spaces, hyphens and Ginnie Mae's `GNMA` prefix --
    `GNMA-2002-005O`, `GNMA 2002-005O` and `2002-005O` are one."""

    def plain(text: str) -> str:
        text = text.strip().upper()
        if text.startswith("GNMA"):
            text = text[4:]
        return "".join(c for c in text if c.isalnum())

    return bool(plain(one)) and plain(one) == plain(other)

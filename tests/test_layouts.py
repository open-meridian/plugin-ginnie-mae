"""Ginnie Mae's layouts read, on its own published sample files
(tests/responses/, as its Disclosure Data Download publishes them beside
each layout)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from ginnie_mae.layouts import (
    PoolRow,
    TrancheRow,
    factor_header,
    lines,
    pool_row,
    remic_header,
    same_pool,
    same_series,
    text_of,
    tranche_row,
)

TESTS = Path(__file__).parent / "responses"


def read(name: str) -> str:
    return text_of((TESTS / name).read_bytes())


def test_factor_a_ginnie_ii_sample() -> None:
    text = read("factorA2_sample.txt")
    header = factor_header(text)
    assert header is not None
    assert (header.program, header.update, header.as_of, header.published) == (
        "II",
        1,
        date(2012, 3, 31),
        date(2012, 4, 5),
    )
    rows = [r for n, line in lines(text) if isinstance(r := pool_row(n, line), PoolRow)]
    assert len(rows) == 15
    first = rows[0]
    assert (first.pool, first.indicator, first.issuer) == ("AA0912", "C", "QUICKEN LOANS, INC")
    assert (first.original, first.remaining, first.factor, first.rate) == (
        Decimal("1748677.00"),
        Decimal("1733859.95"),
        Decimal("0.99152671"),
        Decimal("3.500"),
    )
    assert (first.pool_type, first.issue_date, first.maturity_date, first.cusip) == (
        "SF",
        date(2012, 3, 1),
        date(2027, 3, 20),
        "36177XAM0",
    )
    numbered = next(r for r in rows if r.pool == "000004")
    assert numbered.indicator == "M" and numbered.issue_date == date(1992, 7, 1)


def test_factor_b_and_ginnie_i_samples() -> None:
    final = factor_header(read("factorB2_sample.txt"))
    assert final is not None and (final.update, final.published) == (2, date(2012, 4, 9))
    ginnie_i = factor_header(read("factorB1_sample.txt"))
    assert ginnie_i is not None and ginnie_i.program == "I"
    text = read("factorA1_sample.txt")
    assert any(isinstance(pool_row(n, line), PoolRow) for n, line in lines(text))


def test_remic_sample() -> None:
    text = read("remic1_sample.txt")
    header = remic_header(text)
    assert header is not None
    assert (header.run_date, header.record_date) == (date(2012, 3, 14), date(2012, 2, 29))
    rows = [r for n, line in lines(text) if isinstance(r := tranche_row(n, line), TrancheRow)]
    first = rows[0]
    assert (first.series, first.tranche, first.cusip) == ("GNMA-1994-001", "PK", "3837H0AG8")
    assert (first.factor, first.coupon, first.payment_date) == (
        Decimal(".21552923"),
        Decimal("7.90000"),
        date(2012, 3, 16),
    )
    assert first.original == Decimal("26635000.00") and first.final_distribution == date(
        2024, 6, 16
    )


def test_names_written_two_ways() -> None:
    assert same_pool("000004", "4") and same_pool("aa0912", "AA0912")
    assert not same_pool("", "")
    assert same_series("GNMA-2002-005O", "2002-005O") and same_series("GNMA 2002-005O", "2002005O")


async def test_a_file_kept_before_a_restart_is_the_same_raw_record(tmp_path: Path) -> None:
    from ginnie_mae.files import Samples, Store

    fetched = await Samples().get("factorA2_202610")
    assert fetched is not None
    first, new = Store(tmp_path).keep(fetched)
    assert new
    again, new = Store(tmp_path).keep(fetched)
    assert not new and again.key == first.key and again.path == first.path

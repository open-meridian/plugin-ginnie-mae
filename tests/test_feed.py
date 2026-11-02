"""The data role on the samples: a Ginnie II pool's and a REMIC tranche's
factors recorded when the lake wants them, Factor B as the next version,
and what it does not serve declined with why."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from ginnie_mae import days
from ginnie_mae.agency import Days
from ginnie_mae.feed import Disclosures, identify
from ginnie_mae.terms import Terms

from conftest import (
    BOND,
    FANNIE_POOL,
    INSTANCE,
    NOT_PUBLISHED,
    POOL,
    TRANCHE,
    answering,
    factors,
    feed,
    library,
    records,
    want,
)


def recorder() -> Recorder:
    return answering(Recorder(INSTANCE))


async def test_a_pools_factors_as_the_fixtures_key_them(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    rows = factors(lake)
    # October's Factor A (its Factor B not yet published), then September's
    # Factor B, which supersedes its Factor A.
    assert [(r.meta.row_key, str(as_decimal(r.factor)), r.meta.business_date) for r in rows] == [
        ("GNMA:AA0912:202610", "0.83102210", "2026-11-05"),
        ("GNMA:AA0912:202609", "0.84017733", "2026-10-08"),
    ]
    october = rows[0]
    assert (october.factor_month, october.record_date, october.payment_date) == (
        "202610",
        "2026-10-31",
        "2026-11-20",
    )
    assert october.meta.business_date == "2026-11-05"
    assert october.meta.source.dataset == f"{INSTANCE}:ginnie_mae"
    assert october.meta.raw.key.endswith("#3")
    assert not october.HasField("wac") and not october.meta.source_times
    assert rows[1].payment_date == "2026-10-20"
    assert POOL in work.held and not lake.on("DeclineWant")


async def test_factor_b_is_the_rows_next_version(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    await work.check()
    await work.check()
    final = lake.on("RecordFactors")[-1].factors
    assert [(r.meta.row_key, str(as_decimal(r.factor)), r.meta.business_date) for r in final] == [
        ("GNMA:AA0912:202609", "0.84017733", "2026-10-08"),
        ("GNMA:AA0912:202610", "0.83102211", "2026-11-09"),
    ]
    counted = work.wants.sent_to("ginnie_mae")
    assert counted.restated == 1


async def test_a_tranche_with_its_period_coupon(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-2", [TRANCHE]).message)
    await lake.hear(work, "ObservationsWanted")
    rows = {r.meta.row_key: r for r in factors(lake)}
    assert sorted(rows) == ["GNMA:GNMA-2002-005O:SP:202609", "GNMA:GNMA-2002-005O:SP:202610"]
    october = rows["GNMA:GNMA-2002-005O:SP:202610"]
    assert str(as_decimal(october.factor)) == "0.40873002"
    assert str(as_decimal(october.coupon_rate)) == "5.34000"
    assert (october.record_date, october.payment_date) == ("2026-10-31", "2026-11-16")
    assert october.meta.business_date == "2026-11-13"


async def test_what_it_does_not_serve_is_declined_with_why(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer(
        "ObservationsWanted", lambda _: want("w-3", [BOND, FANNIE_POOL, NOT_PUBLISHED]).message
    )
    await lake.hear(work, "ObservationsWanted")
    declined = {
        (s.entity_id, ops.UnansweredReason.Name(p.reason))
        for p in lake.on("DeclineWant")
        for s in p.subjects
    }
    assert declined == {
        (BOND, "UNANSWERED_REASON_NOT_COVERED"),
        (FANNIE_POOL, "UNANSWERED_REASON_NOT_COVERED"),
        (NOT_PUBLISHED, "UNANSWERED_REASON_SOURCE_SILENT"),
    }


async def test_a_pool_number_meeting_two_records_is_never_recorded(tmp_path: Path) -> None:
    lake = answering(Recorder(INSTANCE), ambiguous=True)
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-4", [POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    [missing] = lake.on("ReportMissingInstrument")
    assert missing.reason == ops.MISS_REASON_AMBIGUOUS and not factors(lake)


async def test_terms_offered_to_the_pools_record(tmp_path: Path) -> None:
    lake = recorder()
    terms = lake.bind(Terms())
    work = feed(lake, tmp_path, terms=terms)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    latest = {f.path: f.value for f in lake.on("OfferTemplateFields")[-1].fields}
    assert latest == {
        "agency": "MORTGAGE_AGENCY_GNMA",
        "pool_number": "AA0912",
        "pass_through_rate": "3.500",
        "original_face": "1748677.00",
        "issue_date": "2012-03-01",
        "maturity_date": "2027-03-20",
        "payment_delay_days": "50",
        "payment_day": "20",
        "record_date_rule": "RECORD_DATE_RULE_LAST_DAY_OF_PRIOR_MONTH",
    }


async def test_the_dates_of_a_factor_by_the_calendar() -> None:
    lake = recorder()
    calendar = Days(lake.bind(Disclosures(library(Path("/nonexistent")))), "CAL-USD")
    assert await days.payment_date("202609", "II", calendar) == date(2026, 10, 20)
    assert await days.payment_date("202610", "I", calendar) == date(2026, 11, 16)  # 15th a Sunday
    assert await days.payment_date("202610", "III", calendar) is None
    assert await days.latest_month(date(2026, 11, 4), calendar) == "202609"
    assert await days.latest_month(date(2026, 11, 5), calendar) == "202610"
    assert {p.calendar_id for p in lake.on("ReadCalendar")} == {"CAL-USD"}


async def test_payment_dates_unset_where_the_calendar_does_not_answer(tmp_path: Path) -> None:
    lake = recorder()
    lake.answer("ReadCalendar", lambda _: ops.ReadCalendarResult(found=False))
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    rows = factors(lake)
    # The month before last, the calendar silent on this month's fourth day.
    assert rows and all(not r.payment_date for r in rows)
    assert all(r.record_date for r in rows) and "is not held" in work.calendar.error


def test_a_record_is_identified_by_its_identifier_or_terms() -> None:
    held = records()
    pool = identify(held[POOL])
    assert pool is not None and pool.pool == "AA0912"
    assert identify(held[FANNIE_POOL]) is None
    tranche = identify(held[TRANCHE])
    assert tranche is not None and tranche.floating and tranche.series == "2002-005O"
    assert identify(held[BOND]) is None


async def test_checks_again_send_nothing_new(tmp_path: Path) -> None:
    lake = recorder()
    work = feed(lake, tmp_path)
    lake.answer("ObservationsWanted", lambda _: want("w-1", [POOL]).message)
    await lake.hear(work, "ObservationsWanted")
    await work.check()
    before = {k: v[0] for k, v in lake._answers["RecordFactors"].versions.items()}  # type: ignore[attr-defined]
    await work.check()
    await work.check()
    after = {k: v[0] for k, v in lake._answers["RecordFactors"].versions.items()}  # type: ignore[attr-defined]
    assert after == before

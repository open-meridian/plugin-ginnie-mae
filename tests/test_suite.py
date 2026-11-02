"""The data and reference suites (meridian.suites) at contract v29, each case
Ginnie Mae's files present mapped to the plugin's own work on the samples.

**Data.** Presented: `records-a-pools-factor` (the Ginnie II pool AA0912);
`an-asset-that-does-not-resolve` (a pool number meeting two records);
`a-subject-declined` (a bond); `a-standing-want-withdrawn`;
`reads-its-datasets-licences`; `reads-a-calendar` (the deployment's US
dollar calendar, by which a pool's payment date is rolled); and the cases
the SDK answers. Not presented,
with why, every case about a kind of data its files never state, and
`reports-its-feed-delay`: Ginnie Mae's files state the day they were
published, never a time, so no age at the edge is measured.

**Reference.** As `plugin-gse-disclosures`: the five cases of its work and
the SDK's; calendars and settlement dates not presented.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import ANSWERED_BY_SDK, Recorder, run, suite

from ginnie_mae.feed import Disclosures, identify
from ginnie_mae.terms import Terms

from conftest import BOND, INSTANCE, POOL, answering, feed, library, records, want

WHY = {
    "closes": "it records factors, never prices",
    "bars": "it records factors, never prices",
    "a currency's rate against another currency": "it records factors, never prices",
    "a crypto asset's price": "it records factors, never prices",
    "prices on a venue": "it records factors, never prices",
    "a security's price": "it records factors, never prices",
    "trades": "it records factors, never trades",
    "quotes": "it records factors, never quotes",
    "outcomes": "it records factors; no event contract's outcome",
    "disputed outcomes": "it records factors; no event contract's outcome",
    "rates": "it records factors, never rates",
    "streams": "it reads Ginnie Mae's monthly files daily and streams nothing",
    "publication times": (
        "Ginnie Mae's files state the day they were published, never a time: no factor's age "
        "at the edge is measured"
    ),
    "option chains": "it lists no option chains",
    "filings": "it publishes no filings",
    "holdings": "it publishes no holdings",
    "corporate actions": "it publishes no corporate actions",
    "ratings": "it publishes no ratings",
    "derived series": "it publishes no figure of its own",
    "calendars": (
        "its offers state a payment day of the month, never a date rolled by a calendar; the "
        "data role reads the calendar"
    ),
    "settlement dates": "it records factors as published; it never computes a settlement date",
}
DATA_PRESENTED = {
    "records-a-pools-factor",
    "an-asset-that-does-not-resolve",
    "a-subject-declined",
    "a-standing-want-withdrawn",
    "reads-its-datasets-licences",
    "reads-a-calendar",
}
REFERENCE_PRESENTED = {
    "fills-a-template",
    "licensed-vendor-value-stays",
    "offers-never-overwrite-a-person",
    "reads-the-record-it-fills",
    "resolves-a-security-it-reconciles",
}


def not_presented(role: str, presented: set[str]) -> dict[str, str]:
    return {
        case.name: WHY[case.about]
        for case in suite(role).cases
        if case.name not in presented and case.name not in ANSWERED_BY_SDK
    }


DATA_NOT_PRESENTED = not_presented("data", DATA_PRESENTED)
REFERENCE_NOT_PRESENTED = not_presented("reference", REFERENCE_PRESENTED)

Producer = Callable[[Recorder], Awaitable[None]]


def data_producers(tmp: Path) -> dict[str, Producer]:
    made = iter(range(100))

    def wanted(subjects: list[str], ambiguous: bool = False) -> Producer:
        async def produce(recorder: Recorder) -> None:
            answering(recorder, ambiguous=ambiguous)
            work = feed(recorder, tmp / f"d{next(made)}")
            recorder.answer("ObservationsWanted", lambda _: want("w-1", subjects).message)
            await recorder.hear(work, "ObservationsWanted")

        return produce

    async def withdrawn(recorder: Recorder) -> None:
        answering(recorder)
        work = feed(recorder, tmp / "withdrawn")
        recorder.answer(
            "WantWithdrawn",
            lambda _: ops.WantWithdrawnEvent(want_id="w-1", dataset=f"{INSTANCE}:ginnie_mae"),
        )
        await recorder.hear(work, "WantWithdrawn")

    async def licences(recorder: Recorder) -> None:
        dataset = f"{INSTANCE}:ginnie_mae"
        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(licences=[ops.DatasetLicence(dataset=dataset)]),
        )
        work = feed(recorder, tmp / "licences")
        await work.wants.read_licences()
        assert work.wants.licensed == {dataset}

    return {
        "records-a-pools-factor": wanted([POOL]),
        "an-asset-that-does-not-resolve": wanted([POOL], ambiguous=True),
        "a-subject-declined": wanted([BOND]),
        "a-standing-want-withdrawn": withdrawn,
        "reads-its-datasets-licences": licences,
        # The record's payment calendar, else the US dollar's, read for each
        # pool's payment date.
        "reads-a-calendar": wanted([POOL]),
    }


def reference_producers(tmp: Path) -> dict[str, Producer]:
    made = iter(range(100))

    async def offered(recorder: Recorder, record: ops.InstrumentRecord | None = None) -> None:
        answering(recorder)
        if record is not None:
            recorder.answer(
                "ResolveInstrument",
                lambda _: ops.ResolveInstrumentResult(found=True, instrument=record),
            )
        security = identify(records()[POOL])
        assert security is not None
        rows = await Disclosures(library(tmp / f"r{next(made)}")).rows([security], ["202610"])
        terms = recorder.bind(Terms())
        assert await terms.offer(security, rows[0][1])

    async def a_persons_value(recorder: Recorder) -> None:
        record = records()[POOL]
        record.sources.add(person="ada", note="original face as the custodian states it")
        await offered(recorder, record)

    return {
        "fills-a-template": offered,
        "licensed-vendor-value-stays": offered,
        "offers-never-overwrite-a-person": a_persons_value,
        "reads-the-record-it-fills": offered,
        "resolves-a-security-it-reconciles": offered,
    }


def test_the_data_suite_passes(tmp_path: Path) -> None:
    report = run(
        "data", data_producers(tmp_path), not_presented=DATA_NOT_PRESENTED, instance_id=INSTANCE
    )
    assert report.passed, report.failures
    assert set(report.passed_cases) == DATA_PRESENTED | set(ANSWERED_BY_SDK)
    assert "reports-its-feed-delay" in report.not_presented


def test_the_reference_suite_passes(tmp_path: Path) -> None:
    report = run(
        "reference",
        reference_producers(tmp_path),
        not_presented=REFERENCE_NOT_PRESENTED,
        instance_id=INSTANCE,
    )
    assert report.passed, report.failures
    assert set(report.passed_cases) == REFERENCE_PRESENTED | set(ANSWERED_BY_SDK)

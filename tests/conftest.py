"""Shared stand-ins: the deployment's records of a Ginnie II pool and a
Ginnie Mae REMIC tranche, as the platform's templates state them; the lake
answering a batch of factors as it does; the template catalogue; and the
lake's wants as the sidecar delivers them."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder

from ginnie_mae.feed import Disclosures
from ginnie_mae.files import Samples, Source, Store
from ginnie_mae.library import Library
from ginnie_mae.preview import calendar_answer
from ginnie_mae.terms import Terms

INSTANCE = "ginnie-mae-1"
AT = datetime(2026, 11, 10, 17, 0, tzinfo=UTC)
TESTS = Path(__file__).parent / "responses"

POOL = "LCL-01JPOOLGNMAAA0912"
TRANCHE = "INS-01JCLASSGNMA000000000001"
FANNIE_POOL = "INS-01JPOOL00000000000000000001"
NOT_PUBLISHED = "INS-01JPOOLGNMA00000000000009"
BOND = "INS-01JBOND00000000000000000001"


def records() -> dict[str, ops.InstrumentRecord]:
    # A provisional record, as a custodian's statement would have brought it
    # in: the pool's number its only term.
    pool = ops.InstrumentRecord(
        instrument_id=POOL,
        identifiers=[ops.Identifier(scheme="agency_pool", value="AA0912", source="GNMA")],
        asset_class=ops.ASSET_CLASS_DEBT,
        instrument_type=ops.INSTRUMENT_TYPE_MBS_POOL,
        currency="USD",
        provisional=True,
        template_id="TPL-mbs-pool",
        template_version="1",
    )
    unpublished = ops.InstrumentRecord(
        instrument_id=NOT_PUBLISHED,
        instrument_type=ops.INSTRUMENT_TYPE_MBS_POOL,
        identifiers=[ops.Identifier(scheme="agency_pool", value="ZZ9999", source="GNMA")],
    )
    fannie = ops.InstrumentRecord(
        instrument_id=FANNIE_POOL,
        instrument_type=ops.INSTRUMENT_TYPE_MBS_POOL,
        identifiers=[ops.Identifier(scheme="agency_pool", value="MA5123", source="FNMA")],
    )
    fannie.mbs_pool.agency = ops.MORTGAGE_AGENCY_FNMA
    fannie.mbs_pool.pool_number = "MA5123"
    tranche = ops.InstrumentRecord(
        instrument_id=TRANCHE,
        asset_class=ops.ASSET_CLASS_DEBT,
        instrument_type=ops.INSTRUMENT_TYPE_CMO_TRANCHE,
        template_id="TPL-cmo-tranche",
        template_version="1",
    )
    tranche.cmo_tranche.agency = ops.MORTGAGE_AGENCY_GNMA
    tranche.cmo_tranche.deal = "2002-005O"
    tranche.cmo_tranche.class_name = "SP"
    tranche.cmo_tranche.interest_types.append(ops.INTEREST_TYPE_FLOATER)
    bond = ops.InstrumentRecord(instrument_id=BOND, instrument_type=ops.INSTRUMENT_TYPE_BOND)
    return {r.instrument_id: r for r in (pool, unpublished, fannie, tranche, bond)}


TEMPLATES = {
    "TPL-mbs-pool": [
        "identifiers", "description", "currency", "instrument_type", "agency", "program",
        "pool_number", "pass_through_rate", "issue_date", "maturity_date", "original_face",
        "original_term_months", "day_count", "payment_delay_days", "payment_day",
        "record_date_rule", "payment_calendar_id",
    ],
    "TPL-cmo-tranche": [
        "identifiers", "description", "currency", "instrument_type", "agency", "deal",
        "class_name", "issue_date", "principal_types", "interest_types", "original_face",
        "coupon_rate", "floating", "maturity_date", "day_count", "payment_delay_days",
        "payment_day", "record_date_rule", "record_date_days",
    ],
}  # fmt: skip


class Lake:
    """The lake's answer to a batch of factors: new recorded, the same again
    unchanged, a changed one the next version."""

    def __init__(self) -> None:
        self.versions: dict[str, tuple[int, Any]] = {}

    def __call__(self, params: Any) -> ops.RecordFactorsResult:
        recorded = restated = unchanged = 0
        for row in params.factors:
            # As the lake compares them: a row's values, its raw record and
            # business date among them.
            value = (
                as_decimal(row.factor),
                row.payment_date,
                row.meta.raw.key,
                row.meta.business_date,
            )
            held = self.versions.get(row.meta.row_key)
            if held is None:
                self.versions[row.meta.row_key] = (1, value)
                recorded += 1
            elif held[1] == value:
                unchanged += 1
            else:
                self.versions[row.meta.row_key] = (held[0] + 1, value)
                restated += 1
        return ops.RecordFactorsResult(recorded=recorded, restated=restated, unchanged=unchanged)


def answering(recorder: Recorder, ambiguous: bool = False) -> Recorder:
    held = records()

    def read(params: Any) -> ops.ResolveInstrumentResult:
        found = held.get(params.instrument_id)
        if found is None:
            return ops.ResolveInstrumentResult(found=False)
        return ops.ResolveInstrumentResult(found=True, instrument=found)

    def resolve(params: Any) -> ops.ResolveIdentifierResult:
        if ambiguous:
            return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS)
        for record in held.values():
            for named in params.identifiers:
                if any(
                    (i.scheme, i.value, i.source) == (named.scheme, named.value, named.source)
                    for i in record.identifiers
                ):
                    return ops.ResolveIdentifierResult(
                        found=True, instrument_id=record.instrument_id
                    )
        return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND)

    def template(params: Any) -> ops.ReadTemplateResult:
        return ops.ReadTemplateResult(
            template=ops.SecurityTemplate(
                template_id=params.template_id,
                template_version=params.template_version,
                fields=[ops.TemplateField(path=p) for p in TEMPLATES.get(params.template_id, [])],
            )
        )

    recorder.answer("ResolveInstrument", read)
    recorder.answer("ResolveIdentifier", resolve)
    recorder.answer("ReadTemplate", template)
    recorder.answer("RecordFactors", Lake())
    recorder.answer("ReadCalendar", calendar_answer)
    return recorder


def library(tmp: Path, source: Source | None = None) -> Library:
    return Library(source or Samples(), Store(tmp))


def feed(
    recorder: Recorder, tmp: Path, terms: Terms | None = None, source: Source | None = None
) -> Disclosures:
    return recorder.bind(Disclosures(library(tmp, source), now=lambda: AT, terms=terms))


def want(want_id: str, subjects: list[str], *, standing: bool = True) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=f"{INSTANCE}:ginnie_mae",
            data_type="meridian.v1.Factor",
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            standing=standing,
        ),
    )


def factors(recorder: Recorder) -> list[ops.Factor]:
    return [f for params in recorder.on("RecordFactors") for f in params.factors]

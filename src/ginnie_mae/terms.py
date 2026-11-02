"""The plugin's reference role class: the terms Ginnie Mae's files state of
a pool or a REMIC tranche, offered to the record's template (W3.23; ruling
686, the first `reference` plugins).

When the data role records a factor, the row it read states terms too, and
this offers them to the record the deployment holds, at the record's
template and version (`TPL-mbs-pool`, `TPL-cmo-tranche`), each value with its
provenance -- the file at the row's line, or the rule it was derived by --
and only the fields the template has (ReadTemplate). Offers, never
decisions: a value is in force once a person accepts it, a person's value
stands (W3.10), and an offer never leaves the deployment (W1.25).

A pool (a factor file): its agency, pool number, pass-through rate (the
pool interest rate), issue and maturity dates and original face (the
original aggregate amount); and, by its program (Ginnie I or II, the file
it is read from), its payment delay, payment day and record-date rule. A
tranche (a REMIC factor file): its agency, series and class, original
balance, final distribution date as its maturity, and the day of the month
it pays. A tranche's coupon is a period's, so it is never offered.

The record is read first (ResolveInstrument) and a pool's number confirmed
to resolve to it (ResolveIdentifier); each record is offered once for each
file content it was read from.
"""

from __future__ import annotations

import logging
from typing import Any

import meridian
from meridian import edge
from meridian.roles import reference

from . import agency, days
from .layouts import PoolRow, TrancheRow
from .library import Found

log = logging.getLogger("ginnie_mae")

AGENCY = "MORTGAGE_AGENCY_GNMA"
POOL_TEMPLATE = "TPL-mbs-pool"
CLASS_TEMPLATE = "TPL-cmo-tranche"


def pool_terms(row: PoolRow, program: str, reported: Any) -> list[meridian.TemplateFieldValue]:
    values: list[tuple[str, str, Any]] = [
        ("agency", AGENCY, edge.derived("agency", "the file is Ginnie Mae's")),
        ("pool_number", row.pool, reported("pool_number")),
        ("pass_through_rate", str(row.rate), reported("pass_through_rate")),
        ("original_face", str(row.original), reported("original_face")),
    ]
    if row.issue_date is not None:
        values.append(("issue_date", row.issue_date.isoformat(), reported("issue_date")))
    if row.maturity_date is not None:
        values.append(("maturity_date", row.maturity_date.isoformat(), reported("maturity_date")))
    if program in days.PROGRAMS:
        delay, day = days.PROGRAMS[program]
        rule = f"a Ginnie {program} pool, as its factor file says"
        values += [
            ("payment_delay_days", str(delay), edge.derived("payment_delay_days", rule)),
            ("payment_day", str(day), edge.derived("payment_day", rule)),
            (
                "record_date_rule",
                "RECORD_DATE_RULE_LAST_DAY_OF_PRIOR_MONTH",
                edge.derived("record_date_rule", rule),
            ),
        ]
    return [meridian.TemplateFieldValue(path=p, value=v, provenance=w) for p, v, w in values]


def tranche_terms(row: TrancheRow, reported: Any) -> list[meridian.TemplateFieldValue]:
    values: list[tuple[str, str, Any]] = [
        ("agency", AGENCY, edge.derived("agency", "the file is Ginnie Mae's")),
        ("deal", row.series, reported("deal")),
        ("class_name", row.tranche, reported("class_name")),
    ]
    if row.original is not None:
        values.append(("original_face", str(row.original), reported("original_face")))
    if row.final_distribution is not None:
        values.append(
            ("maturity_date", row.final_distribution.isoformat(), reported("maturity_date"))
        )
    if row.payment_date is not None:
        values.append(
            (
                "payment_day",
                str(row.payment_date.day),
                edge.derived("payment_day", "the day of the payment date the file states"),
            )
        )
    return [meridian.TemplateFieldValue(path=p, value=v, provenance=w) for p, v, w in values]


class Terms(reference.Role):
    """The reference role's class (open-meridian 0.35): what a row states,
    offered through `agency.Offers`."""

    def __init__(self) -> None:
        self.offers = agency.Offers()

    async def offer(self, security: Any, found: Found, as_of_ns: int = 0) -> bool:
        """Offer what a row states to the security's record, once for each
        file content; whether an offer was made. A pool's number is
        confirmed to resolve to the record first."""
        row = found.row
        ref = self.plugin.raw_record(f"{found.kept.key}#{row.line}")

        def reported(path: str) -> Any:
            return edge.reported(path, ref)

        if isinstance(row, PoolRow):
            return await self.offers.offer(
                self,
                security.subject,
                found.kept.key,
                template=POOL_TEMPLATE,
                values=lambda: pool_terms(row, found.program, reported),
                pool=(security.pool, "GNMA"),
                as_of_ns=as_of_ns,
            )
        assert isinstance(row, TrancheRow)
        return await self.offers.offer(
            self,
            security.subject,
            found.kept.key,
            template=CLASS_TEMPLATE,
            values=lambda: tranche_terms(row, reported),
            as_of_ns=as_of_ns,
        )

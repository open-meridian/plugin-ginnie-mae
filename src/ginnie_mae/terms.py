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

from . import days
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
    """The reference role's class (open-meridian 0.35)."""

    def __init__(self) -> None:
        self.offered: set[tuple[str, str]] = set()
        self.paths: dict[tuple[str, str], frozenset[str]] = {}
        self.offers = 0
        self.refused = ""

    async def template_paths(self, template_id: str, version: str) -> frozenset[str]:
        held = self.paths.get((template_id, version))
        if held is None:
            read = await self.read_template(template_id=template_id, template_version=version)
            held = frozenset(f.path for f in read.template.fields)
            self.paths[(template_id, version)] = held
        return held

    async def confirm(self, security: Any, as_of_ns: int) -> str:
        """The record a pool's number resolves to, read-only."""
        found = await self.resolve_identifier(
            identifiers=[
                meridian.Identifier(scheme="agency_pool", value=security.pool, source="GNMA")
            ],
            as_of_ns=as_of_ns,
        )
        return str(found.instrument_id) if found.found else ""

    async def offer(self, security: Any, found: Found, as_of_ns: int = 0) -> bool:
        """Offer what a row states to the security's record, once for each
        file content; whether an offer was made."""
        done = (security.subject, found.kept.key)
        if done in self.offered:
            return False
        self.offered.add(done)
        row = found.row
        try:
            read = await self.resolve_instrument(instrument_id=security.subject, as_of_ns=as_of_ns)
            if not read.found:
                return False
            if isinstance(row, PoolRow) and await self.confirm(security, as_of_ns) not in (
                "",
                security.subject,
            ):
                return False
            record = read.instrument
            template = record.template_id or (
                POOL_TEMPLATE if isinstance(row, PoolRow) else CLASS_TEMPLATE
            )
            version = record.template_version or "1"
            ref = self.plugin.raw_record(f"{found.kept.key}#{row.line}")

            def reported(path: str) -> Any:
                return edge.reported(path, ref)

            offered = (
                pool_terms(row, found.program, reported)
                if isinstance(row, PoolRow)
                else tranche_terms(row, reported)
            )
            paths = await self.template_paths(template, version)
            fields = [v for v in offered if v.path in paths]
            if not fields:
                return False
            await self.offer_template_fields(
                instrument_id=security.subject,
                template_id=template,
                template_version=version,
                fields=fields,
            )
        except meridian.MeridianError as refused:
            self.refused = str(refused)
            log.warning("terms of %s not offered: %s", security.subject, refused)
            return False
        self.offers += 1
        log.info(
            "terms of %s offered to %s %s: %s",
            security.subject,
            template,
            version,
            ", ".join(v.path for v in fields),
        )
        return True

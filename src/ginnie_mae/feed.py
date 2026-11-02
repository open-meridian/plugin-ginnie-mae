"""The plugin's data role class: each Ginnie Mae pool's and REMIC tranche's
factor the deployment's records name, from Ginnie Mae's monthly files, into
the lake.

**What is recorded** (contract v29, W10.4; rulings 680 and 749). A reader
asks the lake for a pool's or a tranche's factors (`ListFactors`); one the
lake holds none of is wanted, standing, of `ginnie_mae`. The plugin reads
the record the want names (ResolveInstrument): a pool by its pool number --
its `mbs_pool` terms (agency `MORTGAGE_AGENCY_GNMA`), or its `agency_pool`
identifier, the identifier's source `GNMA` --, confirmed to resolve to that
record alone (ResolveIdentifier, a number meeting two records reported
ambiguous and never recorded); a tranche by its series and class
(`cmo_tranche`, agency `GNMA`). It records each factor Ginnie Mae's files
state for it over the last thirteen months, against the want, and keeps
the want current: each new month's Factor A, its Factor B, and a REMIC
file's tranches. A record of another agency, or of no pool or tranche, is
declined not covered; one no file names, source silent.

**Each factor** (`meridian.helpers.debt.factor`): its subject the record's
ID, its row key `GNMA`, the pool or the series and tranche, and the factor
month (`GNMA:AA0912:202609`, as the contract's fixtures key the agencies'),
the factor exactly as published, its factor month (the file's month), record
date (the factor file's as-of date, or the REMIC file's record date) and
payment date (the pool's program's day rolled by the deployment's calendar --
the record's payment calendar, else the US dollar's -- and unset where it
does not answer; or the REMIC file's own), its
business date the day the file says it was published; a floating or inverse
floating tranche's coupon for the period. Factor B's row is the row's next
version, its source the final file, whether or not its factor changed. Ginnie Mae's factor files
state no WAC, WAM or WALA, so none is recorded, and no publication time, so
none is stated.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import meridian
from meridian.helpers import debt
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data

from . import agency, days
from .layouts import PoolRow, TrancheRow, same_pool
from .library import Found, Library

log = logging.getLogger("ginnie_mae")

KEY = "ginnie_mae"
CODE = "GNMA"
FACTOR = "meridian.v1.Factor"
HISTORY_MONTHS = 13
NEW_YORK = ZoneInfo("America/New_York")
FLOATING = {ops.INTEREST_TYPE_FLOATER, ops.INTEREST_TYPE_INVERSE_FLOATER}


def _ns(moment: datetime) -> int:
    return int(moment.timestamp()) * 1_000_000_000 + moment.microsecond * 1000


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Security:
    """A pool or a tranche a want names, as its record states it."""

    subject: str
    pool: str = ""
    series: str = ""
    tranche: str = ""
    calendar: str = ""
    floating: bool = False

    @property
    def is_pool(self) -> bool:
        return bool(self.pool)


def identify(record: ops.InstrumentRecord) -> Security | None:
    """The pool or tranche a record is, by Ginnie Mae's names for it; None
    for a record of no Ginnie Mae pool or tranche."""
    subject = record.instrument_id
    if record.instrument_type == ops.INSTRUMENT_TYPE_MBS_POOL or record.HasField("mbs_pool"):
        terms = record.mbs_pool
        stated = terms.agency
        pool = terms.pool_number if stated == ops.MORTGAGE_AGENCY_GNMA else ""
        for held in record.identifiers:
            if held.scheme == "agency_pool" and held.source.upper() in (CODE, "GINNIE MAE"):
                pool = pool or held.value
        if not pool or stated not in (ops.MORTGAGE_AGENCY_UNSPECIFIED, ops.MORTGAGE_AGENCY_GNMA):
            return None
        return Security(subject, pool=pool, calendar=terms.payment_calendar_id)
    if record.instrument_type == ops.INSTRUMENT_TYPE_CMO_TRANCHE or record.HasField("cmo_tranche"):
        terms = record.cmo_tranche
        if terms.agency != ops.MORTGAGE_AGENCY_GNMA or not terms.deal or not terms.class_name:
            return None
        return Security(
            subject,
            series=terms.deal,
            tranche=terms.class_name,
            floating=bool(FLOATING & set(terms.interest_types)),
        )
    return None


class Disclosures(data.Role):
    """The data role's class (open-meridian 0.35)."""

    def __init__(
        self,
        library: Library,
        now: Callable[[], datetime] = utc_now,
        terms: Any = None,
        payment_calendar: str = agency.USD_CALENDAR,
    ) -> None:
        self.library = library
        self.now = now
        self.terms = terms
        self.wants = data.Wants(self, (KEY,), clock_ns=lambda: _ns(self.now()))
        #: The deployment's business days: a record's payment calendar, else
        #: the setting's (the US dollar's, the Federal Reserve Banks').
        self.calendar = agency.Days(self, payment_calendar)
        self.held: dict[str, Security] = {}
        self.last_check: datetime | None = None
        self.error = ""

    @property
    def dataset(self) -> str:
        return self.wants.dataset(KEY)

    def today(self) -> date:
        """New York's day: the samples' own with sample data, else now."""
        fixed = getattr(self.library.source, "today", None)
        moment = fixed() if callable(fixed) else self.now()
        return moment.astimezone(NEW_YORK).date()

    async def months(self) -> list[str]:
        latest = await days.latest_month(self.today(), self.calendar)
        return [days.add_months(latest, -n) for n in range(HISTORY_MONTHS - 1, -1, -1)]

    # ── Resolving ───────────────────────────────────────────────────────

    async def confirmed(self, security: Security, as_of_ns: int) -> bool:
        """Whether a pool's number may be recorded against (`agency.confirmed`);
        a tranche has none to confirm."""
        if not security.is_pool:
            return True
        return await agency.confirmed(self, security.pool, CODE, as_of_ns)

    # ── Rows ────────────────────────────────────────────────────────────

    async def factor(self, security: Security, found: Found, month: str) -> meridian.Factor:
        row = found.row
        if isinstance(row, PoolRow):
            paid = await days.payment_date(month, found.program, self.calendar, security.calendar)
            key = f"{CODE}:{row.pool}:{month}"
            coupon = None
        else:
            assert isinstance(row, TrancheRow)
            paid = row.payment_date
            key = f"{CODE}:{row.series}:{row.tranche}:{month}"
            coupon = row.coupon if security.floating else None
        made = debt.factor(
            security.subject,
            row.factor,
            month,
            dataset=self.dataset,
            published=found.published.isoformat() if found.published else "",
            record_date=found.as_of.isoformat() if found.as_of else "",
            payment_date=paid.isoformat() if paid else "",
            coupon_rate=coupon,
            raw=self.plugin.raw_record(f"{found.kept.key}#{row.line}"),
        )
        assert made.meta is not None
        return dataclasses.replace(made, meta=dataclasses.replace(made.meta, row_key=key))

    async def rows(
        self, securities: list[Security], months: list[str], again: bool = False
    ) -> list[tuple[Security, Found, str]]:
        """Each security's rows over the months named, oldest first: a pool's
        Factor B row where its month's final file is published, else its
        Factor A row."""
        pools = [s for s in securities if s.is_pool]
        tranches = [s for s in securities if not s.is_pool]
        out: list[tuple[Security, Found, str]] = []
        if not securities:
            return out
        for month in months:
            read = await self.library.read(month, again=again)
            if pools:
                rows = self.library.pools(read, [s.pool for s in pools])
                # Factor B supersedes Factor A: once a pool's final factor is
                # published, its preliminary one is not recorded again.
                final = {named for named, found in rows if found.file.startswith("factorB")}
                for named, found in rows:
                    if named in final and found.file.startswith("factorA"):
                        continue
                    out += [(s, found, month) for s in pools if same_pool(s.pool, named)]
            if tranches:
                wanted = [(s.series, s.tranche) for s in tranches]
                for (series, tranche), found in self.library.tranches(read, wanted):
                    out += [
                        (s, found, month)
                        for s in tranches
                        if (s.series, s.tranche) == (series, tranche)
                    ]
        return out

    async def record(self, found: Sequence[tuple[Any, ...]], want_id: str = "") -> int:
        """The rows found recorded, Factor A's in one batch before Factor B's,
        so the final factor is the row's next version, after the preliminary;
        their terms offered."""
        sent = 0
        for batch in (
            [r for r in found if r[1].file.startswith("factorA")],
            [r for r in found if not r[1].file.startswith("factorA")],
        ):
            factors = [await self.factor(s, f, m) for s, f, m in batch]
            if factors:
                sent += await self.wants.record("factors", factors, KEY, want_id)
        if self.terms is not None:
            for security, row, _ in found:
                await self.terms.offer(security, row)
        return sent

    # ── Wants ───────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        await self.wants.hear(heard, self.answer)

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        """One want answered from Ginnie Mae's files (`agency.answer`)."""
        if key != KEY or want.data_type != FACTOR:
            return dict.fromkeys(subjects, "not_covered")
        return await agency.answer(
            self,
            want,
            subjects,
            kinds,
            identify=identify,
            confirm=self.confirmed,
            rows=self.rows,
            record=self.record,
            months=await self.months(),
            held=self.held,
            as_of_ns=_ns(self.now()),
        )

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        """A standing want no reader renewed (`agency.withdrawn`)."""
        agency.withdrawn(self, heard.message.want_id, self.held)

    # ── Keeping current ─────────────────────────────────────────────────

    async def check(self) -> int:
        """Read the latest two months' files again -- a new month's Factor A,
        its Factor B, a REMIC file -- and record each held pool's and
        tranche's rows. How many rows were sent."""
        self.last_check = self.now()
        if not self.held:
            return 0
        latest = await days.latest_month(self.today(), self.calendar)
        months = [days.add_months(latest, -1), latest]
        try:
            sent = await self.record(await self.rows(list(self.held.values()), months, again=True))
        except (OSError, meridian.MeridianError) as failed:
            self.error = str(failed)
            raise
        self.error = ""
        log.info("checked %s and %s: %d factors sent", *months, sent)
        return sent

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
payment date (the pool's program's day, or the REMIC file's own), its
business date the day the file says it was published; a floating or inverse
floating tranche's coupon for the period. Factor B's factor is the row's
next version where it differs from Factor A's. Ginnie Mae's factor files
state no WAC, WAM or WALA, so none is recorded, and no publication time, so
none is stated.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import meridian
from meridian.helpers import debt
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data

from . import days
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
        return Security(subject, pool=pool)
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
        self, library: Library, now: Callable[[], datetime] = utc_now, terms: Any = None
    ) -> None:
        self.library = library
        self.now = now
        self.terms = terms
        self.wants = data.Wants(self, (KEY,), clock_ns=lambda: _ns(self.now()))
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

    def months(self) -> list[str]:
        latest = days.latest_month(self.today())
        return [days.add_months(latest, -n) for n in range(HISTORY_MONTHS - 1, -1, -1)]

    # ── Resolving ───────────────────────────────────────────────────────

    async def security(self, subject: str, as_of_ns: int) -> Security | None:
        found = await self.resolve_instrument(instrument_id=subject, as_of_ns=as_of_ns)
        return identify(found.instrument) if found.found else None

    async def confirmed(self, security: Security, as_of_ns: int) -> bool:
        """Whether a pool's number resolves to its record alone: one meeting
        two records is reported ambiguous, and nothing is recorded for it."""
        if not security.is_pool:
            return True
        named = [meridian.Identifier(scheme="agency_pool", value=security.pool, source=CODE)]
        found = await self.resolve_identifier(identifiers=named, as_of_ns=as_of_ns)
        if not found.found and found.miss_reason == ops.MISS_REASON_AMBIGUOUS:
            await self.report_missing_instrument(
                source=CODE, identifiers=named, as_of_ns=as_of_ns, reason=ops.MISS_REASON_AMBIGUOUS
            )
            return False
        return True

    # ── Rows ────────────────────────────────────────────────────────────

    def factor(self, security: Security, found: Found, month: str) -> meridian.Factor:
        row = found.row
        if isinstance(row, PoolRow):
            paid = days.payment_date(month, found.program)
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
        """Each security's rows over the months named, oldest first, Factor A
        before Factor B."""
        pools = [s for s in securities if s.is_pool]
        tranches = [s for s in securities if not s.is_pool]
        out: list[tuple[Security, Found, str]] = []
        if not securities:
            return out
        for month in months:
            read = await self.library.read(month, again=again)
            if pools:
                for named, found in self.library.pools(read, [s.pool for s in pools]):
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

    async def record(self, found: list[tuple[Security, Found, str]], want_id: str = "") -> int:
        """The rows found recorded, Factor A's in one batch before Factor B's,
        so a final factor differing from the preliminary is its next version;
        their terms offered."""
        sent = 0
        for batch in (
            [r for r in found if r[1].file.startswith("factorA")],
            [r for r in found if not r[1].file.startswith("factorA")],
        ):
            factors = [self.factor(s, f, m) for s, f, m in batch]
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
        """One want answered from Ginnie Mae's files."""
        if key != KEY or want.data_type != FACTOR:
            return dict.fromkeys(subjects, "not_covered")
        as_of = _ns(self.now())
        declined: dict[str, str] = {}
        securities: list[Security] = []
        for subject in subjects:
            security = await self.security(subject, as_of)
            if security is None or not await self.confirmed(security, as_of):
                declined[subject] = "not_covered"
            else:
                securities.append(security)
        found = await self.rows(securities, self.months())
        named = {s.subject for s, _, _ in found}
        for security in securities:
            if security.subject not in named:
                declined[security.subject] = "source_silent"
        await self.record(found, want.want_id)
        kept = [s for s in securities if s.subject in named]
        log.info(
            "want %s: %d of %d subjects found, %d factors, declined %s",
            want.want_id,
            len(kept),
            len(subjects),
            len(found),
            declined or "none",
        )
        if want.standing and kept:
            for security in kept:
                self.held[security.subject] = security
            self.wants.stand(want, [s.subject for s in kept], kinds)
        return declined

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        self.wants.withdraw(heard.message.want_id)
        still = {s for w in self.wants.standing.values() for s in w.subjects}
        for subject in [s for s in self.held if s not in still]:
            del self.held[subject]

    # ── Keeping current ─────────────────────────────────────────────────

    async def check(self) -> int:
        """Read the latest two months' files again -- a new month's Factor A,
        its Factor B, a REMIC file -- and record each held pool's and
        tranche's rows. How many rows were sent."""
        self.last_check = self.now()
        if not self.held:
            return 0
        latest = days.latest_month(self.today())
        months = [days.add_months(latest, -1), latest]
        try:
            sent = await self.record(await self.rows(list(self.held.values()), months, again=True))
        except (OSError, meridian.MeridianError) as failed:
            self.error = str(failed)
            raise
        self.error = ""
        log.info("checked %s and %s: %d factors sent", *months, sent)
        return sent

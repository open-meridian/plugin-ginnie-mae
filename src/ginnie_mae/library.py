"""Ginnie Mae's files of a factor month, read and kept, and the rows a want
names found in them.

Reading a month asks the source for its factor files, Factor A before
Factor B, and its REMIC factor files (programs.py), keeps each new content
(files.py), and leaves the rows in the kept bytes: a factor file states
every pool Ginnie Mae guarantees, and the plugin records the factors of the
pools and tranches the deployment's records name only (ruling 749).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from . import programs
from .files import Kept, Source, Store
from .layouts import (
    PoolRow,
    TrancheRow,
    Unread,
    factor_header,
    lines,
    pool_row,
    remic_header,
    same_pool,
    same_series,
    text_of,
    tranche_row,
)

log = logging.getLogger("ginnie_mae")


@dataclass(frozen=True)
class Found:
    """A row found, its file, that file's kept record and what its header
    states: the program, the as-of or record date, the publication."""

    row: PoolRow | TrancheRow
    file: str
    kept: Kept
    program: str = ""
    as_of: date | None = None
    published: date | None = None


@dataclass
class Month:
    month: str
    pools: dict[str, tuple[Kept, str]] = field(default_factory=dict)
    remics: dict[str, Kept] = field(default_factory=dict)


@dataclass
class Library:
    source: Source
    store: Store
    months: dict[str, Month] = field(default_factory=dict)
    unread: dict[str, list[Unread]] = field(default_factory=dict)

    async def read(self, month: str, again: bool = False) -> Month:
        """A factor month's files: read once, or again (`again`) to find
        Factor B or a republished file."""
        held = self.months.get(month)
        if held is not None and not again:
            return held
        read = held or Month(month)
        for name, program in programs.pool_files(month):
            kept = await self._fetch(name)
            if kept is not None:
                read.pools[name] = (kept, program)
        for name in programs.remic_files(month):
            kept = await self._fetch(name)
            if kept is not None:
                read.remics[name] = kept
        self.months[month] = read
        return read

    async def _fetch(self, name: str) -> Kept | None:
        fetched = await self.source.get(name)
        if fetched is None:
            return None
        kept, new = self.store.keep(fetched)
        if new:
            log.info("%s read and kept (%d bytes)", name, len(fetched.body))
        return kept

    def _text(self, name: str, kept: Kept) -> str:
        try:
            return text_of(kept.body())
        except FileNotFoundError:
            # Moved past its window: read again at the next check.
            self.store.latest.pop(name, None)
            return ""

    def pools(self, month: Month, wanted: Iterable[str]) -> list[tuple[str, Found]]:
        """Each named pool's rows, by the pool number as named, Factor A's
        before Factor B's."""
        named = list(wanted)
        found: list[tuple[str, Found]] = []
        for name, (kept, program) in month.pools.items():
            text = self._text(name, kept)
            header = factor_header(text)
            for number, line in lines(text):
                hits = [p for p in named if same_pool(line[:6], p)]
                if not hits:
                    continue
                row = pool_row(number, line)
                if row is None:
                    continue
                if isinstance(row, Unread):
                    self.unread.setdefault(name, []).append(row)
                    continue
                as_of = header.as_of if header else None
                published = header.published if header else None
                for hit in hits:
                    found.append((hit, Found(row, name, kept, program, as_of, published)))
        return found

    def tranches(
        self, month: Month, wanted: Iterable[tuple[str, str]]
    ) -> list[tuple[tuple[str, str], Found]]:
        """Each named tranche's rows, by (series, tranche) as named."""
        named = list(wanted)
        found: list[tuple[tuple[str, str], Found]] = []
        for name, kept in month.remics.items():
            text = self._text(name, kept)
            header = remic_header(text)
            for number, line in lines(text):
                if not line.startswith("2"):
                    continue
                row = tranche_row(number, line)
                if row is None:
                    continue
                if isinstance(row, Unread):
                    self.unread.setdefault(name, []).append(row)
                    continue
                for series, tranche in named:
                    if same_series(row.series, series) and row.tranche.upper() == tranche.upper():
                        found.append(
                            (
                                (series, tranche),
                                Found(
                                    row,
                                    name,
                                    kept,
                                    as_of=header.record_date if header else None,
                                    published=header.run_date if header else None,
                                ),
                            )
                        )
        return found

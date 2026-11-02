"""Ginnie Mae's monthly factor files, by the month they state: the names
its Disclosure Data Download publishes them under.

- Factor A, preliminary, the fourth business day: `factorA1_YYYYMM` (Ginnie
  I pools) and `factorA2_YYYYMM` (Ginnie II);
- Factor B, final, the sixth: `factorB1_YYYYMM` and `factorB2_YYYYMM` -- a
  pool's Factor B factor differing from its Factor A one is the row's next
  version;
- the REMIC factor files, `remic1_YYYYMM` and `remic2_YYYYMM`, mid-month.

The month is the factor month (`factorA1_202609.zip`, published 6 October
2026, states September's factors). Factor A Platinum (`factorAplat`) and
Factor A Additional (`factorAAdd`) are not read: a Platinum's factor is not
in this version, nor what the Additional file adds.
"""

from __future__ import annotations


def pool_files(month: str) -> list[tuple[str, str]]:
    """Each factor file of a month, with its program, preliminary first."""
    return [(f"factor{update}{n}_{month}", "I" * n) for update in ("A", "B") for n in (1, 2)]


def remic_files(month: str) -> list[str]:
    return [f"remic1_{month}", f"remic2_{month}"]

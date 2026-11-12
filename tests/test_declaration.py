"""What the version declares: one dataset of Ginnie Mae's factors, pulled and
pushed daily, with no default licence (rulings 1030 to 1032); its two
roles."""

from __future__ import annotations

import tomllib
from pathlib import Path

from ginnie_mae.declaration import CATALOGUE, DECLARATION


def test_one_dataset() -> None:
    [declared] = CATALOGUE
    assert (declared.key, declared.vendor) == ("ginnie_mae", "Ginnie Mae")
    assert list(declared.data_types) == ["meridian.v1.Factor", "meridian.v1.Factor.coupon_rate"]
    assert declared.cadence == 86_400
    # Contract 30 (ruling 1032): Ginnie Mae's terms in words, never a licence.
    assert "Disclosure Data Download" in declared.terms_and_pricing
    assert declared.gap_recovery == "backfill" and not declared.sessions_calendar_id


def test_its_roles_and_declaration() -> None:
    project = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert project["tool"]["meridian"]["roles"] == ["data", "reference"]
    assert project["project"]["dependencies"] == ["open-meridian==0.36.0"]
    assert DECLARATION.documentation == "docs"

"""The plugin's settings, in the data role's order
(spec/plugin-pages-follow-their-role), each the data role's, which reads the
files (the reference role offers what the data role read): no environment,
since Ginnie Mae publishes one set of files; the location of the files and,
where it asks for one, its token; then the role's sample data.

- `files_url`: where Ginnie Mae's files are read from -- the firm's own copy
  of the factor and REMIC factor files it downloads from Ginnie Mae's
  Disclosure Data Download under the terms it accepted there, served over
  HTTPS under Ginnie Mae's own file names (files.py).
- `files_token`: a bearer token the location asks for, secret, never shown.
- `sample_data`: the files committed with the plugin, in place of the
  location.

The SDK declares the storage's two settings from the declaration's kind:
`files_window_days` and `files_past_window`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import meridian


@meridian.settings
class Declared:
    """The settings as declared: one typed class, the SDK's form."""

    files_url: str = meridian.setting(
        "Files location",
        roles=["data"],
        description=(
            "The HTTPS address of the folder holding Ginnie Mae's monthly factor and REMIC "
            "factor files, under Ginnie Mae's own file names (factorA2_202609.zip, "
            "factorB2_202609.zip, remic2_202609.zip): the firm's copy of what it downloads "
            "from the Disclosure Data Download under its terms."
        ),
    )
    files_token: str = meridian.setting(
        "Files location token",
        secret=True,
        roles=["data"],
        description="A bearer token the files location asks for; empty where it asks none.",
    )
    sample_data: bool = meridian.sample_data(
        roles=["data"],
        description=(
            "Read the factor files committed with the plugin instead of the files location: "
            "a Ginnie II pool and a REMIC tranche, September and October 2026, October's "
            "Factor B published after its Factor A. Development deployments only."
        ),
    )


@dataclass(frozen=True)
class Config:
    files_url: str = ""
    files_token: str = ""
    sample_data: bool = False


def config_from(delivered: Any) -> Config:
    """The configuration a delivery of the settings says."""
    values = getattr(delivered, "values", delivered) or {}
    url = values.get("files_url")
    token = values.get("files_token")
    return Config(
        files_url=url if isinstance(url, str) else "",
        files_token=token if isinstance(token, str) else "",
        sample_data=values.get("sample_data") is True,
    )

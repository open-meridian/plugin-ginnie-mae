"""What this version declares beside its roles (W8.1, W4.1): from contract
v25 the whole of what it says about itself.

**The catalogue: one dataset, `ginnie_mae`** (ruling 686: Ginnie Mae's own
format, its own plugin), the factors of its pools and REMIC tranches
(`meridian.v1.Factor`, contract v29, with `coupon_rate` for a floating
tranche): `vendor` Ginnie Mae, no aggregator; `modes` `pull` (a pool's or a
tranche's factors when the lake wants them) and `push` (each month's Factor
A, Factor B and REMIC factors for those kept current); `cadence` a day, the
files being checked daily; `history` 396 days, thirteen months; its day New
York's; no venue, no calendar. Ginnie Mae's factor files state no WAC, WAM
or WALA, so the dataset does not declare them.

No default licence (rulings 1030 to 1032): Ginnie Mae's terms are accepted
on its download page, and the deployment's; docs/terms.md summarises them.

**Storage:** the files as read, archivable, ten years by default.
"""

from __future__ import annotations

import meridian
from meridian.declaration import Declaration, RecordKind, Storage

from .feed import KEY
from .files import FILES
from .page import TITLE, pages
from .settings import Declared

PORT = 8000
CADENCE = 86_400
HISTORY_DAYS = 396
WINDOW_DAYS = 3650
MOST_WINDOW_DAYS = 36500

GINNIE_MAE = meridian.DatasetDeclaration(
    key=KEY,
    vendor="Ginnie Mae",
    data_types=["meridian.v1.Factor", "meridian.v1.Factor.coupon_rate"],
    modes=["pull", "push"],
    cadence=CADENCE,
    history=HISTORY_DAYS,
    day_time_zone="America/New_York",
)
CATALOGUE = [GINNIE_MAE]
FILES_KIND = RecordKind(FILES, "Disclosure files", window_days=WINDOW_DAYS)

DECLARATION = Declaration(
    settings=Declared,
    storage=Storage(retention_days=MOST_WINDOW_DAYS, kinds=[FILES_KIND]),
    catalogue=CATALOGUE,
    interface=meridian.Interface(port=PORT, title=TITLE, pages=pages),
    documentation="docs",
)

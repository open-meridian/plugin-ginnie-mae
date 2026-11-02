# plugin-ginnie-mae

Ginnie Mae's monthly disclosures for [Open Meridian](https://open-meridian.dev),
as a `data` and `reference` plugin: the factor of each Ginnie Mae pool and
REMIC tranche a deployment holds, read from Ginnie Mae's factor files into
its lake as the `ginnie_mae` dataset, and the terms the same files state
offered to each security's record.

Each row is a `Factor` (contract v29) under the pool's or tranche's record,
keyed by `GNMA`, the pool (or series and tranche) and the factor month --
`GNMA:AA0912:202609` -- the factor exactly as published, its factor month
(the month Ginnie Mae names its files by), record date (the file's as-of
date) and payment date (a Ginnie I pool's 15th, a Ginnie II pool's 20th, on
the next business day; a tranche's as the REMIC file states it); a floating
tranche's period coupon. Factor A is preliminary and Factor B final: the
final factor is the row's next version, its source the final file. Factors
are recorded only for the records the deployment names (ruling 749), when a
reader asks, and kept current daily.

## Using it

Ginnie Mae publishes its files to signed-in users of its Disclosure Data
Download; it offers no API, and the plugin holds no one's sign-in. It reads
the files, unchanged and under Ginnie Mae's own names, from a location the
deployment admin names (**Files location**, HTTPS, with an optional token).
See [docs/setup.md](docs/setup.md).

    meridian plugin upload
    meridian plugin launch ginnie-mae 0.1.0 --instance ginnie-mae

Then license `ginnie-mae:ginnie_mae` on the dashboard's **Data sources** page
and entitle the plugins that read factors. Its pages are under **Manage**:
Connection and Datasets, each also a read tool (`read_connection`,
`read_datasets`).

## Developing it

    make ci-remote                    # lint and tests, in containers
    make check                        # meridian plugin check --verified --run-tests
    make e2e                          # the plugin on the harness of the runtime it pins
    make preview SHOTS=/tmp/shots     # the pages in a browser, at 375, 582 and 1280 px

The tests read Ginnie Mae's own published sample files (`tests/responses/`)
and files in its layouts committed under `src/ginnie_mae/samples/`; nothing
in CI reaches Ginnie Mae. Version 0.1.0 is built on `open-meridian==0.35.3`,
contract v29.

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). This project is not
affiliated with or endorsed by Ginnie Mae.

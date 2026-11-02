# Changelog

## 0.1.0

The first version (ruling 686, the plan's Q13 and G'), on open-meridian
0.35.3, contract v29.

- **`data`**: the `ginnie_mae` dataset of `Factor` rows (with
  `coupon_rate`), pulled when the lake wants a held pool's or tranche's
  factors and pushed as each month's Factor A, Factor B and REMIC factors are
  published. Read from Ginnie Mae's Factor A and B files for Ginnie I and II
  pools and its REMIC 1 and 2 factor files, in its published layouts; a pool
  found by its number, a tranche by its series and class; a pool number
  meeting two records reported ambiguous; Factor B's differing factor the
  row's next version.
- **`reference`**: the terms the same rows state offered to the record at
  its template (`TPL-mbs-pool`, `TPL-cmo-tranche`), each with its
  provenance.
- Factor months, record dates and payment dates as the contract's fixtures
  key them.
- The files read from a location the deployment admin names, with sample
  data for development; the data role's Connection and Datasets pages.

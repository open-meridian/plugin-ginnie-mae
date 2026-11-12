# Changelog

## 0.2.0

On open-meridian 0.36.0, contract 30, on core aae501d's harness (chart
0.1.538); `meridian` 0.1.60 in the check. What the plugin records is
unchanged.

- **Ginnie Mae's terms in words** (ruling 1032): the dataset's
  `terms_and_pricing` says the factor files are Ginnie Mae's own
  disclosures, free from its Disclosure Data Download to users who accept
  its terms of use, its loan-level terms barring re-identification (no
  loan-level file is read). Shown on Data sources and in the Datasets
  page's row details. The plugin still declares no licence.
- **A gap recovered by backfill** (`gap_recovery`): the files hold thirteen
  months, read again on a want. No `sessions_calendar_id`: factors are
  published monthly, in no session.
- **Row keys checked against the lake's rule 5** (ruled 2026-11-12): a
  factor is keyed by the pool, or the REMIC series and class, and its month
  (`GNMA:<pool>:<YYYYMM>`), its valid time the month's; Factor A then Factor
  B for a month restate the same key over the same month and the same
  record. The key names the pool, not its record, so a pool resolved again
  to another record would restate under another first subject: listed for
  step 3d, unchanged.
- `meridian plugin migrate --to 0.36.0` moved the pins (the base by
  digest, `meridian` 0.1.60); the tests' pin and absent-licence checks read
  0.36.0 and the words.
- Core's runtime and harness images at `aae501d`, by digest.

## 0.1.0

The first version (ruling 686, the plan's Q13 and G'), on open-meridian
0.35.3, contract v29.

- **`data`**: the `ginnie_mae` dataset of `Factor` rows (with
  `coupon_rate`), pulled when the lake wants a held pool's or tranche's
  factors and pushed as each month's Factor A, Factor B and REMIC factors are
  published. Read from Ginnie Mae's Factor A and B files for Ginnie I and II
  pools and its REMIC 1 and 2 factor files, in its published layouts; a pool
  found by its number, a tranche by its series and class; a pool number
  meeting two records reported ambiguous; Factor B's row the
  row's next version, its source the final file.
- **`reference`**: the terms the same rows state offered to the record at
  its template (`TPL-mbs-pool`, `TPL-cmo-tranche`), each with its
  provenance.
- Factor months, record dates and payment dates as the contract's fixtures
  key them; a pool's payment date rolled to the next business day by the
  deployment's calendar -- the record's payment calendar, else the
  `payment_calendar` setting, by default the platform's US dollar calendar
  (the Federal Reserve Banks', `CAL-01M4VF0F3HJ73RFTB0XWVK1B73`) through the
  SDK's `MarketDays` -- and left unset where the calendar does not answer or
  does not cover the day.
- `agency.py`: the logic this plugin and `plugin-gse-disclosures` hold the
  same (business days on the calendar, a pool's number confirmed, a factor
  want answered, terms offered), one module, proposed for an SDK helper.
- The files read from a location the deployment admin names, with sample
  data for development; the data role's Connection and Datasets pages.

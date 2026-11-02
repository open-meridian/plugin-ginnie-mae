# Overview

Ginnie Mae publishes each month the factor of every pool it guarantees, the
fraction of its original balance still outstanding, first as a preliminary
file (Factor A) and then a final one (Factor B), and the factor of each
REMIC tranche. This plugin reads those files and puts the factors of the
pools and tranches your deployment holds into its lake, as the `ginnie_mae`
dataset, and offers the terms the same files state to each security's
record.

## What it brings in

- **Factors**: for each Ginnie I and Ginnie II pool and REMIC tranche the
  deployment's records name, its factor for each month exactly as published,
  with the month it reflects, its record date and payment date; a floating
  tranche's coupon for the period. A year of history when a pool is first
  asked for, then each month's preliminary factor and its final one -- a
  final factor that differs is the row's next version.
- **Terms**, offered to the record: a pool's number, interest rate, issue
  and maturity dates, original balance and, by its program, its payment
  delay and day; a tranche's series, class, original balance, final
  distribution date and payment day. An offer is never in force until a
  person accepts it, and never replaces a value a person set.

## What it does not do

- It never records a pool or tranche nobody holds, and never creates an
  instrument record.
- It does not read Platinum pools' factors or the Factor A Additional file in
  this version, nor a pool's WAC, WAM or WALA, which the factor files do not
  state.
- It records no prices, trades or quotes, and computes no paydown.
- It does not reach Ginnie Mae's site itself: it reads the files from the
  location you name (see Setup).
- Fannie Mae's and Freddie Mac's pools are another plugin's,
  `gse-disclosures`.

# Setup

## Before launching

- Sign up for Ginnie Mae's Disclosure Data Download and accept its terms of
  use for your firm.
- Arrange a location that serves the files you download, unchanged and
  under Ginnie Mae's own file names, over HTTPS: for example
  `factorA2_202609.zip`, `factorB2_202609.zip`, `factorA1_202609.zip` and
  `remic2_202609.zip`. A bearer token is supported if the location asks for
  one. The plugin reads Factor A and Factor B for Ginnie I and Ginnie II
  pools, and the REMIC 1 and REMIC 2 factor files.

## After launching

1. Open the plugin's **Settings**: enter **Files location** (the folder's
   HTTPS address) and, if it asks for one, **Files location token**.
   **Payment calendar** is the platform's US dollar calendar (the Federal
   Reserve Banks' business days) unless you name your own copy; a pool's
   record naming its own payment calendar goes first.
2. On the dashboard's **Data sources** page, license `ginnie_mae` and
   entitle the plugins that read factors.
3. Check its **Summary**: Connection reads Answering once the location
   answers.

Factors are read when a pool or tranche is first asked for, and checked
daily after that: Factor A is published on the fourth business day of the
month, Factor B on the sixth, the REMIC factors mid-month.

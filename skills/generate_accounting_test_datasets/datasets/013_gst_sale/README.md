# 013_gst_sale - GST Sale

## Business Scenario

Sale with output GST

## Accounting Purpose

This fixture validates deterministic double-entry posting for `GST Sale`.

## Expected Accounting Outcome

- Total debits: 1180.0
- Total credits: 1180.0
- Net profit: 1000.0
- Voucher count: 1

## Reports Expected To Change

- Trial Balance
- Ledger Balances
- Profit & Loss when income or expense ledgers are present
- Balance Sheet when asset, liability, or equity ledgers are present

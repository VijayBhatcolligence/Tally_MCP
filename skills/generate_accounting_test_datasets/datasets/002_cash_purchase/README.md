# 002_cash_purchase - Cash Purchase

## Business Scenario

Purchase goods/expense for cash

## Accounting Purpose

This fixture validates deterministic double-entry posting for `Cash Purchase`.

## Expected Accounting Outcome

- Total debits: 1200.0
- Total credits: 1200.0
- Net profit: -1200.0
- Voucher count: 1

## Reports Expected To Change

- Trial Balance
- Ledger Balances
- Profit & Loss when income or expense ledgers are present
- Balance Sheet when asset, liability, or equity ledgers are present

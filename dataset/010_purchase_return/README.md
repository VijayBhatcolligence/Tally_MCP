# 010_purchase_return - Purchase Return

## Business Scenario

Return part of credit purchase

## Accounting Purpose

This fixture validates deterministic double-entry posting for `Purchase Return`.

## Expected Accounting Outcome

- Total debits: 2500.0
- Total credits: 2500.0
- Net profit: -1500.0
- Voucher count: 2

## Reports Expected To Change

- Trial Balance
- Ledger Balances
- Profit & Loss when income or expense ledgers are present
- Balance Sheet when asset, liability, or equity ledgers are present

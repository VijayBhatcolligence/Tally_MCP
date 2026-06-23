# 008_contra_voucher - Contra Voucher

## Business Scenario

Move cash to bank

## Accounting Purpose

This fixture validates deterministic double-entry posting for `Contra Voucher`.

## Expected Accounting Outcome

- Total debits: 8000.0
- Total credits: 8000.0
- Net profit: 0.0
- Voucher count: 2

## Reports Expected To Change

- Trial Balance
- Ledger Balances
- Profit & Loss when income or expense ledgers are present
- Balance Sheet when asset, liability, or equity ledgers are present

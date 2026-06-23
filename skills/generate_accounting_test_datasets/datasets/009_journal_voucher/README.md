# 009_journal_voucher - Journal Voucher

## Business Scenario

Accrue expense

## Accounting Purpose

This fixture validates deterministic double-entry posting for `Journal Voucher`.

## Expected Accounting Outcome

- Total debits: 900.0
- Total credits: 900.0
- Net profit: -900.0
- Voucher count: 1

## Reports Expected To Change

- Trial Balance
- Ledger Balances
- Profit & Loss when income or expense ledgers are present
- Balance Sheet when asset, liability, or equity ledgers are present

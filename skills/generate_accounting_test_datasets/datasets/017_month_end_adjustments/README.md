# 017_month_end_adjustments - Month End Adjustments

## Business Scenario

Accrual and depreciation adjustments

## Accounting Purpose

This fixture validates deterministic double-entry posting for `Month End Adjustments`.

## Expected Accounting Outcome

- Total debits: 2800.0
- Total credits: 2800.0
- Net profit: -2800.0
- Voucher count: 3

## Reports Expected To Change

- Trial Balance
- Ledger Balances
- Profit & Loss when income or expense ledgers are present
- Balance Sheet when asset, liability, or equity ledgers are present

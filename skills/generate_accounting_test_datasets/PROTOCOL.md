# Protocol

## Factory Dataset Generation

For new or extended company datasets, use `scripts/accounting_dataset_factory.py`.

### New Dataset Protocol

1. If no details are given, use defaults: medium trader dataset with GST.
2. Generate output structure:
   - `manifest.json`
   - `masters/company.json`
   - `masters/groups.json`
   - `masters/ledgers.json`
   - `masters/customers.json`
   - `masters/suppliers.json`
   - `masters/stock_items.json`
   - `transactions/vouchers.json`
   - `reports/trial_balance.json`
   - `reports/profit_loss.json`
   - `reports/balance_sheet.json`
   - `reports/ledger_balances.json`
   - `generation_log.md`
3. Recompute reports from vouchers.
4. Inspect generated output.

### Extend Existing Dataset Protocol

1. Inspect `manifest.json`, `masters/`, `transactions/vouchers.json`, and `reports/`.
2. Determine company name, masters, voucher count, fiscal years, GST status, and inventory status.
3. Ask whether to continue the existing company or create a new company when intent is ambiguous.
4. If continuing, append vouchers only.
5. Never reuse voucher numbers.
6. Recompute every report.
7. Append to `generation_log.md`.

## Legacy Scenario Pack Generation

Use `scripts/generate_datasets.py` for the 20 fixed regression folders.

## Validation

Validation must check:

- Required files exist.
- Ledger names referenced by vouchers exist.
- Stock item names referenced by inventory lines exist.
- Every voucher has at least two entries.
- Every voucher balances: debit total equals credit total.
- Dataset total debit equals total credit.
- Expected Trial Balance matches recomputed balances.
- Expected Profit & Loss matches recomputed income/expense balances.
- Expected Balance Sheet matches recomputed asset/liability/equity balances.
- For factory datasets, `Assets + Expenses = Liabilities + Equity + Income` in Trial Balance terms.
- Voucher IDs are unique.
- Extension voucher IDs are greater than all prior voucher IDs.

## Tally Import Protocol

Convert `tally_import.json` into MCP calls in this order:

1. Create groups.
2. Create ledgers.
3. Create stock groups/items if present.
4. Create vouchers.
5. Read reports.
6. Compare Tally reports against `expected_results.json`.

Voucher amount convention for Tally MCP:

- Debit = negative amount.
- Credit = positive amount.
- Entries must sum to zero after conversion.

## Foundry Import Protocol

Use `foundry_import.json` as the neutral accounting source:

- Debit/credit are explicit.
- Amounts are positive decimals.
- Voucher identity is stable.
- Ledger/group names match `dataset.json`.

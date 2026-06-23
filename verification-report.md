# Tally MCP Write/Read Verification Report

Date: 2026-06-22

Target company: `Good_one`

## MCP Tool Registration

Verified by MCP handshake against `dist/index.mjs`.

Total tools: `33`

Write tools registered:

- `create-company`
- `create-group`
- `create-ledger`
- `create-stock-group`
- `create-stock-item`
- `create-unit`
- `create-godown`
- `create-cost-center`
- `create-currency`
- `create-sales-voucher`
- `create-purchase-voucher`
- `create-payment-voucher`
- `create-receipt-voucher`
- `create-contra-voucher`
- `create-journal-voucher`
- `create-credit-note`
- `create-debit-note`
- `alter-ledger`
- `alter-stock-item`
- `alter-voucher`
- `delete-voucher`

## Passing End-To-End Accounting Verification

Command:

```powershell
node scripts\verify-write-read.mjs
```

Result: `ok: true`

Voucher date used: `2026-06-01`

Note: Tally Educational Mode rejected `2026-06-22` voucher dates. `2026-06-01` succeeded.

Created ledgers:

- `Codex E2E Customer 762103`
- `Codex E2E Supplier 762103`
- `Codex E2E Sales 762103`
- `Codex E2E Purchase 762103`

Created vouchers:

- Sales voucher: customer debit `1000`, sales credit `1000`
- Purchase voucher: purchase debit `400`, supplier credit `400`

Tally import responses:

- 4 ledgers created with `CREATED=1`, `ERRORS=0`, `EXCEPTIONS=0`
- Sales voucher created with `CREATED=1`, `ERRORS=0`, `EXCEPTIONS=0`
- Purchase voucher created with `CREATED=1`, `ERRORS=0`, `EXCEPTIONS=0`

Report readback:

Trial Balance:

```text
Codex E2E Customer 762103   Sundry Debtors      net_debit=-1000  net_credit=0
Codex E2E Purchase 762103   Purchase Accounts   net_debit=-400   net_credit=0
Codex E2E Sales 762103      Sales Accounts      net_debit=0      net_credit=-1000
Codex E2E Supplier 762103   Sundry Creditors    net_debit=0      net_credit=-400
```

Profit and Loss:

```text
Codex E2E Purchase 762103   Purchase Accounts   amount=-400
Codex E2E Sales 762103      Sales Accounts      amount=1000
```

Balance Sheet:

```text
Codex E2E Customer 762103   Sundry Debtors      closing_balance=-1000
Codex E2E Supplier 762103   Sundry Creditors    closing_balance=400
```

Assertions:

- `salesInProfitLoss`: true
- `purchaseInProfitLoss`: true
- `customerInBalanceSheet`: true
- `supplierInBalanceSheet`: true
- `trialBalanceRowsPresent`: true

## Current Tally Runtime Blocker

After testing inventory/unit/location/cost-centre imports, Tally's HTTP endpoint began timing out even for read-only `list-master` requests.

Observed after timeout hardening:

```json
{
  "isError": true,
  "text": "Tally HTTP request timed out"
}
```

Likely cause: Tally UI has a pending prompt/dialog or the current company has inventory/cost-centre features disabled and Tally is not completing those import requests.

Code has been updated so read and write calls fail cleanly with timeout errors instead of hanging agents.


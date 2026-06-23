# Schema

## Factory Dataset Structure

```text
dataset/
├── manifest.json
├── masters/
│   ├── company.json
│   ├── groups.json
│   ├── ledgers.json
│   ├── customers.json
│   ├── suppliers.json
│   └── stock_items.json
├── transactions/
│   └── vouchers.json
├── reports/
│   ├── trial_balance.json
│   ├── profit_loss.json
│   ├── balance_sheet.json
│   └── ledger_balances.json
└── generation_log.md
```

## manifest.json

```json
{
  "seed": 20260623,
  "companyName": "Aarav Trading Company",
  "businessType": "trader",
  "generationDate": "2026-06-23",
  "voucherCount": 250,
  "fiscalYears": ["2026-2027"],
  "features": {
    "gst": true,
    "inventory": false,
    "costCenters": false,
    "payroll": false
  },
  "lastVoucherNumber": 250,
  "extensions": []
}
```

## transactions/vouchers.json

```json
[
  {
    "id": "V000001",
    "voucherNumber": "V000001",
    "type": "Sales",
    "date": "2026-04-01",
    "narration": "Credit sale to customer",
    "entries": [
      {"ledger": "Customer A", "dc": "debit", "amount": 1180.0},
      {"ledger": "Sales", "dc": "credit", "amount": 1000.0},
      {"ledger": "GST Output", "dc": "credit", "amount": 180.0}
    ]
  }
]
```

## Legacy Scenario dataset.json

```json
{
  "metadata": {
    "id": "005_credit_sale",
    "name": "Credit Sale",
    "level": 1,
    "purpose": "Validate credit sale accounting"
  },
  "company": {
    "name": "Foundry Tally Test Co",
    "fiscalYearFrom": "2026-04-01",
    "booksBeginningFrom": "2026-04-01",
    "currency": "INR"
  },
  "groups": [
    {
      "name": "Sundry Debtors",
      "parent": "Current Assets",
      "classification": "asset"
    }
  ],
  "ledgers": [
    {
      "name": "Customer A",
      "group": "Sundry Debtors",
      "classification": "asset",
      "openingBalance": 0
    }
  ],
  "stockItems": [],
  "vouchers": [
    {
      "id": "V001",
      "type": "Sales",
      "date": "2026-04-01",
      "narration": "Credit sale",
      "entries": [
        {
          "ledger": "Customer A",
          "dc": "debit",
          "amount": 1000
        },
        {
          "ledger": "Sales",
          "dc": "credit",
          "amount": 1000
        }
      ]
    }
  ]
}
```

## expected_results.json

Contains:

- `trialBalance`
- `profitLoss`
- `balanceSheet`
- `ledgerBalances`
- `closingBalances`
- `controlTotals`

Neutral balance convention:

- Debit-positive balance: debit minus credit.
- Credit balance is negative.

Tally signed convention:

- `tallySignedClosingBalance = -neutralBalance`

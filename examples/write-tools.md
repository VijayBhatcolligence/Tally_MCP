# Tally MCP Write Tool Examples

Amounts in voucher entries use this MCP convention: debit entries are negative, credit entries are positive, and the voucher total must be zero.

Educational Mode Tally installations may reject most voucher dates. Use `01`, `02`, or `31` dates when testing, for example `2026-06-01`.

## Create Ledger

Request:

```json
{
  "targetCompany": "Good_one",
  "name": "Codex Customer",
  "parent": "Sundry Debtors",
  "openingBalance": 0
}
```

Response:

```json
{
  "created": 1,
  "altered": 0,
  "deleted": 0,
  "errors": 0,
  "exceptions": 0,
  "ok": true
}
```

## Create Sales Voucher

Request:

```json
{
  "targetCompany": "Good_one",
  "date": "2026-06-01",
  "voucherNumber": "CDEX-S-001",
  "partyLedgerName": "Codex Customer",
  "narration": "Codex MCP sales example",
  "entries": [
    {
      "ledgerName": "Codex Customer",
      "amount": -1000
    },
    {
      "ledgerName": "Codex Sales",
      "amount": 1000
    }
  ]
}
```

Response:

```json
{
  "created": 1,
  "altered": 0,
  "deleted": 0,
  "errors": 0,
  "exceptions": 0,
  "ok": true
}
```

## Create Purchase Voucher

Request:

```json
{
  "targetCompany": "Good_one",
  "date": "2026-06-01",
  "voucherNumber": "CDEX-P-001",
  "partyLedgerName": "Codex Supplier",
  "narration": "Codex MCP purchase example",
  "entries": [
    {
      "ledgerName": "Codex Purchase",
      "amount": -400
    },
    {
      "ledgerName": "Codex Supplier",
      "amount": 400
    }
  ]
}
```

Response:

```json
{
  "created": 1,
  "altered": 0,
  "deleted": 0,
  "errors": 0,
  "exceptions": 0,
  "ok": true
}
```


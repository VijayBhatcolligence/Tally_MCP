# Tally MCP Architecture

This MCP server lets an AI agent talk to Tally Prime through Tally's XML HTTP API on `localhost:9000`.

## High-Level Flow

```text
AI Agent / Codex
      |
      | MCP tool call
      v
dist/index.mjs
      |
      v
dist/mcp.mjs
      |
      +-----------------------+
      |                       |
      v                       v
Read/report tools         Write/import tools
dist/tally.mjs            dist/tally-import.mjs
      |                       |
      | Tally XML POST        | Tally XML Import Data POST
      v                       v
Tally Prime HTTP API on localhost:9000
      |
      v
Open Tally company data
```

## Read Path

```text
Agent asks: trial-balance / profit-loss / list-master
        |
        v
mcp.mjs calls handlePull()
        |
        v
tally.mjs loads XML template from pull/*.xml
        |
        v
POST XML to Tally localhost:9000
        |
        v
Parse XML response to JSON/TSV
        |
        v
Return result to agent
```

For large reports, rows are cached in DuckDB memory and the agent can query them using `query-database`.

## Write Path

```text
Agent asks: create-ledger / create-sales-voucher
        |
        v
mcp.mjs validates tool schema
        |
        v
tally-import.mjs builds Tally Import Data XML
        |
        v
POST XML to Tally localhost:9000
        |
        v
Parse Tally response:
CREATED / ALTERED / DELETED / ERRORS / EXCEPTIONS
        |
        v
Return structured JSON
```

Example response:

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

## Voucher Amount Rule

Voucher entries use this MCP convention:

```text
Debit  = negative amount
Credit = positive amount
Total must equal zero
```

Example sales voucher:

```text
Customer ledger  -1000  debit
Sales ledger      1000  credit
Total                0
```

## Important Tally Notes

- Tally must be open and listening on `localhost:9000`.
- The target company must be open or selected in Tally.
- Educational Mode may reject normal dates. `2026-06-01` worked during testing.
- If Tally shows a popup/prompt, XML calls can time out until the prompt is cleared.


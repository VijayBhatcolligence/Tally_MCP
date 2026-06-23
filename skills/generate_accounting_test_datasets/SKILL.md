---
name: generate-accounting-test-datasets
description: Accounting Dataset Factory for deterministic Foundry-Tally equivalence datasets. Use when Codex needs to create a new realistic accounting company dataset, extend an existing dataset without breaking balances, inspect dataset metadata, generate deterministic vouchers for trader/service/manufacturer/retail/distributor businesses, or produce expected Trial Balance, Balance Sheet, Profit & Loss, ledger balances, GST, inventory, and import payloads.
---

# Accounting Dataset Factory

Use this skill to generate or extend deterministic accounting datasets with known expected outcomes. Do not invent random accounting data. Always regenerate expected results from voucher math.

## Core Workflow

1. Read `SCHEMA.md` before changing dataset structure.
2. Read `PROTOCOL.md` before generating or validating datasets.
3. For company-style datasets, use `scripts/accounting_dataset_factory.py`.
4. For the legacy 20 scenario pack, use `scripts/generate_datasets.py`.
5. Validate generated data with `scripts/validate_datasets.py` when using the legacy pack, or `scripts/accounting_dataset_factory.py inspect`.
6. Use generated `reports/` for Foundry-Tally comparison.

## Operating Modes

### New Dataset

If the user asks for a new dataset and gives no details, use defaults:

- size: `medium`
- business type: `trader`
- scenarios: `GST`
- Indian accounting data

Ask only for missing essentials when needed: size, business type, and special scenarios.

Create a new dataset:

```bash
python scripts/accounting_dataset_factory.py new --output dataset --size medium --business-type trader --scenarios GST
```

### Extend Existing Dataset

If the user says "add more data", inspect the existing dataset first and prefer extending it. Do not create a new company unless explicitly requested.

```bash
python scripts/accounting_dataset_factory.py inspect --path dataset
python scripts/accounting_dataset_factory.py extend --path dataset --voucher-count 100
```

The extension mode must:

- preserve company metadata
- reuse existing masters
- never duplicate voucher numbers
- append new vouchers
- recompute reports
- update `manifest.json`

If intent is ambiguous after inspection, ask exactly:

```text
Do you want to:
1. Continue existing company
2. Create a new company
```

## User Intent Rules

- If the user says `Generate dataset`, create a new medium trader GST dataset with realistic Indian accounting data.
- If the user says `add more data`, extend the current dataset.
- If the user says `create new dataset`, create a completely new company dataset.
- Always prefer extending existing datasets over replacing them.
- Never overwrite an existing dataset unless the user explicitly asks.

## Legacy Scenario Pack

Generate the 20 deterministic regression folders:

```bash
python scripts/generate_datasets.py --all --output dataset
```

Generate stress dataset:

```bash
python scripts/generate_datasets.py --stress-scale 1000 --output datasets/stress_1000
```

Validate all datasets:

```bash
python scripts/validate_datasets.py datasets
```

## Rules

- Keep all amounts deterministic.
- Keep voucher IDs stable inside each dataset.
- Store generation metadata in `manifest.json`.
- Balance every voucher: total debits must equal total credits.
- Compute expected Trial Balance, Balance Sheet, Profit & Loss, Ledger Balances, and Closing Balances from vouchers.
- Always preserve accounting equation integrity.
- In extension mode, inspect before writing.
- Prefer small, auditable scenarios over large opaque fixtures.
- Use `020_stress_small` for committed stress data; generate 500/1000/5000 voucher datasets on demand.

## Reference Files

- `PROTOCOL.md`: generation and validation protocol.
- `ROLE.md`: expected agent behavior and accounting assumptions.
- `SCHEMA.md`: normalized JSON schema and report conventions.

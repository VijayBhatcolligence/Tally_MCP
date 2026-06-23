#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from generate_datasets import compute_expected  # noqa: E402


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_dataset(folder):
    errors = []
    required = ["dataset.json", "expected_results.json", "README.md", "tally_import.json", "foundry_import.json"]
    for name in required:
        if not (folder / name).exists():
            errors.append(f"missing {name}")
    if errors:
        return errors

    dataset = load_json(folder / "dataset.json")
    expected = load_json(folder / "expected_results.json")
    ledgers = {l["name"] for l in dataset.get("ledgers", [])}
    stock_items = {s["name"] for s in dataset.get("stockItems", [])}

    for voucher in dataset.get("vouchers", []):
        if len(voucher.get("entries", [])) < 2:
            errors.append(f"{voucher.get('id')} has fewer than two entries")
        debit = 0
        credit = 0
        for entry in voucher.get("entries", []):
            if entry["ledger"] not in ledgers:
                errors.append(f"{voucher.get('id')} references unknown ledger {entry['ledger']}")
            if entry["dc"] == "debit":
                debit += entry["amount"]
            elif entry["dc"] == "credit":
                credit += entry["amount"]
            else:
                errors.append(f"{voucher.get('id')} has invalid dc {entry['dc']}")
        if round(debit - credit, 2) != 0:
            errors.append(f"{voucher.get('id')} does not balance: debit={debit} credit={credit}")
        for line in voucher.get("inventoryEntries", []):
            if line["stockItem"] not in stock_items:
                errors.append(f"{voucher.get('id')} references unknown stock item {line['stockItem']}")

    recomputed = compute_expected(dataset)
    if expected != recomputed:
        errors.append("expected_results.json does not match recomputed expected results")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="datasets")
    args = parser.parse_args()
    root = Path(args.path)
    if not root.is_absolute():
        root = Path.cwd() / root

    folders = [root] if (root / "dataset.json").exists() else sorted(p for p in root.iterdir() if p.is_dir())
    report = {}
    total_errors = 0
    for folder in folders:
        errors = validate_dataset(folder)
        report[folder.name] = {"ok": not errors, "errors": errors}
        total_errors += len(errors)

    print(json.dumps({"ok": total_errors == 0, "datasetCount": len(folders), "errorCount": total_errors, "datasets": report}, indent=2))
    if total_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

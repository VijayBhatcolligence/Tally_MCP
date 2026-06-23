#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

GENERATION_DATE = "2026-06-23"
FISCAL_YEAR = "2026-2027"
FISCAL_START = date(2026, 4, 1)

SIZE_DEFAULTS = {
    "small": 25,
    "medium": 250,
    "large": 2000,
}

BUSINESS_NAMES = {
    "trader": "Aarav Trading Company",
    "service company": "Nisha Professional Services",
    "manufacturer": "Prakash Manufacturing Works",
    "retail shop": "Kaveri Retail Mart",
    "distributor": "Sankalp Distribution House",
}


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def mf(value):
    return float(money(value))


def stable_int(seed, *parts):
    text = "|".join([str(seed), *map(str, parts)])
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_scenarios(value):
    if not value:
        return {"GST"}
    parts = {p.strip().lower().replace("_", " ") for p in value.split(",") if p.strip()}
    if "none" in parts:
        return set()
    mapping = {
        "gst": "GST",
        "inventory": "inventory",
        "cost centers": "costCenters",
        "cost centre": "costCenters",
        "cost center": "costCenters",
        "payroll": "payroll",
    }
    return {mapping[p] for p in parts if p in mapping}


def company_for(seed, business_type):
    base = BUSINESS_NAMES.get(business_type, BUSINESS_NAMES["trader"])
    suffix = stable_int(seed, business_type) % 900 + 100
    return f"{base} {suffix}"


def base_groups():
    return [
        {"name": "Capital Account", "parent": "Primary", "classification": "equity"},
        {"name": "Current Assets", "parent": "Primary", "classification": "asset"},
        {"name": "Current Liabilities", "parent": "Primary", "classification": "liability"},
        {"name": "Sales Accounts", "parent": "Primary", "classification": "income"},
        {"name": "Purchase Accounts", "parent": "Primary", "classification": "expense"},
        {"name": "Direct Expenses", "parent": "Primary", "classification": "expense"},
        {"name": "Indirect Expenses", "parent": "Primary", "classification": "expense"},
        {"name": "Duties & Taxes", "parent": "Current Liabilities", "classification": "liability"},
        {"name": "Sundry Debtors", "parent": "Current Assets", "classification": "asset"},
        {"name": "Sundry Creditors", "parent": "Current Liabilities", "classification": "liability"},
        {"name": "Cash-in-Hand", "parent": "Current Assets", "classification": "asset"},
        {"name": "Bank Accounts", "parent": "Current Assets", "classification": "asset"},
        {"name": "Stock-in-Hand", "parent": "Current Assets", "classification": "asset"},
    ]


def base_masters(business_type, features):
    customers = [{"name": f"Customer {c}", "gstin": f"27ABCDE{idx:04d}F1Z{idx % 9}"} for idx, c in enumerate(["A", "B", "C", "D", "E"], 1)]
    suppliers = [{"name": f"Supplier {c}", "gstin": f"29ABCDE{idx:04d}G1Z{idx % 9}"} for idx, c in enumerate(["A", "B", "C", "D"], 1)]
    ledgers = [
        ("Capital", "Capital Account", "equity"),
        ("Cash", "Cash-in-Hand", "asset"),
        ("Bank", "Bank Accounts", "asset"),
        ("Sales", "Sales Accounts", "income"),
        ("Purchase", "Purchase Accounts", "expense"),
        ("Freight Expense", "Direct Expenses", "expense"),
        ("Rent Expense", "Indirect Expenses", "expense"),
        ("Round Off", "Indirect Expenses", "expense"),
    ]
    if features["gst"]:
        ledgers += [("GST Input", "Duties & Taxes", "asset"), ("GST Output", "Duties & Taxes", "liability")]
    if features["inventory"]:
        ledgers += [("Inventory", "Stock-in-Hand", "asset"), ("COGS", "Direct Expenses", "expense")]
    if features["payroll"]:
        ledgers += [("Salary Expense", "Indirect Expenses", "expense"), ("Salary Payable", "Current Liabilities", "liability")]
    ledgers += [(c["name"], "Sundry Debtors", "asset") for c in customers]
    ledgers += [(s["name"], "Sundry Creditors", "liability") for s in suppliers]
    stock_items = []
    if features["inventory"]:
        prefix = "SKU"
        if business_type == "manufacturer":
            prefix = "FG"
        stock_items = [
            {"name": f"{prefix}-A", "stockGroup": "Finished Goods", "baseUnit": "Nos"},
            {"name": f"{prefix}-B", "stockGroup": "Finished Goods", "baseUnit": "Nos"},
            {"name": f"{prefix}-C", "stockGroup": "Finished Goods", "baseUnit": "Nos"},
        ]
    return {
        "groups": base_groups(),
        "ledgers": [{"name": n, "group": g, "classification": c, "openingBalance": 0.0} for n, g, c in ledgers],
        "customers": customers,
        "suppliers": suppliers,
        "stockItems": stock_items,
    }


def entry(ledger, dc, amount):
    return {"ledger": ledger, "dc": dc, "amount": mf(amount)}


def voucher(number, voucher_type, vdate, narration, entries):
    return {
        "id": f"V{number:06d}",
        "voucherNumber": f"V{number:06d}",
        "type": voucher_type,
        "date": vdate.isoformat(),
        "narration": narration,
        "entries": entries,
    }


def add_sale(number, seed, vdate, masters, features):
    customer = masters["customers"][stable_int(seed, number, "customer") % len(masters["customers"])]["name"]
    base = Decimal(500 + (stable_int(seed, number, "sale") % 4500))
    entries = [entry(customer, "debit", base), entry("Sales", "credit", base)]
    if features["gst"]:
        gst = money(base * Decimal("0.18"))
        entries = [entry(customer, "debit", base + gst), entry("Sales", "credit", base), entry("GST Output", "credit", gst)]
    return voucher(number, "Sales", vdate, f"Credit sale to {customer}", entries)


def add_purchase(number, seed, vdate, masters, features):
    supplier = masters["suppliers"][stable_int(seed, number, "supplier") % len(masters["suppliers"])]["name"]
    base = Decimal(400 + (stable_int(seed, number, "purchase") % 3600))
    debit_ledger = "Inventory" if features["inventory"] else "Purchase"
    entries = [entry(debit_ledger, "debit", base), entry(supplier, "credit", base)]
    if features["gst"]:
        gst = money(base * Decimal("0.18"))
        entries = [entry(debit_ledger, "debit", base), entry("GST Input", "debit", gst), entry(supplier, "credit", base + gst)]
    return voucher(number, "Purchase", vdate, f"Credit purchase from {supplier}", entries)


def add_receipt(number, seed, vdate, masters):
    customer = masters["customers"][stable_int(seed, number, "receipt") % len(masters["customers"])]["name"]
    amount = Decimal(300 + (stable_int(seed, number, "receipt-amount") % 2500))
    return voucher(number, "Receipt", vdate, f"Receipt from {customer}", [entry("Bank", "debit", amount), entry(customer, "credit", amount)])


def add_payment(number, seed, vdate, masters):
    supplier = masters["suppliers"][stable_int(seed, number, "payment") % len(masters["suppliers"])]["name"]
    amount = Decimal(250 + (stable_int(seed, number, "payment-amount") % 2200))
    return voucher(number, "Payment", vdate, f"Payment to {supplier}", [entry(supplier, "debit", amount), entry("Bank", "credit", amount)])


def add_contra(number, seed, vdate):
    amount = Decimal(500 + (stable_int(seed, number, "contra") % 3000))
    return voucher(number, "Contra", vdate, "Cash deposit into bank", [entry("Bank", "debit", amount), entry("Cash", "credit", amount)])


def add_journal(number, seed, vdate, features):
    if features["payroll"] and number % 3 == 0:
        amount = Decimal(1200 + (stable_int(seed, number, "salary") % 5000))
        return voucher(number, "Journal", vdate, "Salary accrual", [entry("Salary Expense", "debit", amount), entry("Salary Payable", "credit", amount)])
    amount = Decimal(800 + (stable_int(seed, number, "rent") % 2500))
    return voucher(number, "Journal", vdate, "Rent accrual", [entry("Rent Expense", "debit", amount), entry("Bank", "credit", amount)])


def generate_vouchers(seed, masters, features, start_number, count):
    vouchers = []
    cycle = ["Sales", "Purchase", "Receipt", "Payment", "Contra", "Journal"]
    for offset in range(count):
        number = start_number + offset
        vdate = FISCAL_START + timedelta(days=(number - 1) % 330)
        kind = cycle[(number - 1) % len(cycle)]
        if kind == "Sales":
            vouchers.append(add_sale(number, seed, vdate, masters, features))
        elif kind == "Purchase":
            vouchers.append(add_purchase(number, seed, vdate, masters, features))
        elif kind == "Receipt":
            vouchers.append(add_receipt(number, seed, vdate, masters))
        elif kind == "Payment":
            vouchers.append(add_payment(number, seed, vdate, masters))
        elif kind == "Contra":
            vouchers.append(add_contra(number, seed, vdate))
        else:
            vouchers.append(add_journal(number, seed, vdate, features))
    return vouchers


def compute_reports(ledgers, vouchers):
    meta = {l["name"]: l for l in ledgers}
    balances = {l["name"]: money(l.get("openingBalance", 0)) for l in ledgers}
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for v in vouchers:
        vd = Decimal("0.00")
        vc = Decimal("0.00")
        for e in v["entries"]:
            amt = money(e["amount"])
            if e["dc"] == "debit":
                balances[e["ledger"]] = balances.get(e["ledger"], Decimal("0.00")) + amt
                vd += amt
                total_debit += amt
            else:
                balances[e["ledger"]] = balances.get(e["ledger"], Decimal("0.00")) - amt
                vc += amt
                total_credit += amt
        if vd != vc:
            raise ValueError(f"Voucher {v['voucherNumber']} is unbalanced: {vd} != {vc}")

    trial = []
    ledger_balances = {}
    pl_rows = []
    bs_rows = []
    for ledger in sorted(balances):
        bal = balances[ledger]
        info = meta.get(ledger, {"group": "", "classification": "unknown"})
        row = {
            "ledger": ledger,
            "group": info["group"],
            "classification": info["classification"],
            "debit": mf(bal if bal > 0 else 0),
            "credit": mf(-bal if bal < 0 else 0),
            "neutralBalance": mf(bal),
            "tallySignedClosingBalance": mf(-bal),
        }
        trial.append(row)
        ledger_balances[ledger] = row
        if info["classification"] in ("income", "expense"):
            pl_rows.append({"ledger": ledger, "classification": info["classification"], "amount": mf(-bal)})
        elif bal != 0:
            bs_rows.append({"ledger": ledger, "classification": info["classification"], "closingBalance": mf(-bal)})
    net_profit = sum(money(r["amount"]) for r in pl_rows)
    return {
        "trial_balance": {"rows": trial, "totalDebit": mf(total_debit), "totalCredit": mf(total_credit), "balanced": total_debit == total_credit},
        "profit_loss": {"rows": sorted(pl_rows, key=lambda r: r["ledger"]), "netProfit": mf(net_profit)},
        "balance_sheet": {"rows": sorted(bs_rows, key=lambda r: r["ledger"]), "netProfit": mf(net_profit)},
        "ledger_balances": ledger_balances,
    }


def write_dataset(path, manifest, masters, vouchers):
    path.mkdir(parents=True, exist_ok=True)
    write_json(path / "manifest.json", manifest)
    write_json(path / "masters" / "company.json", manifest["company"])
    write_json(path / "masters" / "groups.json", masters["groups"])
    write_json(path / "masters" / "ledgers.json", masters["ledgers"])
    write_json(path / "masters" / "customers.json", masters["customers"])
    write_json(path / "masters" / "suppliers.json", masters["suppliers"])
    write_json(path / "masters" / "stock_items.json", masters["stockItems"])
    write_json(path / "transactions" / "vouchers.json", vouchers)
    reports = compute_reports(masters["ledgers"], vouchers)
    for name, data in reports.items():
        write_json(path / "reports" / f"{name}.json", data)
    log = path / "generation_log.md"
    if not log.exists():
        log.write_text(f"# Generation Log\n\n", encoding="utf-8")
    log.write_text(log.read_text(encoding="utf-8") + f"- {GENERATION_DATE}: voucher_count={len(vouchers)}, last_voucher={manifest['lastVoucherNumber']}, mode={manifest['lastOperation']}\n", encoding="utf-8")


def new_dataset(args):
    features = {
        "gst": "GST" in parse_scenarios(args.scenarios),
        "inventory": "inventory" in parse_scenarios(args.scenarios),
        "costCenters": "costCenters" in parse_scenarios(args.scenarios),
        "payroll": "payroll" in parse_scenarios(args.scenarios),
    }
    count = args.voucher_count or SIZE_DEFAULTS[args.size]
    seed = args.seed
    company = {
        "name": args.company_name or company_for(seed, args.business_type),
        "fiscalYearFrom": "2026-04-01",
        "booksBeginningFrom": "2026-04-01",
        "currency": "INR",
    }
    masters = base_masters(args.business_type, features)
    vouchers = generate_vouchers(seed, masters, features, 1, count)
    manifest = {
        "seed": seed,
        "companyName": company["name"],
        "company": company,
        "businessType": args.business_type,
        "generationDate": GENERATION_DATE,
        "voucherCount": len(vouchers),
        "fiscalYears": [FISCAL_YEAR],
        "features": features,
        "lastVoucherNumber": len(vouchers),
        "lastOperation": "new",
        "extensions": [],
    }
    write_dataset(Path(args.output), manifest, masters, vouchers)


def inspect_dataset(path):
    manifest = read_json(path / "manifest.json")
    vouchers = read_json(path / "transactions" / "vouchers.json")
    ledgers = read_json(path / "masters" / "ledgers.json")
    stock_items = read_json(path / "masters" / "stock_items.json")
    dates = sorted({v["date"][:4] for v in vouchers})
    return {
        "companyName": manifest["companyName"],
        "businessType": manifest["businessType"],
        "voucherCount": len(vouchers),
        "lastVoucherNumber": manifest["lastVoucherNumber"],
        "fiscalYears": manifest["fiscalYears"],
        "calendarYearsCovered": dates,
        "gst": manifest["features"].get("gst", False),
        "inventory": bool(stock_items) or manifest["features"].get("inventory", False),
        "ledgerCount": len(ledgers),
        "stockItemCount": len(stock_items),
    }


def extend_dataset(args):
    path = Path(args.path)
    manifest = read_json(path / "manifest.json")
    masters = {
        "groups": read_json(path / "masters" / "groups.json"),
        "ledgers": read_json(path / "masters" / "ledgers.json"),
        "customers": read_json(path / "masters" / "customers.json"),
        "suppliers": read_json(path / "masters" / "suppliers.json"),
        "stockItems": read_json(path / "masters" / "stock_items.json"),
    }
    vouchers = read_json(path / "transactions" / "vouchers.json")
    start = int(manifest["lastVoucherNumber"]) + 1
    new_vouchers = generate_vouchers(manifest["seed"], masters, manifest["features"], start, args.voucher_count)
    vouchers.extend(new_vouchers)
    manifest["voucherCount"] = len(vouchers)
    manifest["lastVoucherNumber"] = start + args.voucher_count - 1
    manifest["lastOperation"] = "extend"
    manifest.setdefault("extensions", []).append({"generationDate": GENERATION_DATE, "voucherCount": args.voucher_count, "fromVoucher": start, "toVoucher": manifest["lastVoucherNumber"]})
    write_dataset(path, manifest, masters, vouchers)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new")
    new.add_argument("--output", required=True)
    new.add_argument("--size", choices=sorted(SIZE_DEFAULTS), default="medium")
    new.add_argument("--business-type", choices=sorted(BUSINESS_NAMES), default="trader")
    new.add_argument("--scenarios", default="GST")
    new.add_argument("--voucher-count", type=int)
    new.add_argument("--seed", type=int, default=20260623)
    new.add_argument("--company-name")
    ext = sub.add_parser("extend")
    ext.add_argument("--path", required=True)
    ext.add_argument("--voucher-count", type=int, default=100)
    ins = sub.add_parser("inspect")
    ins.add_argument("--path", required=True)
    args = parser.parse_args()
    if args.command == "new":
        new_dataset(args)
        print(json.dumps(inspect_dataset(Path(args.output)), indent=2))
    elif args.command == "extend":
        before = inspect_dataset(Path(args.path))
        extend_dataset(args)
        after = inspect_dataset(Path(args.path))
        print(json.dumps({"before": before, "after": after}, indent=2))
    elif args.command == "inspect":
        print(json.dumps(inspect_dataset(Path(args.path)), indent=2))


if __name__ == "__main__":
    main()

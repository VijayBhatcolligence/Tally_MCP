#!/usr/bin/env python3
import argparse
import json
import shutil
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dataset-config.json"
DATASETS_DIR = ROOT / "datasets"


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money_float(value):
    return float(money(value))


BASE_GROUPS = [
    ("Capital Account", "Primary", "equity"),
    ("Current Assets", "Primary", "asset"),
    ("Current Liabilities", "Primary", "liability"),
    ("Fixed Assets", "Primary", "asset"),
    ("Direct Expenses", "Primary", "expense"),
    ("Indirect Expenses", "Primary", "expense"),
    ("Direct Incomes", "Primary", "income"),
    ("Indirect Incomes", "Primary", "income"),
    ("Sales Accounts", "Direct Incomes", "income"),
    ("Purchase Accounts", "Direct Expenses", "expense"),
    ("Sundry Debtors", "Current Assets", "asset"),
    ("Sundry Creditors", "Current Liabilities", "liability"),
    ("Cash-in-Hand", "Current Assets", "asset"),
    ("Bank Accounts", "Current Assets", "asset"),
    ("Duties & Taxes", "Current Liabilities", "liability"),
    ("Stock-in-Hand", "Current Assets", "asset"),
]

BASE_LEDGERS = [
    ("Capital", "Capital Account", "equity"),
    ("Cash", "Cash-in-Hand", "asset"),
    ("Bank", "Bank Accounts", "asset"),
    ("Sales", "Sales Accounts", "income"),
    ("Purchase", "Purchase Accounts", "expense"),
    ("Sales Return", "Sales Accounts", "contra_income"),
    ("Purchase Return", "Purchase Accounts", "contra_expense"),
    ("Customer A", "Sundry Debtors", "asset"),
    ("Customer B", "Sundry Debtors", "asset"),
    ("Customer C", "Sundry Debtors", "asset"),
    ("Supplier A", "Sundry Creditors", "liability"),
    ("Supplier B", "Sundry Creditors", "liability"),
    ("Supplier C", "Sundry Creditors", "liability"),
    ("GST Input", "Duties & Taxes", "asset"),
    ("GST Output", "Duties & Taxes", "liability"),
    ("Inventory", "Stock-in-Hand", "asset"),
    ("COGS", "Direct Expenses", "expense"),
    ("Rent Expense", "Indirect Expenses", "expense"),
    ("Salary Expense", "Indirect Expenses", "expense"),
    ("Depreciation Expense", "Indirect Expenses", "expense"),
    ("Accrued Expenses", "Current Liabilities", "liability"),
]


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def groups(names=None):
    selected = BASE_GROUPS if names is None else [g for g in BASE_GROUPS if g[0] in names]
    return [{"name": n, "parent": p, "classification": c} for n, p, c in selected]


def ledgers(names):
    selected = [l for l in BASE_LEDGERS if l[0] in set(names)]
    return [{"name": n, "group": g, "classification": c, "openingBalance": 0.0} for n, g, c in selected]


def entry(ledger, dc, amount):
    return {"ledger": ledger, "dc": dc, "amount": money_float(amount)}


def voucher(v_id, v_type, date, narration, entries, inventory_entries=None):
    v = {"id": v_id, "type": v_type, "date": date, "narration": narration, "entries": entries}
    if inventory_entries:
        v["inventoryEntries"] = inventory_entries
    return v


def dataset(ds_id, name, level, purpose, ledger_names, vouchers, stock_items=None, groups_used=None, scenario=None):
    config = load_config()
    return {
        "metadata": {"id": ds_id, "name": name, "level": level, "purpose": purpose, "scenario": scenario or name},
        "company": config["company"],
        "groups": groups(groups_used),
        "ledgers": ledgers(ledger_names),
        "stockItems": stock_items or [],
        "vouchers": vouchers,
    }


def compute_expected(ds):
    ledger_meta = {l["name"]: l for l in ds["ledgers"]}
    balances = {l["name"]: money(l.get("openingBalance", 0)) for l in ds["ledgers"]}
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")

    for v in ds["vouchers"]:
        v_debit = Decimal("0.00")
        v_credit = Decimal("0.00")
        for e in v["entries"]:
            amt = money(e["amount"])
            if e["dc"] == "debit":
                balances[e["ledger"]] += amt
                debit_total += amt
                v_debit += amt
            elif e["dc"] == "credit":
                balances[e["ledger"]] -= amt
                credit_total += amt
                v_credit += amt
            else:
                raise ValueError(f"Invalid dc in {v['id']}: {e['dc']}")
        if v_debit != v_credit:
            raise ValueError(f"Voucher {v['id']} does not balance: {v_debit} != {v_credit}")

    trial = []
    ledger_balances = {}
    profit_rows = []
    balance_rows = []
    closing_balances = {"stockItems": []}

    for ledger_name in sorted(balances):
        bal = balances[ledger_name]
        meta = ledger_meta[ledger_name]
        debit = bal if bal > 0 else Decimal("0.00")
        credit = -bal if bal < 0 else Decimal("0.00")
        tally_signed = -bal
        row = {
            "ledger": ledger_name,
            "group": meta["group"],
            "classification": meta["classification"],
            "debit": money_float(debit),
            "credit": money_float(credit),
            "neutralBalance": money_float(bal),
            "tallySignedClosingBalance": money_float(tally_signed),
        }
        trial.append(row)
        ledger_balances[ledger_name] = row

        cls = meta["classification"]
        if cls in ("income", "expense", "contra_income", "contra_expense"):
            amount = -bal
            profit_rows.append({
                "ledger": ledger_name,
                "classification": cls,
                "amount": money_float(amount),
            })
        elif bal != 0:
            balance_rows.append({
                "ledger": ledger_name,
                "classification": cls,
                "closingBalance": money_float(tally_signed),
            })

    net_profit = sum(money(r["amount"]) for r in profit_rows)
    asset_total = sum(money(r["closingBalance"]) for r in balance_rows if r["classification"] == "asset")
    liability_equity_total = sum(money(r["closingBalance"]) for r in balance_rows if r["classification"] in ("liability", "equity"))

    stock_qty = {}
    stock_value = {}
    for v in ds["vouchers"]:
        for line in v.get("inventoryEntries", []):
            item = line["stockItem"]
            qty = money(line.get("quantity", 0))
            value = money(line.get("value", 0))
            direction = line.get("direction", "in")
            if direction == "in":
                stock_qty[item] = stock_qty.get(item, Decimal("0.00")) + qty
                stock_value[item] = stock_value.get(item, Decimal("0.00")) + value
            else:
                stock_qty[item] = stock_qty.get(item, Decimal("0.00")) - qty
                stock_value[item] = stock_value.get(item, Decimal("0.00")) - value
    for item in sorted(stock_qty):
        closing_balances["stockItems"].append({
            "stockItem": item,
            "quantity": money_float(stock_qty[item]),
            "value": money_float(stock_value[item]),
        })

    return {
        "trialBalance": trial,
        "profitLoss": {
            "rows": sorted(profit_rows, key=lambda r: r["ledger"]),
            "netProfit": money_float(net_profit),
        },
        "balanceSheet": {
            "rows": sorted(balance_rows, key=lambda r: r["ledger"]),
            "assetTotal": money_float(asset_total),
            "liabilityEquityTotalBeforeProfit": money_float(liability_equity_total),
            "netProfit": money_float(net_profit),
            "checkTotalWithProfit": money_float(asset_total + liability_equity_total + net_profit),
        },
        "ledgerBalances": ledger_balances,
        "closingBalances": closing_balances,
        "controlTotals": {
            "totalDebits": money_float(debit_total),
            "totalCredits": money_float(credit_total),
            "balanced": debit_total == credit_total,
        },
    }


def tally_import(ds):
    tool_map = {
        "Sales": "create-sales-voucher",
        "Purchase": "create-purchase-voucher",
        "Payment": "create-payment-voucher",
        "Receipt": "create-receipt-voucher",
        "Contra": "create-contra-voucher",
        "Journal": "create-journal-voucher",
        "Credit Note": "create-credit-note",
        "Debit Note": "create-debit-note",
    }

    def signed(e):
        return -money_float(e["amount"]) if e["dc"] == "debit" else money_float(e["amount"])

    return {
        "company": ds["company"],
        "createGroupCalls": [{"name": g["name"], "parent": g["parent"]} for g in ds["groups"]],
        "createLedgerCalls": [{"name": l["name"], "parent": l["group"], "openingBalance": l["openingBalance"]} for l in ds["ledgers"]],
        "createStockItemCalls": ds["stockItems"],
        "createVoucherCalls": [
            {
                "tool": tool_map[v["type"]],
                "voucherNumber": v["id"],
                "date": v["date"],
                "narration": v["narration"],
                "entries": [{"ledgerName": e["ledger"], "amount": signed(e)} for e in v["entries"]],
            }
            for v in ds["vouchers"]
        ],
    }


def foundry_import(ds):
    return {
        "company": ds["company"],
        "chartOfAccounts": ds["ledgers"],
        "stockItems": ds["stockItems"],
        "journalEntries": [
            {
                "externalId": v["id"],
                "entryType": v["type"],
                "postingDate": v["date"],
                "memo": v["narration"],
                "lines": deepcopy(v["entries"]),
            }
            for v in ds["vouchers"]
        ],
    }


def scenario_definitions():
    d = "2026-04-01"
    return [
        dataset("001_capital_introduction", "Capital Introduction", 1, "Owner introduces capital in cash", ["Capital", "Cash"], [voucher("V001", "Journal", d, "Capital introduced", [entry("Cash", "debit", 10000), entry("Capital", "credit", 10000)])]),
        dataset("002_cash_purchase", "Cash Purchase", 1, "Purchase goods/expense for cash", ["Cash", "Purchase"], [voucher("V001", "Purchase", d, "Cash purchase", [entry("Purchase", "debit", 1200), entry("Cash", "credit", 1200)])]),
        dataset("003_cash_sale", "Cash Sale", 1, "Sell goods for cash", ["Cash", "Sales"], [voucher("V001", "Sales", d, "Cash sale", [entry("Cash", "debit", 1800), entry("Sales", "credit", 1800)])]),
        dataset("004_credit_purchase", "Credit Purchase", 1, "Purchase on credit from supplier", ["Purchase", "Supplier A"], [voucher("V001", "Purchase", d, "Credit purchase", [entry("Purchase", "debit", 2500), entry("Supplier A", "credit", 2500)])]),
        dataset("005_credit_sale", "Credit Sale", 1, "Sale on credit to customer", ["Customer A", "Sales"], [voucher("V001", "Sales", d, "Credit sale", [entry("Customer A", "debit", 3200), entry("Sales", "credit", 3200)])]),
        dataset("006_receipt_voucher", "Receipt Voucher", 1, "Receive money from customer", ["Customer A", "Bank", "Sales"], [voucher("V001", "Sales", d, "Opening credit sale", [entry("Customer A", "debit", 2000), entry("Sales", "credit", 2000)]), voucher("V002", "Receipt", "2026-04-02", "Customer receipt", [entry("Bank", "debit", 1500), entry("Customer A", "credit", 1500)])], groups_used=None),
        dataset("007_payment_voucher", "Payment Voucher", 1, "Pay supplier", ["Supplier A", "Bank", "Purchase"], [voucher("V001", "Purchase", d, "Opening credit purchase", [entry("Purchase", "debit", 1800), entry("Supplier A", "credit", 1800)]), voucher("V002", "Payment", "2026-04-02", "Supplier payment", [entry("Supplier A", "debit", 1000), entry("Bank", "credit", 1000)])]),
        dataset("008_contra_voucher", "Contra Voucher", 1, "Move cash to bank", ["Cash", "Bank", "Capital"], [voucher("V001", "Journal", d, "Opening cash", [entry("Cash", "debit", 5000), entry("Capital", "credit", 5000)]), voucher("V002", "Contra", "2026-04-02", "Cash deposit to bank", [entry("Bank", "debit", 3000), entry("Cash", "credit", 3000)])], groups_used=None),
        dataset("009_journal_voucher", "Journal Voucher", 1, "Accrue expense", ["Rent Expense", "Accrued Expenses"], [voucher("V001", "Journal", d, "Rent accrued", [entry("Rent Expense", "debit", 900), entry("Accrued Expenses", "credit", 900)])]),
        dataset("010_purchase_return", "Purchase Return", 1, "Return part of credit purchase", ["Purchase", "Purchase Return", "Supplier A"], [voucher("V001", "Purchase", d, "Credit purchase", [entry("Purchase", "debit", 2000), entry("Supplier A", "credit", 2000)]), voucher("V002", "Debit Note", "2026-04-02", "Purchase return", [entry("Supplier A", "debit", 500), entry("Purchase Return", "credit", 500)])]),
        dataset("011_sales_return", "Sales Return", 1, "Customer returns goods", ["Customer A", "Sales", "Sales Return"], [voucher("V001", "Sales", d, "Credit sale", [entry("Customer A", "debit", 2600), entry("Sales", "credit", 2600)]), voucher("V002", "Credit Note", "2026-04-02", "Sales return", [entry("Sales Return", "debit", 600), entry("Customer A", "credit", 600)])]),
        dataset("012_gst_purchase", "GST Purchase", 1, "Purchase with input GST", ["Purchase", "GST Input", "Supplier A"], [voucher("V001", "Purchase", d, "GST purchase", [entry("Purchase", "debit", 1000), entry("GST Input", "debit", 180), entry("Supplier A", "credit", 1180)])]),
        dataset("013_gst_sale", "GST Sale", 1, "Sale with output GST", ["Customer A", "Sales", "GST Output"], [voucher("V001", "Sales", d, "GST sale", [entry("Customer A", "debit", 1180), entry("Sales", "credit", 1000), entry("GST Output", "credit", 180)])]),
        dataset("014_multiple_customers", "Multiple Customers", 2, "Multiple customer credit sales and receipt", ["Customer A", "Customer B", "Customer C", "Sales", "Bank"], [voucher("V001", "Sales", d, "Sale A", [entry("Customer A", "debit", 1000), entry("Sales", "credit", 1000)]), voucher("V002", "Sales", "2026-04-02", "Sale B", [entry("Customer B", "debit", 1500), entry("Sales", "credit", 1500)]), voucher("V003", "Sales", "2026-04-03", "Sale C", [entry("Customer C", "debit", 500), entry("Sales", "credit", 500)]), voucher("V004", "Receipt", "2026-04-04", "Receipt A", [entry("Bank", "debit", 700), entry("Customer A", "credit", 700)])]),
        dataset("015_multiple_suppliers", "Multiple Suppliers", 2, "Multiple supplier purchases and payment", ["Supplier A", "Supplier B", "Supplier C", "Purchase", "Bank"], [voucher("V001", "Purchase", d, "Purchase A", [entry("Purchase", "debit", 800), entry("Supplier A", "credit", 800)]), voucher("V002", "Purchase", "2026-04-02", "Purchase B", [entry("Purchase", "debit", 1200), entry("Supplier B", "credit", 1200)]), voucher("V003", "Purchase", "2026-04-03", "Purchase C", [entry("Purchase", "debit", 600), entry("Supplier C", "credit", 600)]), voucher("V004", "Payment", "2026-04-04", "Payment B", [entry("Supplier B", "debit", 500), entry("Bank", "credit", 500)])]),
        dataset("016_inventory_purchase_sale", "Inventory Purchase Sale", 2, "Inventory purchase, sale and COGS", ["Inventory", "Supplier A", "Customer A", "Sales", "COGS"], [voucher("V001", "Purchase", d, "Inventory purchase", [entry("Inventory", "debit", 1000), entry("Supplier A", "credit", 1000)], [{"stockItem": "Widget A", "quantity": 10, "value": 1000, "direction": "in"}]), voucher("V002", "Sales", "2026-04-02", "Inventory sale", [entry("Customer A", "debit", 900), entry("Sales", "credit", 900)]), voucher("V003", "Journal", "2026-04-02", "COGS recognition", [entry("COGS", "debit", 400), entry("Inventory", "credit", 400)], [{"stockItem": "Widget A", "quantity": 4, "value": 400, "direction": "out"}])], stock_items=[{"name": "Widget A", "stockGroup": "Finished Goods", "baseUnit": "Nos"}]),
        dataset("017_month_end_adjustments", "Month End Adjustments", 2, "Accrual and depreciation adjustments", ["Rent Expense", "Salary Expense", "Depreciation Expense", "Accrued Expenses"], [voucher("V001", "Journal", "2026-04-30", "Rent accrual", [entry("Rent Expense", "debit", 1000), entry("Accrued Expenses", "credit", 1000)]), voucher("V002", "Journal", "2026-04-30", "Salary accrual", [entry("Salary Expense", "debit", 1500), entry("Accrued Expenses", "credit", 1500)]), voucher("V003", "Journal", "2026-04-30", "Depreciation", [entry("Depreciation Expense", "debit", 300), entry("Accrued Expenses", "credit", 300)])]),
        dataset("018_profit_scenario", "Profit Scenario", 2, "Revenue exceeds expenses", ["Cash", "Sales", "Purchase", "Rent Expense"], [voucher("V001", "Sales", d, "Cash sale", [entry("Cash", "debit", 5000), entry("Sales", "credit", 5000)]), voucher("V002", "Purchase", "2026-04-02", "Cash purchase", [entry("Purchase", "debit", 1500), entry("Cash", "credit", 1500)]), voucher("V003", "Payment", "2026-04-03", "Rent paid", [entry("Rent Expense", "debit", 700), entry("Cash", "credit", 700)])]),
        dataset("019_loss_scenario", "Loss Scenario", 2, "Expenses exceed revenue", ["Cash", "Sales", "Purchase", "Rent Expense", "Salary Expense"], [voucher("V001", "Sales", d, "Cash sale", [entry("Cash", "debit", 1000), entry("Sales", "credit", 1000)]), voucher("V002", "Purchase", "2026-04-02", "Cash purchase", [entry("Purchase", "debit", 1800), entry("Cash", "credit", 1800)]), voucher("V003", "Payment", "2026-04-03", "Rent paid", [entry("Rent Expense", "debit", 800), entry("Cash", "credit", 800)]), voucher("V004", "Payment", "2026-04-04", "Salary paid", [entry("Salary Expense", "debit", 600), entry("Cash", "credit", 600)])]),
        stress_dataset("020_stress_small", 100),
    ]


def stress_dataset(ds_id, count):
    vouchers = []
    ledger_names = ["Cash", "Bank", "Sales", "Purchase", "Rent Expense", "Customer A", "Supplier A"]
    for i in range(1, count + 1):
        day = ((i - 1) % 28) + 1
        date = f"2026-04-{day:02d}"
        amount = 100 + (i % 37) * 10
        if i % 4 == 1:
            vouchers.append(voucher(f"ST{i:05d}", "Sales", date, "Deterministic cash sale", [entry("Cash", "debit", amount), entry("Sales", "credit", amount)]))
        elif i % 4 == 2:
            vouchers.append(voucher(f"ST{i:05d}", "Purchase", date, "Deterministic credit purchase", [entry("Purchase", "debit", amount), entry("Supplier A", "credit", amount)]))
        elif i % 4 == 3:
            vouchers.append(voucher(f"ST{i:05d}", "Receipt", date, "Deterministic customer receipt", [entry("Bank", "debit", amount), entry("Customer A", "credit", amount)]))
        else:
            vouchers.append(voucher(f"ST{i:05d}", "Journal", date, "Deterministic receivable setup", [entry("Customer A", "debit", amount), entry("Sales", "credit", amount)]))
    return dataset(ds_id, f"Stress Small {count}", 3, f"Deterministic {count} voucher stress fixture", ledger_names, vouchers)


def readme(ds, expected):
    return f"""# {ds['metadata']['id']} - {ds['metadata']['name']}

## Business Scenario

{ds['metadata']['purpose']}

## Accounting Purpose

This fixture validates deterministic double-entry posting for `{ds['metadata']['scenario']}`.

## Expected Accounting Outcome

- Total debits: {expected['controlTotals']['totalDebits']}
- Total credits: {expected['controlTotals']['totalCredits']}
- Net profit: {expected['profitLoss']['netProfit']}
- Voucher count: {len(ds['vouchers'])}

## Reports Expected To Change

- Trial Balance
- Ledger Balances
- Profit & Loss when income or expense ledgers are present
- Balance Sheet when asset, liability, or equity ledgers are present
"""


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def emit(ds, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = compute_expected(ds)
    write_json(output_dir / "dataset.json", ds)
    write_json(output_dir / "expected_results.json", expected)
    write_json(output_dir / "tally_import.json", tally_import(ds))
    write_json(output_dir / "foundry_import.json", foundry_import(ds))
    (output_dir / "README.md").write_text(readme(ds, expected), encoding="utf-8")


def generate_all(output_dir=DATASETS_DIR):
    if output_dir.exists():
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
    output_dir.mkdir(parents=True, exist_ok=True)
    for ds in scenario_definitions():
        emit(ds, output_dir / ds["metadata"]["id"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dataset")
    parser.add_argument("--stress-scale", type=int)
    parser.add_argument("--output", help="Output folder. With --all, creates all dataset folders inside this folder. With --dataset, writes that dataset into this folder.")
    args = parser.parse_args()

    if args.stress_scale:
        out = Path(args.output) if args.output else DATASETS_DIR / f"stress_{args.stress_scale}"
        emit(stress_dataset(f"stress_{args.stress_scale}", args.stress_scale), out)
        return

    scenarios = {ds["metadata"]["id"]: ds for ds in scenario_definitions()}
    if args.dataset:
        if args.dataset not in scenarios:
            raise SystemExit(f"Unknown dataset: {args.dataset}")
        out = Path(args.output) if args.output else DATASETS_DIR / args.dataset
        if args.output:
            out = out / args.dataset
        emit(scenarios[args.dataset], out)
        return

    if args.all:
        generate_all(Path(args.output) if args.output else DATASETS_DIR)
        return

    parser.print_help()


if __name__ == "__main__":
    main()

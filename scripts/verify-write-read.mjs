import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const root = new URL('../', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const targetCompany = process.env.TALLY_TEST_COMPANY || 'Good_one';
const voucherDate = process.env.TALLY_TEST_DATE || '2026-06-01';
const suffix = process.env.TALLY_TEST_SUFFIX || Date.now().toString().slice(-6);
const serverPath = new URL('../dist/index.mjs', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

const names = {
    customer: `Codex E2E Customer ${suffix}`,
    supplier: `Codex E2E Supplier ${suffix}`,
    sales: `Codex E2E Sales ${suffix}`,
    purchase: `Codex E2E Purchase ${suffix}`
};

function parseTsv(text) {
    const lines = text.trim().split(/\r?\n/);
    if (lines.length < 2)
        return [];
    const headers = lines[0].split('\t');
    return lines.slice(1).map(line => {
        const values = line.split('\t');
        return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? '']));
    });
}

function numberValue(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
}

async function main() {
    const transport = new StdioClientTransport({
        command: 'node',
        args: [serverPath],
        cwd: root
    });
    const client = new Client({ name: 'tally-write-read-verifier', version: '1.0.0' });
    await client.connect(transport);

    async function call(name, args) {
        const res = await client.callTool({ name, arguments: args });
        const text = res.content?.[0]?.text ?? '';
        if (res.isError)
            throw new Error(`${name} failed: ${text}`);
        return text;
    }

    async function importCall(name, args) {
        const text = await call(name, args);
        const parsed = JSON.parse(text);
        if (!parsed.ok)
            throw new Error(`${name} import failed: ${text}`);
        return parsed;
    }

    async function reportTable(name, args) {
        const text = await call(name, args);
        const parsed = JSON.parse(text);
        if (!parsed.tableID)
            throw new Error(`${name} returned no tableID: ${text}`);
        return parsed.tableID;
    }

    const writes = [];
    writes.push(await importCall('create-ledger', { targetCompany, name: names.customer, parent: 'Sundry Debtors' }));
    writes.push(await importCall('create-ledger', { targetCompany, name: names.supplier, parent: 'Sundry Creditors' }));
    writes.push(await importCall('create-ledger', { targetCompany, name: names.sales, parent: 'Sales Accounts' }));
    writes.push(await importCall('create-ledger', { targetCompany, name: names.purchase, parent: 'Purchase Accounts' }));
    writes.push(await importCall('create-sales-voucher', {
        targetCompany,
        date: voucherDate,
        voucherNumber: `CDEX-S-${suffix}`,
        partyLedgerName: names.customer,
        narration: 'Codex MCP verification sales',
        entries: [
            { ledgerName: names.customer, amount: -1000 },
            { ledgerName: names.sales, amount: 1000 }
        ]
    }));
    writes.push(await importCall('create-purchase-voucher', {
        targetCompany,
        date: voucherDate,
        voucherNumber: `CDEX-P-${suffix}`,
        partyLedgerName: names.supplier,
        narration: 'Codex MCP verification purchase',
        entries: [
            { ledgerName: names.purchase, amount: -400 },
            { ledgerName: names.supplier, amount: 400 }
        ]
    }));

    const tb = await reportTable('trial-balance', { targetCompany, fromDate: voucherDate, toDate: voucherDate });
    const pl = await reportTable('profit-loss', { targetCompany, fromDate: voucherDate, toDate: voucherDate });
    const bs = await reportTable('balance-sheet', { targetCompany, toDate: voucherDate });

    const tbRows = parseTsv(await call('query-database', {
        sql: `select ledger_name, group_name, net_debit, net_credit from ${tb} where ledger_name like 'Codex E2E % ${suffix}' order by ledger_name`
    }));
    const plRows = parseTsv(await call('query-database', {
        sql: `select ledger_name, group_name, amount from ${pl} where ledger_name like 'Codex E2E % ${suffix}' order by ledger_name`
    }));
    const bsRows = parseTsv(await call('query-database', {
        sql: `select ledger_name, group_name, closing_balance from ${bs} where ledger_name like 'Codex E2E % ${suffix}' order by ledger_name`
    }));

    const plByLedger = Object.fromEntries(plRows.map(row => [row.ledger_name, numberValue(row.amount)]));
    const bsByLedger = Object.fromEntries(bsRows.map(row => [row.ledger_name, numberValue(row.closing_balance)]));
    const assertions = {
        salesInProfitLoss: plByLedger[names.sales] === 1000,
        purchaseInProfitLoss: plByLedger[names.purchase] === -400,
        customerInBalanceSheet: bsByLedger[names.customer] === -1000,
        supplierInBalanceSheet: bsByLedger[names.supplier] === 400,
        trialBalanceRowsPresent: tbRows.length === 4
    };

    await client.close();
    console.log(JSON.stringify({
        ok: Object.values(assertions).every(Boolean),
        targetCompany,
        voucherDate,
        suffix,
        names,
        writes: writes.map(({ created, altered, deleted, errors, exceptions, lineError }) => ({ created, altered, deleted, errors, exceptions, lineError })),
        assertions,
        reports: {
            trialBalance: tbRows,
            profitLoss: plRows,
            balanceSheet: bsRows
        }
    }, null, 2));
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});


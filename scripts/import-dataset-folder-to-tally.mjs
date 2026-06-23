import fs from 'node:fs';
import path from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const root = process.cwd();
const datasetRoot = path.resolve(process.argv[2] || 'dataset');
const targetCompany = process.argv[3] || 'Good_one';
process.env.TALLY_HTTP_TIMEOUT_MS = process.env.TALLY_HTTP_TIMEOUT_MS || '5000';

const voucherToolByType = {
  Sales: 'create-sales-voucher',
  Purchase: 'create-purchase-voucher',
  Payment: 'create-payment-voucher',
  Receipt: 'create-receipt-voucher',
  Contra: 'create-contra-voucher',
  Journal: 'create-journal-voucher',
  'Credit Note': 'create-credit-note',
  'Debit Note': 'create-debit-note'
};

function parseTsvNames(text) {
  return new Set((text || '')
    .split(/\r?\n/)
    .slice(1)
    .map(line => line.trim())
    .filter(Boolean));
}

function safeEducationalDate(date) {
  const [year, month, dayText] = date.split('-');
  const day = Number(dayText);
  const last = new Date(Number(year), Number(month), 0).getDate();
  if (day === 1 || day === 2 || day === last) return date;
  return `${year}-${month}-${day % 2 === 0 ? '02' : '01'}`;
}

function parseResult(res) {
  const text = res.content?.[0]?.text ?? '';
  try {
    return JSON.parse(text);
  } catch {
    return { ok: !res.isError, text };
  }
}

async function main() {
  const transport = new StdioClientTransport({
    command: 'node',
    args: [path.join(root, 'dist', 'index.mjs')],
    cwd: root
  });
  const client = new Client({ name: 'dataset-folder-importer', version: '1.0.0' });
  await client.connect(transport);

  async function call(name, args) {
    const res = await client.callTool({ name, arguments: args });
    return { isError: !!res.isError, result: parseResult(res), rawText: res.content?.[0]?.text ?? '' };
  }

  async function namesFor(collection, optional = false) {
    const res = await call('list-master', { targetCompany, collection });
    if (res.isError) {
      if (optional) return new Set();
      throw new Error(`Cannot list ${collection}: ${res.rawText}`);
    }
    return parseTsvNames(res.rawText);
  }

  const existing = {
    group: await namesFor('group'),
    ledger: await namesFor('ledger'),
    stockitem: await namesFor('stockitem', true),
    stockgroup: await namesFor('stockgroup', true),
    unit: await namesFor('unit', true)
  };

  const report = {
    targetCompany,
    datasetRoot,
    groups: { created: 0, skipped: 0, failed: [] },
    ledgers: { created: 0, skipped: 0, failed: [] },
    stock: { created: 0, skipped: 0, failed: [] },
    vouchers: { created: 0, failed: [], dateMapped: [] },
    datasets: []
  };

  const folders = fs.readdirSync(datasetRoot, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .map(entry => entry.name)
    .sort();

  for (const folder of folders) {
    const tallyPath = path.join(datasetRoot, folder, 'tally_import.json');
    const datasetPath = path.join(datasetRoot, folder, 'dataset.json');
    if (!fs.existsSync(tallyPath) || !fs.existsSync(datasetPath)) continue;
    const tally = JSON.parse(fs.readFileSync(tallyPath, 'utf-8'));
    const dataset = JSON.parse(fs.readFileSync(datasetPath, 'utf-8'));
    const dsReport = { id: folder, groups: 0, ledgers: 0, stock: 0, vouchers: 0, failures: 0 };

    for (const group of tally.createGroupCalls || []) {
      if (existing.group.has(group.name)) {
        report.groups.skipped++;
        continue;
      }
      const res = await call('create-group', { targetCompany, name: group.name, parent: group.parent });
      if (res.result.ok && res.result.created > 0) {
        existing.group.add(group.name);
        report.groups.created++;
        dsReport.groups++;
      } else {
        report.groups.failed.push({ dataset: folder, group, result: res.result });
        dsReport.failures++;
      }
    }

    for (const ledger of tally.createLedgerCalls || []) {
      if (existing.ledger.has(ledger.name)) {
        report.ledgers.skipped++;
        continue;
      }
      const res = await call('create-ledger', {
        targetCompany,
        name: ledger.name,
        parent: ledger.parent,
        openingBalance: ledger.openingBalance || 0
      });
      if (res.result.ok && res.result.created > 0) {
        existing.ledger.add(ledger.name);
        report.ledgers.created++;
        dsReport.ledgers++;
      } else {
        report.ledgers.failed.push({ dataset: folder, ledger, result: res.result });
        dsReport.failures++;
      }
    }

    for (const voucher of tally.createVoucherCalls || []) {
      const tool = voucher.tool;
      const date = safeEducationalDate(voucher.date);
      if (date !== voucher.date) {
        report.vouchers.dateMapped.push({ dataset: folder, voucherNumber: voucher.voucherNumber, from: voucher.date, to: date });
      }
      const res = await call(tool, {
        targetCompany,
        date,
        voucherNumber: `${folder}-${voucher.voucherNumber}`,
        narration: `${folder}: ${voucher.narration}`,
        partyLedgerName: voucher.entries[0]?.ledgerName,
        entries: voucher.entries
      });
      if (res.result.ok && res.result.created > 0) {
        report.vouchers.created++;
        dsReport.vouchers++;
      } else {
        report.vouchers.failed.push({ dataset: folder, voucher, effectiveDate: date, result: res.result });
        dsReport.failures++;
      }
    }

    // Inventory masters are attempted after accounting vouchers so disabled inventory features do not block accounting import.
    for (const item of dataset.stockItems || []) {
      const unit = item.baseUnit;
      const stockGroup = item.stockGroup;
      if (unit && !existing.unit.has(unit)) {
        const res = await call('create-unit', { targetCompany, symbol: unit, decimalPlaces: 0 });
        if (res.result.ok && res.result.created > 0) {
          existing.unit.add(unit);
          report.stock.created++;
          dsReport.stock++;
        } else {
          report.stock.failed.push({ dataset: folder, type: 'unit', unit, result: res.result });
          dsReport.failures++;
        }
      }
      if (stockGroup && !existing.stockgroup.has(stockGroup)) {
        const res = await call('create-stock-group', { targetCompany, name: stockGroup });
        if (res.result.ok && res.result.created > 0) {
          existing.stockgroup.add(stockGroup);
          report.stock.created++;
          dsReport.stock++;
        } else {
          report.stock.failed.push({ dataset: folder, type: 'stock-group', stockGroup, result: res.result });
          dsReport.failures++;
        }
      }
      if (!existing.stockitem.has(item.name)) {
        const res = await call('create-stock-item', {
          targetCompany,
          name: item.name,
          parent: stockGroup,
          baseUnit: unit
        });
        if (res.result.ok && res.result.created > 0) {
          existing.stockitem.add(item.name);
          report.stock.created++;
          dsReport.stock++;
        } else {
          report.stock.failed.push({ dataset: folder, type: 'stock-item', item, result: res.result });
          dsReport.failures++;
        }
      } else {
        report.stock.skipped++;
      }
    }

    report.datasets.push(dsReport);
    console.log(`Imported ${folder}: vouchers=${dsReport.vouchers}, ledgers=${dsReport.ledgers}, groups=${dsReport.groups}, failures=${dsReport.failures}`);
  }

  await client.close();
  const reportPath = path.join(root, 'dataset', 'tally_import_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf-8');
  console.log(JSON.stringify({
    reportPath,
    groups: report.groups,
    ledgers: report.ledgers,
    stock: report.stock,
    vouchers: {
      created: report.vouchers.created,
      failed: report.vouchers.failed.length,
      dateMapped: report.vouchers.dateMapped.length
    }
  }, null, 2));

  if (report.groups.failed.length || report.ledgers.failed.length || report.vouchers.failed.length || report.stock.failed.length) {
    process.exitCode = 2;
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});

import http from 'node:http';
import { XMLParser } from 'fast-xml-parser';

const tallyPort = parseInt(process.env.TALLY_PORT || '9000');

function escapeXml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
}

function dateToTally(value) {
    if (!value)
        return '';
    if (/^\d{8}$/.test(value))
        return value;
    if (/^\d{4}-\d{2}-\d{2}$/.test(value))
        return value.replace(/-/g, '');
    throw new Error(`Invalid date '${value}'. Expected YYYY-MM-DD.`);
}

function yesNo(value) {
    return value ? 'Yes' : 'No';
}

function amount(value) {
    const n = Number(value);
    if (!Number.isFinite(n))
        throw new Error(`Invalid amount '${value}'.`);
    return n.toFixed(2);
}

function tallyEnvelope(reportName, requestData, targetCompany) {
    const staticVariables = targetCompany
        ? `<STATICVARIABLES><SVCURRENTCOMPANY>${escapeXml(targetCompany)}</SVCURRENTCOMPANY></STATICVARIABLES>`
        : '';
    return `<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>${escapeXml(reportName)}</REPORTNAME>
        ${staticVariables}
      </REQUESTDESC>
      <REQUESTDATA>
        ${requestData}
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>`;
}

function tallyMessage(xml) {
    return `<TALLYMESSAGE xmlns:UDF="TallyUDF">${xml}</TALLYMESSAGE>`;
}

export async function postTallyXml(xml) {
    return new Promise((resolve, reject) => {
        const timeoutMs = Number(process.env.TALLY_HTTP_TIMEOUT_MS || 15000);
        let settled = false;
        const finish = (fn, value) => {
            if (settled)
                return;
            settled = true;
            clearTimeout(timer);
            fn(value);
        };
        const timer = setTimeout(() => {
            req.destroy();
            finish(reject, new Error('Tally HTTP request timed out'));
        }, timeoutMs);
        const req = http.request({
            hostname: 'localhost',
            port: tallyPort,
            path: '',
            method: 'POST',
            headers: {
                'Content-Length': Buffer.byteLength(xml, 'utf16le'),
                'Content-Type': 'text/xml;charset=utf-16'
            }
        }, (res) => {
            let data = '';
            res.setEncoding('utf16le');
            res.on('data', chunk => data += chunk.toString());
            res.on('end', () => finish(resolve, data));
            res.on('error', err => finish(reject, err));
        });
        req.on('error', err => finish(reject, err));
        req.write(xml, 'utf16le');
        req.end();
    });
}

export function parseImportResponse(xml) {
    const parser = new XMLParser({ ignoreAttributes: false, parseTagValue: true });
    const parsed = parser.parse(xml || '');
    const response = parsed?.RESPONSE || {};
    const readNumber = (name) => Number(response[name] ?? 0);
    const result = {
        created: readNumber('CREATED'),
        altered: readNumber('ALTERED'),
        deleted: readNumber('DELETED'),
        errors: readNumber('ERRORS'),
        cancelled: readNumber('CANCELLED'),
        exceptions: readNumber('EXCEPTIONS'),
        ignored: readNumber('IGNORED'),
        lastVoucherId: readNumber('LASTVCHID'),
        lastMasterId: readNumber('LASTMID'),
        raw: xml || ''
    };
    if (response.LINEERROR)
        result.lineError = Array.isArray(response.LINEERROR) ? response.LINEERROR.join('; ') : String(response.LINEERROR);
    result.ok = result.errors === 0 && result.cancelled === 0 && result.exceptions === 0;
    return result;
}

async function importXml({ reportName = 'All Masters', targetCompany, xml }) {
    const requestXml = tallyEnvelope(reportName, xml, targetCompany);
    const raw = await postTallyXml(requestXml);
    return parseImportResponse(raw);
}

export async function createCompany(args) {
    const booksFrom = dateToTally(args.booksBeginningFrom || args.financialYearFrom);
    const xml = tallyMessage(`<COMPANY NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.name)}</NAME>
  <MAILINGNAME>${escapeXml(args.mailingName || args.name)}</MAILINGNAME>
  <COUNTRYNAME>${escapeXml(args.countryName || 'India')}</COUNTRYNAME>
  ${args.stateName ? `<STATENAME>${escapeXml(args.stateName)}</STATENAME>` : ''}
  <CURRENCYNAME>${escapeXml(args.currencyName || '₹')}</CURRENCYNAME>
  <FINANCIALYEARFROM>${dateToTally(args.financialYearFrom)}</FINANCIALYEARFROM>
  <BOOKSFROM>${booksFrom}</BOOKSFROM>
</COMPANY>`);
    return importXml({ xml });
}

export async function createGroup(args) {
    const xml = tallyMessage(`<GROUP NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.name)}</NAME>
  <PARENT>${escapeXml(args.parent || 'Primary')}</PARENT>
  <ISSUBLEDGER>${yesNo(args.isSubLedger || false)}</ISSUBLEDGER>
  <ISBILLWISEON>${yesNo(args.isBillWise || false)}</ISBILLWISEON>
  <ISCOSTCENTRESON>${yesNo(args.useCostCenters || false)}</ISCOSTCENTRESON>
</GROUP>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function createLedger(args) {
    const xml = tallyMessage(`<LEDGER NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.name)}</NAME>
  <PARENT>${escapeXml(args.parent)}</PARENT>
  <ISBILLWISEON>${yesNo(args.isBillWise || false)}</ISBILLWISEON>
  <ISCOSTCENTRESON>${yesNo(args.useCostCenters || false)}</ISCOSTCENTRESON>
  <OPENINGBALANCE>${amount(args.openingBalance || 0)}</OPENINGBALANCE>
</LEDGER>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function alterLedger(args) {
    const xml = tallyMessage(`<LEDGER NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Alter">
  <NAME>${escapeXml(args.name)}</NAME>
  ${args.parent ? `<PARENT>${escapeXml(args.parent)}</PARENT>` : ''}
  ${args.isBillWise === undefined ? '' : `<ISBILLWISEON>${yesNo(args.isBillWise)}</ISBILLWISEON>`}
  ${args.useCostCenters === undefined ? '' : `<ISCOSTCENTRESON>${yesNo(args.useCostCenters)}</ISCOSTCENTRESON>`}
  ${args.openingBalance === undefined ? '' : `<OPENINGBALANCE>${amount(args.openingBalance)}</OPENINGBALANCE>`}
</LEDGER>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function createStockGroup(args) {
    const xml = tallyMessage(`<STOCKGROUP NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.name)}</NAME>
  ${args.parent ? `<PARENT>${escapeXml(args.parent)}</PARENT>` : ''}
  <ISADDABLE>${yesNo(args.isAddable !== false)}</ISADDABLE>
</STOCKGROUP>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function createUnit(args) {
    const xml = tallyMessage(`<UNIT NAME="${escapeXml(args.symbol)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.symbol)}</NAME>
  <ORIGINALNAME>${escapeXml(args.symbol)}</ORIGINALNAME>
  <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
  <DECIMALPLACES>${Number(args.decimalPlaces || 0)}</DECIMALPLACES>
</UNIT>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function createGodown(args) {
    const xml = tallyMessage(`<GODOWN NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.name)}</NAME>
  <PARENT>${escapeXml(args.parent || 'Main Location')}</PARENT>
</GODOWN>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function createCostCenter(args) {
    const xml = tallyMessage(`<COSTCENTRE NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.name)}</NAME>
  ${args.parent ? `<PARENT>${escapeXml(args.parent)}</PARENT>` : ''}
  <CATEGORY>${escapeXml(args.category || 'Primary Cost Category')}</CATEGORY>
</COSTCENTRE>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function createCurrency(args) {
    const xml = tallyMessage(`<CURRENCY NAME="${escapeXml(args.symbol)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.symbol)}</NAME>
  <MAILINGNAME>${escapeXml(args.formalName || args.symbol)}</MAILINGNAME>
  <ORIGINALNAME>${escapeXml(args.symbol)}</ORIGINALNAME>
  <DECIMALPLACES>${Number(args.decimalPlaces || 2)}</DECIMALPLACES>
</CURRENCY>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function createStockItem(args) {
    const xml = tallyMessage(`<STOCKITEM NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Create">
  <NAME>${escapeXml(args.name)}</NAME>
  ${args.parent ? `<PARENT>${escapeXml(args.parent)}</PARENT>` : ''}
  <BASEUNITS>${escapeXml(args.baseUnit)}</BASEUNITS>
  ${args.openingQuantity === undefined ? '' : `<OPENINGBALANCE>${Number(args.openingQuantity)} ${escapeXml(args.baseUnit)}</OPENINGBALANCE>`}
  ${args.openingValue === undefined ? '' : `<OPENINGVALUE>${amount(args.openingValue)}</OPENINGVALUE>`}
</STOCKITEM>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function alterStockItem(args) {
    const xml = tallyMessage(`<STOCKITEM NAME="${escapeXml(args.name)}" RESERVEDNAME="" ACTION="Alter">
  <NAME>${escapeXml(args.name)}</NAME>
  ${args.parent ? `<PARENT>${escapeXml(args.parent)}</PARENT>` : ''}
  ${args.baseUnit ? `<BASEUNITS>${escapeXml(args.baseUnit)}</BASEUNITS>` : ''}
  ${args.openingQuantity === undefined ? '' : `<OPENINGBALANCE>${Number(args.openingQuantity)} ${escapeXml(args.baseUnit || '')}</OPENINGBALANCE>`}
  ${args.openingValue === undefined ? '' : `<OPENINGVALUE>${amount(args.openingValue)}</OPENINGVALUE>`}
</STOCKITEM>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

function ledgerEntryXml(entry) {
    const entryAmount = Number(entry.amount);
    if (!Number.isFinite(entryAmount))
        throw new Error(`Invalid ledger entry amount for '${entry.ledgerName}'.`);
    return `<LEDGERENTRIES.LIST>
  <LEDGERNAME>${escapeXml(entry.ledgerName)}</LEDGERNAME>
  <ISDEEMEDPOSITIVE>${yesNo(entryAmount < 0)}</ISDEEMEDPOSITIVE>
  <AMOUNT>${amount(entryAmount)}</AMOUNT>
  ${entry.billName ? `<BILLALLOCATIONS.LIST><NAME>${escapeXml(entry.billName)}</NAME><BILLTYPE>${escapeXml(entry.billType || 'New Ref')}</BILLTYPE><AMOUNT>${amount(entryAmount)}</AMOUNT></BILLALLOCATIONS.LIST>` : ''}
</LEDGERENTRIES.LIST>`;
}

function voucherXml(args, voucherType) {
    const entries = args.entries || [];
    if (entries.length < 2)
        throw new Error('A voucher requires at least two ledger entries.');
    const total = entries.reduce((sum, entry) => sum + Number(entry.amount), 0);
    if (Math.abs(total) > 0.005)
        throw new Error(`Voucher entries must balance to zero. Current total is ${total.toFixed(2)}.`);
    const partyLedger = args.partyLedgerName || entries[0]?.ledgerName || '';
    const tallyDate = dateToTally(args.date);
    return tallyMessage(`<VOUCHER VCHTYPE="${escapeXml(voucherType)}" ACTION="Create" OBJVIEW="Accounting Voucher View">
  <DATE>${tallyDate}</DATE>
  <EFFECTIVEDATE>${tallyDate}</EFFECTIVEDATE>
  <VOUCHERTYPENAME>${escapeXml(voucherType)}</VOUCHERTYPENAME>
  ${args.voucherNumber ? `<VOUCHERNUMBER>${escapeXml(args.voucherNumber)}</VOUCHERNUMBER>` : ''}
  ${partyLedger ? `<PARTYLEDGERNAME>${escapeXml(partyLedger)}</PARTYLEDGERNAME>` : ''}
  <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
  <ISINVOICE>No</ISINVOICE>
  ${args.narration ? `<NARRATION>${escapeXml(args.narration)}</NARRATION>` : ''}
  ${entries.map(ledgerEntryXml).join('\n  ')}
</VOUCHER>`);
}

export async function createVoucher(args, voucherType) {
    return importXml({ targetCompany: args.targetCompany, xml: voucherXml(args, voucherType) });
}

export async function alterVoucher(args) {
    const xml = voucherXml(args, args.voucherType).replace('ACTION="Create"', 'ACTION="Alter"');
    return importXml({ targetCompany: args.targetCompany, xml });
}

export async function deleteVoucher(args) {
    const xml = tallyMessage(`<VOUCHER VCHTYPE="${escapeXml(args.voucherType)}" ACTION="Delete">
  <DATE>${dateToTally(args.date)}</DATE>
  <VOUCHERTYPENAME>${escapeXml(args.voucherType)}</VOUCHERTYPENAME>
  <VOUCHERNUMBER>${escapeXml(args.voucherNumber)}</VOUCHERNUMBER>
</VOUCHER>`);
    return importXml({ targetCompany: args.targetCompany, xml });
}

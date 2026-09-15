// Fixture-only browser regression. Never contacts a live API or writes to a database.
// Run: node scripts/test_data_explorer_ui.cjs
// --screenshots-only skips regression groups; --live reads deployed static assets only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
let chromium;
try { ({ chromium } = require('playwright')); } catch {
  ({ chromium } = require(path.join(process.env.USERPROFILE || '', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')));
}

const root = path.resolve(__dirname, '..');
const live = process.argv.includes('--live');
const screenshotsOnly = process.argv.includes('--screenshots-only');
const origin = live ? 'https://app.cellaidata.com' : 'https://data-explorer.fixture';
const token = 'fixture-admin-only';
const tokenKey = 'cellx-workflow-management-token';
const columns = [
  { name: 'id', type: 'int', primary_key: true, nullable: false, masked: false },
  { name: 'Records', type: 'varchar', primary_key: false, nullable: false, masked: false },
  { name: 'Schema', type: 'varchar', primary_key: false, nullable: true, masked: false },
  { name: 'notes', type: 'text', primary_key: false, nullable: true, masked: true },
  ...Array.from({ length: 7 }, (_, i) => ({ name: `metric_${i}`, type: 'int', primary_key: false, nullable: true, masked: false })),
];
const company = { id: 'fixture-company', name: 'Records' };
const agent = { id: 'fixture-agent', name: 'Schema', state: 'draft', use_state: 'planned', company_id: company.id };
const actual = { name: 'Records', physical_exists: true, association: 'registry_planned', company_id: company.id, company_name: company.name, agents: [agent], columns,
  relations: [{ column: 'id', referenced_table: 'OtherTable', referenced_column: 'id' }] };
const other = { ...actual, name: 'OtherTable', association: 'unlinked', company_id: null, company_name: null, agents: [], relations: [] };
const planned = { name: 'PlannedTable', state: 'planned', physical_exists: false, company_id: company.id, company_name: company.name, agents: [agent] };
const catalog = { ok: true, read_only: true, registry_available: true, companies: [company], agents: [agent], tables: [actual, other],
  planned_tables: [{ name: actual.name, state: 'planned', physical_exists: true, company_id: company.id, company_name: company.name, agents: [agent] }, planned] };
const records = Array.from({ length: 125 }, (_, index) => ({
  id: index + 1,
  Records: index < 3 ? `needle ${index}` : index === 3 ? '<img src=x onerror=alert(1)>' : 'Records',
  Schema: index === 0 ? '[REDACTED]' : index === 1 ? null : index === 2 ? '{"Records":"Schema"}' : 'Schema',
  notes: '[REDACTED]',
  ...Object.fromEntries(Array.from({ length: 7 }, (_, i) => [`metric_${i}`, index + i])),
}));

async function fixture(browser, viewport = { width: 1440, height: 960 }) {
  const context = await browser.newContext({ viewport, locale: 'en-US', serviceWorkers: 'block' });
  const page = await context.newPage();
  const state = { requests: [], errors: [], unexpected: [], fail: null, catalog, holdRows: null };
  page.on('pageerror', error => state.errors.push(error.message));
  page.on('response', response => {
    const url = new URL(response.url());
    if (live && url.origin === origin && url.pathname.startsWith('/data/') && response.status() !== 200) state.errors.push(`Static asset ${url.pathname}: ${response.status()}`);
  });
  page.on('dialog', async dialog => { state.errors.push(`Unexpected dialog: ${dialog.type()}`); await dialog.dismiss(); });
  await page.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== origin) { state.unexpected.push(url.origin); return route.abort(); }
    if (url.pathname === '/ext-api' || url.pathname.startsWith('/ext-api/')) {
      const operation = url.pathname.replace('/ext-api/data-explorer/', '');
      state.requests.push({ operation, method: request.method(), headers: request.headers(), url });
      const keys = operation === 'rows' ? ['table', 'page', 'page_size', 'search', 'sort', 'direction', 'filters'] : operation === 'table' ? ['table'] : [];
      assert.equal(request.method(), 'GET', 'Explorer must remain read only');
      assert([...url.searchParams.keys()].every(key => keys.includes(key)), 'Unexpected API query field');
      assert(!request.url().includes(token), 'Token leaked into request URL');
      if (request.headers()['x-workflow-admin-token'] !== token) return route.fulfill({ status: 401, json: { ok: false, code: 'admin_required' } });
      if (state.fail?.operation === operation) {
        if (state.fail.malformed) return route.fulfill({ status: 200, contentType: 'application/json', body: '{not-json' });
        return route.fulfill({ status: state.fail.status, json: { ok: false, code: state.fail.code } });
      }
      if (operation === 'status') return route.fulfill({ json: { ok: true, read_only: true, admin_only: true, tenant_access_supported: false, database_available: true, registry_available: true } });
      if (operation === 'catalog') return route.fulfill({ json: state.catalog });
      const table = [actual, other].find(item => item.name === url.searchParams.get('table'));
      if (!table) return route.fulfill({ status: 404, json: { ok: false, code: 'table_not_found' } });
      if (operation === 'table') return route.fulfill({ json: { ok: true, table } });
      if (operation === 'rows') {
        if (state.holdRows) await state.holdRows;
        const pageNumber = Number(url.searchParams.get('page') || 1);
        const pageSize = Number(url.searchParams.get('page_size') || 50);
        const search = url.searchParams.get('search') || '';
        const sort = url.searchParams.get('sort') || 'id';
        const direction = url.searchParams.get('direction') || 'asc';
        assert(pageNumber >= 1 && pageSize <= 100 && pageSize >= 1, 'Pagination violates backend bounds');
        assert(columns.some(column => column.name === sort && !column.masked), 'Sorting a masked/unknown column');
        let rows = records.filter(row => !search || ['Records', 'Schema'].some(key => String(row[key] ?? '').includes(search)));
        rows = [...rows].sort((a, b) => (typeof a[sort] === 'number' ? a[sort] - b[sort] : String(a[sort]).localeCompare(String(b[sort]))) * (direction === 'desc' ? -1 : 1));
        const offset = (pageNumber - 1) * pageSize;
        return route.fulfill({ json: { ok: true, read_only: true, table: table.name, columns, rows: rows.slice(offset, offset + pageSize),
          page: pageNumber, page_size: pageSize, has_more: offset + pageSize < rows.length, sort, direction } });
      }
      throw new Error(`Unexpected API endpoint: ${url.pathname}`);
    }
    // No arbitrary network passthrough: only GETs for this app's static bundle.
    const staticPath = /^\/data\/(?:[A-Za-z0-9_./-]+\.(?:html|js|css|png|svg|ico|woff2?))?$/;
    if (request.method() !== 'GET' || !staticPath.test(url.pathname)) {
      state.unexpected.push(url.pathname); return route.abort();
    }
    if (live) {
      assert(!request.headers()['x-workflow-admin-token'], 'Token must not be sent to static assets');
      return route.continue();
    }
    const name = url.pathname.replace(/^\/data\/?/, '') || 'index.html';
    const file = path.resolve(root, 'cellx-data-ui', name);
    assert(file.startsWith(path.join(root, 'cellx-data-ui') + path.sep), 'Unexpected asset path');
    const shared = ['i18n.js', 'i18n.css'].includes(name) ? path.join(root, 'shared', name) : null;
    const asset = fs.existsSync(file) ? file : shared;
    if (!asset || !fs.existsSync(asset)) return route.fulfill({ status: 404, body: '' });
    const contentType = name.endsWith('.js') ? 'application/javascript' : name.endsWith('.css') ? 'text/css' : name.endsWith('.png') ? 'image/png' : 'text/html';
    return route.fulfill({ contentType, body: fs.readFileSync(asset) });
  });
  await page.goto(origin + '/data/?lang=en');
  await page.waitForFunction(() => document.getElementById('connectionStatus').textContent.length > 0);
  return { page, state, context };
}

async function connect(page, value = token) {
  await page.locator('#adminToken').fill(value);
  await page.locator('#connectionForm button[type=submit]').click();
  await page.waitForFunction(() => document.getElementById('tableList').getAttribute('aria-busy') !== 'true');
}
function choice(page, name) { return page.locator('.table-choice').filter({ has: page.locator('.table-label', { hasText: new RegExp(`^${name}$`) }) }); }
async function openRecords(page) {
  await choice(page, 'Records').click();
  await page.waitForFunction(() => document.querySelectorAll('#recordsTable tbody tr').length > 0);
}
async function settled(page) { await page.waitForFunction(() => document.getElementById('recordsTable').getAttribute('aria-busy') === 'false'); }
async function apply(page) { await page.locator('#recordControls button[type=submit]').click(); await settled(page); }

async function captureScreenshots(browser) {
  const current = await fixture(browser);
  try {
    const { page, state } = current;
    page.setDefaultTimeout(6000);
    await connect(page); await openRecords(page); await settled(page);
    const output = path.join(root, 'outputs');
    fs.mkdirSync(output, { recursive: true });
    for (const [width, height, language] of [[1440, 960, 'en'], [390, 844, 'zh-CN']]) {
      await page.setViewportSize({ width, height });
      await page.locator('[data-language-picker]').selectOption(language);
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all([...document.images].map(image => image.decode().catch(() => {})));
        document.querySelectorAll('.table-scroll').forEach(element => { element.scrollLeft = 0; element.scrollTop = 0; });
        window.scrollTo(0, 0);
        if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
      });
      assert(await page.locator('.brand img').evaluate(image => image.complete && image.naturalWidth > 0), 'Brand image did not load');
      assert(await page.locator('#recordsPanel .table-scroll').evaluate(el => el.offsetWidth - el.clientWidth >= 14 && el.offsetHeight - el.clientHeight >= 14), 'Scrollbars must reserve visible space on both axes');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Page overflows viewport');
      const file = path.join(output, `data-explorer-${width}.png`);
      await page.screenshot({ path: file, fullPage: true, animations: 'disabled', caret: 'hide' });
      await page.locator('#recordsPanel .table-scroll').screenshot({ path: path.join(output, `data-explorer-table-${width}.png`) });
      console.log(`CAPTURE: ${path.relative(root, file)} (${language}, ${live ? 'deployed' : 'local'} static assets; mocked API)`);
    }
    assert.deepEqual(state.errors, []); assert.deepEqual(state.unexpected, []);
  } finally { await current.context.close(); }
}

const tests = [
  ['admin gating, session token, rejected credentials and disconnect', async ({ page, state }) => {
    assert.equal(state.requests.length, 0);
    await page.locator('#refreshCatalog').click();
    assert.equal(state.requests.length, 0);
    await connect(page, 'fixture-invalid');
    assert.match(await page.locator('#catalogStatus').innerText(), /admin_required/);
    assert.equal(await page.locator('.table-choice').count(), 0);
    await connect(page);
    await openRecords(page);
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), tokenKey), token);
    assert.equal(await page.evaluate(key => localStorage.getItem(key), tokenKey), null);
    await page.reload();
    await page.waitForFunction(() => document.querySelectorAll('.table-choice').length === 3);
    await page.locator('#disconnect').click();
    assert.equal(await page.evaluate(key => sessionStorage.getItem(key), tokenKey), null);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 0);
    assert.equal(await page.locator('.table-choice').count(), 0);
    const count = state.requests.length;
    await page.locator('#refreshCatalog').click();
    assert.equal(state.requests.length, count);
  }],
  ['physical/planned distinction, deduplication and company/agent/table filtering', async ({ page, state }) => {
    await connect(page);
    assert.equal(await choice(page, 'Records').count(), 1);
    assert.equal(await choice(page, 'Records').locator('.table-state').innerText(), 'Planned + actual');
    assert.equal(await choice(page, 'OtherTable').locator('.table-state').innerText(), 'Actual');
    assert.equal(await page.locator('.company-group').count(), 2);
    assert.equal(await page.locator('.company-group > summary [data-i18n-skip]').first().innerText(), company.name);
    const count = state.requests.length;
    await choice(page, 'PlannedTable').click();
    assert.match(await page.locator('#recordsStatus').innerText(), /No physical table/);
    assert.equal(state.requests.length, count, 'Planned-only table must not request metadata or rows');
    assert(await page.locator('#recordSearch').isDisabled());
    await page.locator('#tableFilter').fill('Schema');
    assert.equal(await page.locator('.table-choice').count(), 2);
    await page.locator('#tableFilter').fill(company.name);
    assert.equal(await page.locator('.table-choice').count(), 2, 'Company search must include its planned table');
    await page.locator('#tableFilter').fill('no-such-table');
    assert.equal(await page.locator('.table-choice').count(), 0);
    assert.match(await page.locator('#tableList').innerText(), /No matching tables/);
  }],
  ['sorting, search, pagination and empty records', async ({ page, state }) => {
    await connect(page); await openRecords(page);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 50);
    assert(await page.locator('#previousPage').isDisabled());
    await page.locator('#nextPage').click(); await settled(page);
    assert.match(await page.locator('#pageInfo').innerText(), /Page 2/);
    assert.equal(await page.locator('#recordsTable tbody tr').first().locator('td').first().innerText(), '51');
    await page.locator('#nextPage').click(); await settled(page);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 25);
    assert(await page.locator('#nextPage').isDisabled());
    await page.locator('#previousPage').click(); await settled(page);
    assert.match(await page.locator('#pageInfo').innerText(), /Page 2/);
    await page.locator('#pageSize').selectOption('25'); await settled(page);
    assert.match(await page.locator('#pageInfo').innerText(), /Page 1/);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 25);
    await page.locator('#sortColumn').selectOption('id');
    await page.locator('#sortDirection').selectOption('desc'); await apply(page);
    assert.equal(await page.locator('#recordsTable tbody tr').first().locator('td').first().innerText(), '125');
    await page.locator('#recordSearch').fill('needle'); await apply(page);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 3);
    assert(await page.locator('#nextPage').isDisabled());
    const query = state.requests.filter(item => item.operation === 'rows').at(-1).url.searchParams;
    assert.equal(query.get('search'), 'needle'); assert.equal(query.get('direction'), 'desc'); assert.equal(query.get('page'), '1');
    await page.locator('#recordSearch').fill('no-such-record'); await apply(page);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 0);
    assert.match(await page.locator('#recordsStatus').innerText(), /No matching records/);
  }],
  ['schema/relations, masked sorting and unmodified data across languages', async ({ page }) => {
    await connect(page); await openRecords(page);
    assert.deepEqual(await page.locator('#recordsTable th').allTextContents(), columns.map(column => column.name));
    assert.equal(await page.locator('#sortColumn option[value=notes]').count(), 0);
    assert.equal(await page.locator('#recordsTable img').count(), 0, 'Record HTML must remain text');
    assert.match(await page.locator('#recordsTable tbody').innerText(), /<img src=x onerror=alert\(1\)>/);
    assert.equal(await page.locator('#recordsTable tbody tr').first().locator('td').nth(2).innerText(), '[REDACTED]', 'Unmasked data must remain literal');
    assert.equal(await page.locator('#recordsTable .protected-value').count(), 50);
    assert.equal(await page.locator('#recordsTable .protected-value').first().getAttribute('title'), '[REDACTED]');
    const values = await page.locator('#recordsTable [data-i18n-skip]').allTextContents();
    const schemaNames = await page.locator('#schemaTable tbody tr td:first-child').allTextContents();
    const relation = await page.locator('#relationsTable tbody').textContent();
    await page.locator('#recordSearch').fill('unsaved query');
    for (const language of ['zh-CN', 'en']) {
      await page.locator('[data-language-picker]').selectOption(language);
      assert.deepEqual(await page.locator('#recordsTable [data-i18n-skip]').allTextContents(), values);
      assert.deepEqual(await page.locator('#recordsTable th').allTextContents(), columns.map(column => column.name));
      assert.deepEqual(await page.locator('#schemaTable tbody tr td:first-child').allTextContents(), schemaNames);
      assert.equal(await page.locator('#relationsTable tbody').textContent(), relation);
      assert.equal(await page.locator('#recordSearch').inputValue(), 'unsaved query');
      assert.equal(await page.locator('#tableName').textContent(), 'Records');
      assert.equal(await page.locator('.agent-group summary [data-i18n-skip]').first().textContent(), 'Schema');
      assert.equal(await page.locator('.company-group > summary [data-i18n-skip]').first().textContent(), company.name);
      assert.equal(await page.locator('#recordsTable .protected-value').first().innerText(), language === 'en' ? 'Protected' : '\u53d7\u4fdd\u62a4');
    }
    await page.locator('#schemaTab').click(); assert(await page.locator('#schemaPanel').isVisible());
    await page.locator('#schemaTab').press('ArrowRight'); assert(await page.locator('#relationsPanel').isVisible());
  }],
  ['loading, database errors, malformed response and retry', async ({ page, state }) => {
    await connect(page);
    let release; state.holdRows = new Promise(resolve => { release = resolve; });
    await choice(page, 'Records').click();
    await page.waitForFunction(() => document.getElementById('recordsTable').getAttribute('aria-busy') === 'true');
    assert.match(await page.locator('#recordsStatus').innerText(), /Loading records/);
    assert(await page.locator('#nextPage').isDisabled());
    assert(await page.locator('#recordSearch').isDisabled());
    release(); state.holdRows = null; await settled(page);
    state.fail = { operation: 'rows', status: 503, code: 'database_unavailable' };
    await page.locator('#refreshTable').click();
    await page.waitForFunction(() => document.getElementById('recordsStatus').dataset.tone === 'error');
    assert.match(await page.locator('#recordsStatus').innerText(), /database_unavailable/);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 0);
    await page.locator('[data-language-picker]').selectOption('zh-CN');
    assert.match(await page.locator('#recordsStatus').innerText(), /database_unavailable/);
    assert(!/Database service unavailable/.test(await page.locator('#recordsStatus').innerText()));
    state.fail = { operation: 'rows', malformed: true };
    await page.locator('#refreshTable').click();
    await page.waitForFunction(() => document.getElementById('recordsStatus').dataset.tone === 'error');
    state.fail = null; await page.locator('#refreshTable').click();
    await page.waitForFunction(() => document.querySelectorAll('#recordsTable tbody tr').length === 50);
  }],
  ['empty catalog, registry unavailable and auth expiry', async ({ page, state }) => {
    state.catalog = { ...catalog, tables: [], planned_tables: [] }; await connect(page);
    assert.match(await page.locator('#catalogStatus').innerText(), /No tables available/);
    state.catalog = { ...catalog, registry_available: false, tables: [other], planned_tables: [] };
    await connect(page); assert.match(await page.locator('#catalogStatus').innerText(), /Registry unavailable/);
    state.fail = { operation: 'catalog', status: 403, code: 'admin_required' };
    await connect(page); assert.equal(await page.locator('.table-choice').count(), 0);
    assert.match(await page.locator('#catalogStatus').innerText(), /admin_required/);
  }],
  ['disconnect cancels late responses', async ({ page, state }) => {
    await connect(page);
    let release; state.holdRows = new Promise(resolve => { release = resolve; });
    await choice(page, 'Records').click();
    await page.waitForFunction(() => document.getElementById('recordsTable').getAttribute('aria-busy') === 'true');
    await page.locator('#disconnect').click(); release(); state.holdRows = null;
    await page.waitForTimeout(100);
    assert.equal(await page.locator('#recordsTable tbody tr').count(), 0);
    assert.equal(await page.locator('.table-choice').count(), 0);
    assert(await page.locator('#tableDetail').isHidden());
  }],
  ['mobile table scrolling and page containment in both languages', async ({ page }) => {
    await connect(page); await openRecords(page);
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      for (const language of ['en', 'zh-CN']) {
        await page.locator('[data-language-picker]').selectOption(language);
        const geometry = await page.locator('#recordsPanel .table-scroll').evaluate(element => {
          element.scrollLeft = element.scrollWidth;
          return { overflow: element.scrollWidth > element.clientWidth, moved: element.scrollLeft > 0,
            pageFits: document.documentElement.scrollWidth <= window.innerWidth + 1 };
        });
        assert.deepEqual(geometry, { overflow: true, moved: true, pageFits: true }, `${width}px ${language}`);
      }
    }
  }],
];

(async () => {
  if (!live) for (const file of ['app.js', 'index.html', 'i18n-zh.js']) assert(fs.existsSync(path.join(root, 'cellx-data-ui', file)), `Frontend not ready: ${file}`);
  const chrome = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined);
  const browser = await chromium.launch({ headless: true, ignoreDefaultArgs: ['--hide-scrollbars'], ...(chrome ? { executablePath: chrome } : {}) });
  let failures = 0;
  try {
    for (const [name, run] of screenshotsOnly ? [] : tests) {
      let current;
      try {
        current = await fixture(browser); current.page.setDefaultTimeout(6000);
        await run(current);
        assert.deepEqual(current.state.errors, []); assert.deepEqual(current.state.unexpected, []);
        console.log(`PASS: ${name}`);
      } catch (error) { failures++; console.error(`FAIL: ${name}\n${error.stack}`); }
      finally {
        await current?.page.unrouteAll({ behavior: 'wait' });
        await current?.context.close();
      }
    }
    await captureScreenshots(browser);
  } finally { await browser.close(); }
  if (!screenshotsOnly) console.log(`${tests.length - failures}/${tests.length} fixture-only Data Explorer checks passed.`);
  process.exitCode = failures ? 1 : 0;
})().catch(error => { console.error(error); process.exitCode = 1; });

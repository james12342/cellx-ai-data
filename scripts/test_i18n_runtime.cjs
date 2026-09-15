const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

let chromium;
try { ({ chromium } = require('playwright')); }
catch {
  ({ chromium } = require(process.env.PLAYWRIGHT_MODULE ||
    'C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
}
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'shared/i18n.js'), 'utf8');
const key = 'cell-ai-data-language';
const dictionary = { Status: '\u72b6\u6001', Title: '\u6807\u9898', 'Hello {name}': '\u4f60\u597d {name}' };
const html = `<!doctype html><html><head><meta charset="utf-8"></head><body>
  <select data-language-picker><option value="en">English</option><option value="zh-CN">Chinese</option></select>
  <span id="status" data-i18n="Status">Status</span>
  <input id="record" value="Status Login user content">
  <div id="raw">Status Login user content</div>
  <div data-i18n-skip><span id="skipped" data-i18n="Status">User caption</span></div>
  <script src="/i18n.js"></script><script>CellI18n.register(${JSON.stringify(dictionary)});</script>
  </body></html>`;

let browser;
async function fixture(options = {}) {
  const context = await browser.newContext({ locale: options.locale || 'en-US', timezoneId: 'UTC' });
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (!/^(?:www\.|app\.)?cellaidata\.com$/.test(url.hostname)) return route.abort();
    return route.fulfill({ contentType: url.pathname === '/i18n.js' ? 'application/javascript' : 'text/html',
      body: url.pathname === '/i18n.js' ? source : html });
  });
  if (options.cookie !== undefined) await context.addCookies([
    { name: key, value: options.cookie, domain: '.cellaidata.com', path: '/', secure: true, sameSite: 'Lax' },
  ]);
  await context.addInitScript(({ key, local, blocked }) => {
    if (local !== undefined) localStorage.setItem(key, local);
    if (blocked === 'getter') Object.defineProperty(window, 'localStorage', {
      get() { throw new DOMException('Blocked localStorage getter', 'SecurityError'); },
    });
    if (blocked === 'methods') {
      Storage.prototype.getItem = () => { throw new DOMException('Blocked read', 'SecurityError'); };
      Storage.prototype.setItem = () => { throw new DOMException('Blocked write', 'SecurityError'); };
    }
    if (blocked) Object.defineProperty(document, 'cookie', {
      get() { throw new DOMException('Blocked cookie getter', 'SecurityError'); },
      set() { throw new DOMException('Blocked cookie setter', 'SecurityError'); },
    });
  }, { key, local: options.local, blocked: options.blocked });
  const errors = [];
  async function open(url = options.url || 'https://app.cellaidata.com/data/') {
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await page.waitForFunction(() => !!window.CellI18n);
    return page;
  }
  try { return { context, errors, open, page: await open() }; }
  catch (error) { await context.close(); throw error; }
}
async function settle(page) {
  // Yield past observer delivery rather than using arbitrary wall-clock sleeps.
  await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 0)));
}
const tests = [];
function test(name, run) { tests.push({ name, run }); }
async function withFixture(options, run) {
  const f = await fixture(options);
  try { await run(f); assert.deepEqual(f.errors, [], 'Unexpected browser errors'); }
  finally { await f.context.close(); }
}

test('startup priority: query > cookie > local storage > browser locale', async () => {
  const cases = [
    { query: 'en', cookie: 'zh-CN', local: 'zh-CN', locale: 'zh-CN', expected: 'en' },
    { query: 'zh-CN', cookie: 'en', local: 'en', expected: 'zh-CN' },
    { query: 'invalid', cookie: 'zh-CN', local: 'en', expected: 'zh-CN' },
    { cookie: 'invalid', local: 'zh-CN', expected: 'zh-CN' },
    { cookie: 'en', local: 'zh-CN', locale: 'zh-CN', expected: 'en' },
    { locale: 'zh-TW', expected: 'zh-CN' },
    { locale: 'fr-FR', expected: 'en' },
  ];
  for (const scenario of cases) await withFixture({ ...scenario,
    url: 'https://app.cellaidata.com/data/' + (scenario.query ? '?lang=' + scenario.query : ''),
  }, async ({ page }) => {
    assert.equal(await page.evaluate(() => CellI18n.lang), scenario.expected, JSON.stringify(scenario));
    assert.equal(await page.locator('[data-language-picker]').inputValue(), scenario.expected);
  });
});

test('stale text updates remove both annotations; new source and params remain authoritative', () =>
  withFixture({}, async ({ page }) => {
    for (const mode of ['childList', 'characterData', 'unrelatedAttribute']) {
      await page.evaluate(() => {
        const el = document.getElementById('status');
        el.setAttribute('data-agent-i18n', '');
        CellI18n.text(el, 'Status');
      });
      await settle(page);
      await page.evaluate(mode => {
        const el = document.getElementById('status');
        if (mode === 'characterData') el.firstChild.data = 'User replacement';
        else el.textContent = 'User replacement';
        if (mode === 'unrelatedAttribute') el.setAttribute('data-i18n-title', 'Title');
      }, mode);
      await settle(page);
      assert.deepEqual(await page.locator('#status').evaluate(el => [el.textContent,
        el.hasAttribute('data-i18n'), el.hasAttribute('data-agent-i18n')]), ['User replacement', false, false], mode);
      await page.evaluate(() => CellI18n.setLanguage('zh-CN'));
      assert.equal(await page.locator('#status').textContent(), 'User replacement');
    }
    await page.evaluate(() => {
      const el = document.getElementById('status');
      el.textContent = 'Pending';
      el.setAttribute('data-i18n', 'Hello {name}');
      el.setAttribute('data-i18n-params', JSON.stringify({ name: 'Alice' }));
    });
    await settle(page);
    assert.equal(await page.locator('#status').textContent(), '\u4f60\u597d Alice');
    await page.evaluate(() => {
      const el = document.getElementById('status');
      el.textContent = 'Pending';
      el.setAttribute('data-i18n-params', JSON.stringify({ name: 'Bob' }));
    });
    await settle(page);
    assert.equal(await page.locator('#status').textContent(), '\u4f60\u597d Bob');
    assert.equal(await page.locator('#record').inputValue(), 'Status Login user content');
    assert.equal(await page.locator('#raw').textContent(), 'Status Login user content');
    assert.equal(await page.locator('#skipped').textContent(), 'User caption');
  }));

test('null, scalar, array and malformed params do not stop subsequent rendering', () =>
  withFixture({}, async ({ page }) => {
    for (const params of ['null', '[]', '3', '"text"', '{bad']) {
      await page.evaluate(params => {
        const el = document.createElement('span');
        el.setAttribute('data-i18n', 'Hello {name}');
        el.setAttribute('data-i18n-params', params);
        document.body.append(el);
      }, params);
      await settle(page);
    }
    assert.equal(await page.evaluate(() => CellI18n.t('Hello {name}', null)), 'Hello {name}');
    await page.evaluate(() => CellI18n.setLanguage('zh-CN'));
    assert.equal(await page.locator('#status').textContent(), dictionary.Status);
  }));

test('observer reconnects after an unexpected render exception', () =>
  withFixture({}, async ({ page, errors }) => {
    await page.evaluate(() => {
      const el = document.createElement('span');
      el.querySelectorAll = () => { throw new Error('Intentional observer recovery probe'); };
      document.body.append(el);
    });
    await settle(page);
    assert.deepEqual(errors.splice(0), ['Intentional observer recovery probe']);
    await page.evaluate(() => {
      const el = document.createElement('span');
      el.id = 'after-error';
      el.setAttribute('data-i18n', 'Status');
      document.body.append(el);
    });
    await settle(page);
    assert.equal(await page.locator('#after-error').textContent(), 'Status');
  }));

test('date formatting preserves missing/invalid values and supports granular options', () =>
  withFixture({}, async ({ page }) => {
    const result = await page.evaluate(() => {
      const date = '2026-09-14T12:34:56.789Z';
      const options = [{ timeZoneName: 'short' }, { era: 'short' }, { fractionalSecondDigits: 3 },
        { dayPeriod: 'short' }, { year: 'numeric' }];
      return { missing: [null, undefined, ''].map(x => CellI18n.formatDate(x)),
        invalid: CellI18n.formatDate('not-a-date'),
        fallback: CellI18n.formatDate(date, { timeZone: 'not-a-zone' }),
        granular: options.map(o => CellI18n.formatDate(date, o) === new Intl.DateTimeFormat('en-US', o).format(new Date(date))) };
    });
    assert.deepEqual(result, { missing: ['', '', ''], invalid: 'not-a-date',
      fallback: '2026-09-14T12:34:56.789Z', granular: [true, true, true, true, true] });
  }));

test('dynamic /data links propagate locale and unsafe destinations stay unchanged', () =>
  withFixture({}, async ({ page }) => {
    const hrefs = ['https://evil.example/data/', 'https://app.cellaidata.com.evil.example/data/',
      'javascript:void(0)', 'mailto:test@example.com', '#record', '/ext-api/data-explorer/rows'];
    await page.evaluate(hrefs => {
      for (const [i, href] of hrefs.entries()) {
        const a = document.createElement('a'); a.id = 'link-' + i; a.setAttribute('href', href); document.body.append(a);
      }
      for (const attribute of ['download', 'data-i18n-skip']) {
        const a = document.createElement('a'); a.id = attribute; a.href = '/data/'; a.setAttribute(attribute, ''); document.body.append(a);
      }
      CellI18n.setLanguage('zh-CN');
    }, hrefs);
    await settle(page);
    for (const [i, href] of hrefs.entries()) assert.equal(await page.locator('#link-' + i).getAttribute('href'), href);
    for (const id of ['download', 'data-i18n-skip']) assert.equal(await page.locator('#' + id).getAttribute('href'), '/data/');
    await page.locator('#link-0').evaluate(a => { a.href = 'https://www.cellaidata.com/data/?keep=yes#table'; });
    await page.waitForFunction(() => document.getElementById('link-0').href.includes('lang=zh-CN'));
    assert.equal(await page.locator('#link-0').getAttribute('href'), 'https://www.cellaidata.com/data/?keep=yes&lang=zh-CN#table');
  }));

test('real same-origin cross-tab storage event refreshes UI, URL and listeners', () =>
  withFixture({}, async ({ page, open }) => {
    const other = await open('https://app.cellaidata.com/data/?lang=en&keep=yes#table');
    await other.evaluate(() => {
      window.languageEvents = [];
      window.addEventListener('cell-language-change', e => languageEvents.push(e.detail.language));
    });
    await page.evaluate(() => CellI18n.setLanguage('zh-CN'));
    await other.waitForFunction(() => CellI18n.lang === 'zh-CN' && languageEvents.includes('zh-CN'));
    assert.equal(await other.locator('#status').textContent(), dictionary.Status);
    assert.equal(new URL(other.url()).searchParams.get('lang'), 'zh-CN');
    assert.equal(new URL(other.url()).searchParams.get('keep'), 'yes');
    await other.reload();
    assert.equal(await other.evaluate(() => CellI18n.lang), 'zh-CN');
  }));

test('cross-origin cookie sync on pageshow notifies listeners', () =>
  withFixture({}, async ({ page, open }) => {
    const other = await open('https://www.cellaidata.com/data/?lang=en');
    await other.evaluate(() => {
      window.languageEvents = [];
      window.addEventListener('cell-language-change', e => languageEvents.push(e.detail.language));
    });
    await page.evaluate(() => CellI18n.setLanguage('zh-CN'));
    await other.evaluate(() => window.dispatchEvent(new Event('pageshow')));
    assert.equal(await other.evaluate(() => CellI18n.lang), 'zh-CN');
    assert.deepEqual(await other.evaluate(() => languageEvents), ['zh-CN']);
  }));

test('throwing storage getters/methods and cookies retain query/link fallback', async () => {
  for (const blocked of ['getter', 'methods']) await withFixture({ blocked }, async ({ page }) => {
    assert.equal(await page.evaluate(() => CellI18n.lang), 'en');
    await page.evaluate(() => {
      const a = document.createElement('a'); a.id = 'next'; a.href = 'https://www.cellaidata.com/data/'; document.body.append(a);
      CellI18n.setLanguage('zh-CN');
    });
    await page.waitForFunction(() => document.getElementById('next').href.includes('lang=zh-CN'));
    await page.goto(await page.locator('#next').getAttribute('href'));
    assert.equal(await page.evaluate(() => CellI18n.lang), 'zh-CN');
    await page.reload();
    assert.equal(await page.evaluate(() => CellI18n.lang), 'zh-CN');
  });
});

(async () => {
  const executablePath = process.env.CHROME_PATH ||
    (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined);
  browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  let failures = 0;
  try {
    for (const { name, run } of tests) {
      try { await run(); console.log('PASS ' + name); }
      catch (error) { failures++; console.error('FAIL ' + name + '\n' + error.stack); }
    }
  } finally { await browser.close(); }
  console.log(`${tests.length - failures}/${tests.length} runtime test groups passed; no live requests or app draft storage.`);
  if (failures) process.exitCode = 1;
})().catch(error => { console.error(error); process.exitCode = 1; });

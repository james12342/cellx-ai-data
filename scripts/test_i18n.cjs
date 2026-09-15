const { chromium } = require('C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const live = process.argv.includes('--live');
const workflow = JSON.parse(fs.readFileSync('cellx-extension-ui/workflow-templates/orderdesk-daily-orders-to-db.json', 'utf8'));
workflow.id = 'i18n-fixture';
workflow.name = 'Login';
workflow.nodes[0].name = 'Research';

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  try {
    async function setup(locale, blockedStorage = false) {
      const context = await browser.newContext({ locale, viewport: { width: 1440, height: 1000 } });
      await context.addInitScript(({ workflow, blockedStorage }) => {
        localStorage.setItem('cellx-workflows-draft', JSON.stringify({ version: '1.0', activeWorkflowId: workflow.id, workflows: [workflow] }));
        if (blockedStorage) {
          Object.defineProperty(document, 'cookie', { get: () => '', set: () => {} });
          Storage.prototype.setItem = () => { throw new Error('Storage unavailable'); };
          Storage.prototype.getItem = () => null;
        }
      }, { workflow, blockedStorage });
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (!/^(www\.|app\.)?cellaidata\.com$/.test(url.hostname)) return route.abort();
        if (url.pathname.startsWith('/ext-api')) return route.fulfill({ json: { ok: true, version: '0.1.0', templates: [], items: [], tables: [], database: 'fixture', tableCount: 0, scheduler: { running: true } } });
        if (live) return route.continue();
        const agent = url.pathname.startsWith('/agent/');
        const relative = agent ? url.pathname.slice('/agent/'.length) : url.pathname.slice(1);
        const file = path.join(agent ? 'cellx-extension-ui' : 'rdp-marketing-site', relative || 'index.html');
        if (!fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({ status: 404, body: '' });
        const contentType = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.json') ? 'application/json' : file.endsWith('.png') ? 'image/png' : 'text/html';
        return route.fulfill({ contentType, body: fs.readFileSync(file) });
      });
      return context;
    }
    for (const locale of ['zh-CN', 'en-US', 'zh-TW', 'fr-FR']) {
      const context = await setup(locale);
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto('https://app.cellaidata.com/agent/');
      const expected = locale.startsWith('zh') ? 'zh-CN' : 'en';
      await page.waitForFunction(lang => document.documentElement.lang === lang && window.CellI18n, expected);
      assert.equal(await page.locator('#saveBtn').textContent(), expected === 'en' ? 'Save Draft' : '保存草稿');
      const schedule = page.locator('[data-daily-run-time]');
      const timeBefore = await schedule.inputValue();
      const zoneBefore = await page.locator('[data-integration-key="timezone"]').inputValue();
      await page.locator('#aiVoiceBuilderBtn').click();
      await page.locator('#aiVoicePrompt').fill('Login Research Save Draft 用户内容');
      await page.evaluate(() => {
        const p = document.createElement('p');
        p.textContent = 'Login Research Save Draft';
        document.querySelector('#aiVoiceConversation').append(p);
      });
      await page.locator('[data-language-picker]').selectOption(expected === 'en' ? 'zh-CN' : 'en');
      assert.equal(await page.locator('#aiVoicePrompt').inputValue(), 'Login Research Save Draft 用户内容');
      assert.equal(await page.locator('#aiVoiceConversation').innerText(), 'Login Research Save Draft');
      assert.equal(await schedule.inputValue(), timeBefore);
      assert.equal(await page.locator('[data-integration-key="timezone"]').inputValue(), zoneBefore);
      assert.equal(await page.locator('#propName').inputValue(), 'Research');
      assert.equal(await page.locator('#workflowTitle').textContent(), 'Login');
      assert.equal((await page.locator('#aiVoicePrompt').boundingBox()).height, 62);
      await page.evaluate(() => {
        nodes[0].testResult = { status: 'success', message: 'Completed', input: {}, output: { rows: [{ Name: 'Login', Notes: 'Save Draft', url: 'https://example.com/' }] } };
        showNodeResultDialog(nodes[0].id);
      });
      assert((await page.locator('#resultDialog table').innerText()).includes('Login'));
      assert((await page.locator('#resultDialog table').innerText()).includes('Save Draft'));
      assert((await page.locator('#resultDialog table thead').innerText()).includes('Name'));
      await page.locator('[data-language-picker]').selectOption(expected);
      assert((await page.locator('#resultDialog table').innerText()).includes('Save Draft'));
      await page.locator('[data-close-result-dialog]').click();
      await page.locator('[data-language-picker]').selectOption(expected === 'en' ? 'zh-CN' : 'en');
      await page.reload();
      assert.equal(await page.locator('[data-language-picker]').inputValue(), expected === 'en' ? 'zh-CN' : 'en');
      await page.goto('https://www.cellaidata.com/');
      assert.equal(await page.locator('[data-language-picker]').inputValue(), expected === 'en' ? 'zh-CN' : 'en');
      await page.locator('[data-language-picker]').selectOption('zh-CN');
      assert((await page.locator('a[href*="app.cellaidata.com/agent/"]').first().getAttribute('href')).includes('lang=zh-CN'));
      for (const width of [320, 390, 768, 1440]) {
        await page.setViewportSize({ width, height: 1000 });
        const box = await page.locator('[data-language-picker]').boundingBox();
        assert(box && box.x >= 0 && box.x + box.width <= width + 1, 'Language control fits ' + width);
        if (locale === 'zh-CN' && [390, 1440].includes(width)) await page.screenshot({ path: `outputs/i18n-home-${live ? 'live' : 'local'}-${width}.png` });
      }
      await page.goto('https://www.cellaidata.com/analytics.html');
      assert.equal(await page.locator('[data-language-picker]').inputValue(), 'zh-CN');
      await page.goto('https://app.cellaidata.com/agent/');
      await page.locator('#marketplaceBtn').click();
      assert((await page.locator('#marketplacePanel').innerText()).includes('市场'));
      await page.locator('#closeMarketplaceBtn').click();
      await page.locator('#browseTemplatesBtn').click();
      assert((await page.locator('#templateBrowser').innerText()).includes('模板'));
      await page.locator('#closeTemplatesBtn').click();
      await page.locator('#aiVoiceBuilderBtn').click();
      if (locale === 'zh-CN') {
        for (const width of [390, 1440]) {
          await page.setViewportSize({ width, height: 1000 });
          await page.locator('#aiVoiceBuilderPanel').screenshot({ path: `outputs/i18n-voice-${live ? 'live' : 'local'}-${width}.png` });
        }
      }
      assert.deepEqual(errors, []);
      await context.close();
    }
    const blocked = await setup('en-US', true);
    const fallback = await blocked.newPage();
    await fallback.goto('https://www.cellaidata.com/');
    await fallback.locator('[data-language-picker]').selectOption('zh-CN');
    const href = await fallback.locator('a[href*="app.cellaidata.com/agent/"]').first().getAttribute('href');
    await fallback.goto(href);
    assert.equal(await fallback.locator('[data-language-picker]').inputValue(), 'zh-CN');
    await fallback.reload();
    assert.equal(await fallback.locator('[data-language-picker]').inputValue(), 'zh-CN');
    await blocked.close();
    console.log('PASS: first-visit zh/en/zh-TW/other, switching, refresh, cross-origin cookie/link fallback, analytics/templates/marketplace, user content/timezone preservation and responsive controls. ' + (live ? 'LIVE' : 'LOCAL'));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

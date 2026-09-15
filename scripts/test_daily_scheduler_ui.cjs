const { chromium } = require('C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const live = process.argv.includes('--live');
  const site = live ? 'https://app.cellaidata.com' : 'https://scheduler.test';
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    const dialogs = [];
    const posted = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', async dialog => { dialogs.push(dialog.message()); await dialog.accept(); });
    const workflow = JSON.parse(fs.readFileSync('cellx-extension-ui/workflow-templates/orderdesk-daily-orders-to-db.json', 'utf8'));
    workflow.id = 'scheduler-ui-test';
    workflow.nodes[1].integrationSettings.orderdeskStoreId = 'fixture-store';
    workflow.nodes[1].integrationSettings.orderdeskApiKey = 'fixture-key';
    await page.addInitScript(workflow => {
      if (!localStorage.getItem('cellx-workflows-draft')) localStorage.setItem('cellx-workflows-draft', JSON.stringify({ version: '1.0', activeWorkflowId: workflow.id, workflows: [workflow] }));
      sessionStorage.setItem('cellx-workflow-management-token', 'fixture-admin');
    }, workflow);
    let saved;
    const health = { running: true };
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== site) return route.abort();
      if (url.pathname === '/ext-api/workflow-schedules/save') {
        const payload = route.request().postDataJSON();
        posted.push(payload);
        const settings = payload.workflow.nodes[0].integrationSettings;
        if (!/^\d{1,2}\s+\d{1,2}\s+\*\s+\*\s+\*$/.test(settings.schedule)) return route.fulfill({ status: 400, json: { ok: false, message: 'Daily schedules require a daily time.' } });
        const [minute, hour] = settings.schedule.split(/\s+/).map(Number);
        const next = new Date('2026-09-15T00:00:00Z');
        next.setUTCHours(hour + (settings.timezone === 'America/New_York' ? 4 : 7), minute);
        saved = { saved: true, enabled: settings.scheduleEnabled === 'true', nextRun: settings.scheduleEnabled === 'true' ? next.toISOString() : null, timezone: settings.timezone, runs: [] };
        return route.fulfill({ json: { ok: true, schedule: saved, scheduler: health } });
      }
      if (url.pathname === '/ext-api/workflow-schedules') return route.fulfill({ json: { ok: true, schedule: saved, scheduler: health } });
      if (url.pathname === '/ext-api/workflows/run') {
        return route.fulfill({ json: { ok: false, status: 'error', results: [{ nodeId: 'node-2', status: 'error', message: 'Fixture provider failure', output: { ok: false }, input: {} }] } });
      }
      if (url.pathname.startsWith('/ext-api')) return route.fulfill({ json: { ok: true, version: '0.1.0', tables: [], items: [], database: 'fixture', tableCount: 0 } });
      if (live) return route.continue();
      const file = path.join('cellx-extension-ui', url.pathname.replace(/^\/(?:workflow|agent)\/?/, '') || 'index.html');
      if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: '' });
      const contentType = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.json') ? 'application/json' : 'text/html';
      return route.fulfill({ contentType, body: fs.readFileSync(file) });
    });
    await page.goto(site + '/agent/');
    const time = page.locator('[data-daily-run-time]');
    const raw = page.locator('[data-integration-key="schedule"]');
    assert.equal(await time.inputValue(), '06:00');
    assert.equal(await page.locator('.daily-cron-advanced').evaluate(el => el.open), false);
    assert.deepEqual(await page.evaluate(() => ['0 0 * * *', '59 23 * * *', '60 12 * * *', '0 24 * * *', '*/15 * * * *'].map(dailyCronToTime)), ['00:00', '23:59', '', '', '']);
    await time.fill('07:30');
    await page.locator('[data-integration-key="timezone"]').fill('America/New_York');
    await page.locator('#saveBtn').click();
    await page.waitForFunction(() => !document.getElementById('saveBtn').disabled);
    assert.equal(posted[0].workflow.nodes[0].integrationSettings.schedule, '30 7 * * *');
    assert.equal(posted[0].workflow.nodes[1].integrationSettings.scriptName, 'orderdesk_orders_to_db.py');
    assert.equal(posted[0].workflow.nodes[1].integrationSettings.orderdeskApiKey, 'fixture-key');
    assert.ok(posted[0].workflow.nodes.every(node => !('testResult' in node)));
    assert.ok(dialogs[0].includes('saved on server'));
    await page.getByText(/Next run:/).first().waitFor();
    await time.fill('00:00');
    await page.locator('#saveCredentialBtn').click();
    await page.getByText(/^Daily schedule saved on server/).first().waitFor();
    assert.equal(posted.at(-1).workflow.nodes[0].integrationSettings.schedule, '0 0 * * *');
    await time.fill('23:59');
    await page.locator('#saveBtn').click();
    await page.waitForFunction(() => !document.getElementById('saveBtn').disabled);
    assert.equal(posted.at(-1).workflow.nodes[0].integrationSettings.schedule, '59 23 * * *');
    await page.reload();
    assert.equal(await time.inputValue(), '23:59');
    assert.equal(await page.locator('[data-integration-key="timezone"]').inputValue(), 'America/New_York');
    await page.locator('.daily-cron-advanced summary').click();
    await raw.fill('15 9 * * *');
    assert.equal(await time.inputValue(), '09:15');
    await raw.fill('*/15 * * * *');
    assert.equal(await time.inputValue(), '');
    await page.locator('#saveBtn').click();
    await page.waitForFunction(() => !document.getElementById('saveBtn').disabled);
    assert.equal(posted.at(-1).workflow.nodes[0].integrationSettings.schedule, '*/15 * * * *');
    assert.ok(dialogs.at(-1).includes('server schedule was not updated'));
    await page.reload();
    assert.equal(await raw.inputValue(), '*/15 * * * *');
    assert.equal(await page.locator('.daily-cron-advanced').evaluate(el => el.open), true);
    await page.locator('#dailyCronStatus').waitFor();
    await time.fill('18:45');
    await page.locator('#saveCredentialBtn').click();
    await page.getByText(/Daily schedule saved on server/).first().waitFor();
    assert.equal(posted.at(-1).workflow.nodes[0].integrationSettings.schedule, '45 18 * * *');
    const count = posted.length;
    await time.fill('');
    await page.locator('#saveBtn').click();
    await page.waitForFunction(() => !document.getElementById('saveBtn').disabled);
    assert.equal(posted.length, count);
    assert.ok(dialogs.at(-1).includes('Choose a valid daily run time'));
    await time.fill('18:45');
    await page.locator('[data-integration-key="scheduleEnabled"]').selectOption('false');
    await page.locator('#saveCredentialBtn').click();
    await page.getByText('Agent saved on server. Daily schedule is disabled.', { exact: true }).waitFor();
    assert.equal(posted.at(-1).workflow.nodes[0].integrationSettings.scheduleEnabled, 'false');
    await page.locator('#refreshScheduleBtn').click();
    await page.getByText('Disabled | Scheduler: Running', { exact: true }).waitFor();
    await page.locator('#runWorkflowBtn').click();
    await page.getByText('Fixture provider failure', { exact: true }).first().waitFor();
    await page.evaluate(() => {
      const data = JSON.parse(localStorage.getItem('cellx-workflows-draft'));
      const other = structuredClone(data.workflows[0]);
      other.id = 'same-name-other';
      other.nodes[0].integrationSettings.schedule = '10 8 * * *';
      data.workflows.push(other);
      localStorage.setItem('cellx-workflows-draft', JSON.stringify(data));
    });
    await page.reload();
    await page.locator('[data-workflow-id="same-name-other"]').click();
    assert.equal(await time.inputValue(), '08:10');
    await page.locator('[data-workflow-id="scheduler-ui-test"]').click();
    assert.equal(await time.inputValue(), '18:45');
    assert.deepEqual(errors, []);
    fs.mkdirSync('outputs', { recursive: true });
    await page.locator('.properties').screenshot({ path: 'outputs/daily-schedule-properties.png' });
    for (const width of [1770, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      const fits = await page.locator('.properties').evaluate(panel => {
        const bounds = panel.getBoundingClientRect();
        return [...panel.querySelectorAll('input, select, .property-actions button')].every(el => {
          const r = el.getBoundingClientRect();
          return !r.width || r.left >= bounds.left && r.right <= bounds.right;
        });
      });
      assert.ok(fits, `Property controls overflow at ${width}`);
      if (width !== 320) await page.locator('.properties').screenshot({ path: `outputs/daily-schedule-properties-${width}.png` });
    }
    console.log('PASS: daily time/cron conversion, midnight/end of day, both save buttons, reload, timezone, next run, preserved complex cron, empty-time validation, disabled schedule, narrow layouts and no JS errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

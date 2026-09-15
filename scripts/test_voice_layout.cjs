const { chromium } = require('C:/Users/hibre/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const live = process.argv.includes('--live');
  const site = live ? 'https://app.cellaidata.com' : 'https://voice.test';
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: process.argv.includes('--zh') ? 'zh-CN' : 'en-US' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      sessionStorage.setItem('cellx-workflow-management-token', 'fixture-admin');
      window.voiceSent = [];
      window.fakeTrack = { enabled: true, stop() { window.trackStopped = true; } };
      Object.defineProperty(navigator.mediaDevices, 'getUserMedia', { value: async () => ({ getTracks: () => [window.fakeTrack], getAudioTracks: () => [window.fakeTrack] }) });
      window.RTCPeerConnection = class {
        addTrack() {}
        createDataChannel() {
          window.voiceChannel = { readyState: 'connecting', send(value) { window.voiceSent.push(JSON.parse(value)); }, close() { this.readyState = 'closed'; this.onclose?.(); } };
          return window.voiceChannel;
        }
        async createOffer() { return { sdp: 'mock-sdp' }; }
        async setLocalDescription() {}
        async setRemoteDescription() { window.voiceChannel.readyState = 'open'; window.voiceChannel.onopen(); }
        close() {}
      };
    });
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.href === 'https://api.openai.com/v1/realtime/calls') return route.fulfill({ body: 'mock-sdp' });
      if (url.origin !== site) return route.abort();
      if (url.pathname.endsWith('/ai/realtime-session')) return route.fulfill({ json: { ok: true, value: 'mock-ephemeral' } });
      if (url.pathname.startsWith('/ext-api')) return route.fulfill({ json: { ok: true, tables: [], items: [], database: 'fixture', tableCount: 0 } });
      if (live) return route.continue();
      const file = path.join('cellx-extension-ui', url.pathname.replace(/^\/agent\/?/, '') || 'index.html');
      if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: '' });
      const contentType = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.json') ? 'application/json' : 'text/html';
      return route.fulfill({ contentType, body: fs.readFileSync(file) });
    });
    await page.goto(site + '/agent/');
    await page.locator('#aiVoiceBuilderBtn').click();
    await page.locator('#voiceListenBtn').click();
    await page.waitForFunction(() => document.querySelector('#aiVoiceStatus').textContent === (window.CellI18n ? CellI18n.t('Voice connected.') : 'Voice connected.'));
    await page.locator('#voiceMuteBtn').click();
    assert.equal(await page.evaluate(() => window.fakeTrack.enabled), false);
    await page.locator('#voiceMuteBtn').click();
    assert.equal(await page.evaluate(() => window.fakeTrack.enabled), true);
    await page.locator('#aiVoicePrompt').fill('Build an order agent');
    await page.locator('#voiceSendBtn').click();
    assert.equal(await page.locator('#aiVoicePrompt').inputValue(), '');
    assert(await page.evaluate(() => window.voiceSent.some(e => e.item?.content?.[0]?.text === 'Build an order agent')));
    for (const width of [320, 390, 768, 1024, 1440, 1770]) {
      await page.setViewportSize({ width, height: width < 1000 ? 844 : 1000 });
      const metrics = await page.evaluate(() => {
        const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { x: r.x, right: r.right, top: r.top, bottom: r.bottom, height: r.height }; };
        return { input: rect('#aiVoicePrompt'), chat: rect('#aiVoiceConversation'), panel: rect('.ai-voice-input'), preview: rect('.ai-voice-preview'), actions: [...document.querySelectorAll('.ai-voice-input .ai-voice-actions button')].map(el => { const r = el.getBoundingClientRect(); return { x: r.x, right: r.right, top: r.top, bottom: r.bottom }; }) };
      });
      assert.equal(metrics.input.height, 62);
      assert(metrics.chat.height >= 280);
      assert(metrics.panel.x >= 0 && metrics.panel.right <= width, `Panel fits at ${width}`);
      if (width <= 900) assert(metrics.preview.top >= metrics.panel.bottom);
      for (const button of metrics.actions) {
        assert(button.x >= metrics.panel.x && button.right <= metrics.panel.right);
        assert(button.top >= metrics.input.bottom);
      }
      for (let i = 0; i < metrics.actions.length; i++) for (let j = i + 1; j < metrics.actions.length; j++) {
        const a = metrics.actions[i], b = metrics.actions[j];
        assert(a.right <= b.x || b.right <= a.x || a.bottom <= b.top || b.bottom <= a.top);
      }
      if ([390, 1440].includes(width)) await page.screenshot({ path: `outputs/voice-layout-${live ? 'live' : 'local'}-${width}.png`, fullPage: true });
    }
    await page.locator('#aiVoicePrompt').evaluate(el => { el.style.height = '500px'; el.value = Array(30).fill('Long request').join('\n'); });
    assert.equal((await page.locator('#aiVoicePrompt').boundingBox()).height, 140);
    assert(await page.locator('#aiVoicePrompt').evaluate(el => el.scrollHeight > el.clientHeight));
    await page.locator('#closeAiVoiceBuilderBtn').click();
    await page.waitForFunction(() => window.trackStopped);
    assert.deepEqual(errors, []);
    console.log('PASS: two-line input, taller chat, bounded resize, six viewports, accessible controls, mocked connect/mute/send/close cleanup; ' + (live ? 'live assets' : 'local assets'));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

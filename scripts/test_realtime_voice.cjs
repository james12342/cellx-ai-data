const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.voiceSent = [];
      window.trackStopped = false;
      window.fakeTrack = { enabled: true, stop() { window.trackStopped = true; } };
      Object.defineProperty(navigator.mediaDevices, 'getUserMedia', { value: async () => ({
        getTracks: () => [window.fakeTrack], getAudioTracks: () => [window.fakeTrack],
      }) });
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
    let builds = 0;
    await page.route('**/ai/realtime-session', route => route.fulfill({ json: { ok: true, value: 'mock-ephemeral' } }));
    await page.route('https://api.openai.com/v1/realtime/calls', route => route.fulfill({ body: 'mock-sdp' }));
    await page.route('**/ai/workflow-builder', route => {
      builds++;
      return route.fulfill({ json: { ok: true, template: { name: 'Voice Test Workflow', nodes: [{ id: 'node-1', type: 'trigger', name: 'Daily Schedule', action: 'cron', x: 80, y: 80 }], links: [] } } });
    });
    await page.goto(process.env.VOICE_TEST_URL || 'http://127.0.0.1:3016/workflow/');
    await page.locator('#aiVoiceBuilderBtn').click();
    await page.locator('#voiceListenBtn').click();
    await page.waitForFunction(() => document.querySelector('#aiVoiceStatus').textContent === 'Voice connected.');
    await page.locator('#voiceMuteBtn').click();
    assert.equal(await page.evaluate(() => window.fakeTrack.enabled), false);
    await page.locator('#voiceMuteBtn').click();
    assert.equal(await page.evaluate(() => window.fakeTrack.enabled), true);
    const tool = async (id, name, args = {}) => {
      await page.evaluate(({ id, name, args }) => window.voiceChannel.onmessage({ data: JSON.stringify({ type: 'response.function_call_arguments.done', call_id: id, name, arguments: JSON.stringify(args) }) }), { id, name, args });
      await page.waitForFunction(id => window.voiceSent.some(e => e.item?.call_id === id), id);
      return page.evaluate(id => JSON.parse(window.voiceSent.find(e => e.item?.call_id === id).item.output), id);
    };
    assert.equal((await tool('build-one', 'build_workflow', { request: 'Create a daily order workflow', mode: 'create' })).ok, true);
    assert.equal((await tool('apply-one', 'apply_workflow_draft')).applied, true);
    assert.equal(await page.locator('.workflow-tab.active .workflow-tab-title').textContent(), 'Voice Test Workflow');
    assert.equal((await tool('apply-again', 'apply_workflow_draft')).ok, false);
    await tool('build-two', 'build_workflow', { request: 'Revise this workflow', mode: 'update' });
    await page.evaluate(() => { workflowTitle = 'Manual edit while drafting'; });
    assert.equal((await tool('apply-stale', 'apply_workflow_draft')).ok, false);
    await tool('build-two', 'build_workflow', { request: 'Duplicate event', mode: 'update' });
    assert.equal(builds, 2);
    await page.screenshot({ path: path.join(process.cwd(), 'dist', 'realtime-voice-desktop.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(process.cwd(), 'dist', 'realtime-voice-mobile.png') });
    const boxes = await page.locator('.ai-voice-input, .ai-voice-preview').evaluateAll(elements => elements.map(e => ({ x: e.getBoundingClientRect().x, right: e.getBoundingClientRect().right, top: e.getBoundingClientRect().top, bottom: e.getBoundingClientRect().bottom })));
    assert(boxes[1].top >= boxes[0].bottom, 'Mobile panels must stack without overlapping');
    await page.locator('#closeAiVoiceBuilderBtn').click();
    await page.waitForFunction(() => window.trackStopped);
    assert.equal(await page.locator('#voiceListenBtn').isDisabled(), false);
    assert.deepEqual(errors, []);
    console.log('PASS: connect, mute, draft, apply, duplicate events, stale-draft protection, close cleanup, desktop/mobile layout.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

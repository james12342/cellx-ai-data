(() => {
  const root = document.querySelector('[data-workflow-motion]');
  if (!root) return;
  const nodes = [...root.querySelectorAll('[data-motion-node]')];
  const wires = [...root.querySelectorAll('[data-motion-wire]')];
  const results = [...root.querySelectorAll('[data-motion-result]')];
  const carriers = [...root.querySelectorAll('[data-motion-carrier]')];
  const status = root.querySelector('[data-motion-status]');
  const count = root.querySelector('[data-motion-count]');
  const toggle = root.querySelector('[data-motion-toggle]');
  const progress = root.querySelector('[data-motion-progress]');
  const timeline = root.querySelector('.motion-timeline');
  const time = root.querySelector('[data-motion-time]');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const stages = ['Agent receives new orders', 'Agent reviews carrier choices', 'Data skill saves the results', 'Email skill prepares a summary', 'Complete. Agent results are ready.'];
  const waiting = ['Ready for orders', 'Waiting for orders', 'Waiting for review', 'Waiting for results'];
  const running = ['Receiving 3 orders', 'Reviewing 3 orders', 'Writing 3 rows', 'Composing summary'];
  const done = ['3 orders received', '3 carriers matched', '3 rows saved', 'Email preview ready'];
  const duration = 16000;
  let elapsed = reduced.matches ? 12000 : 0;
  let paused = reduced.matches;
  let visible = true;
  let frame = 0;
  let last = null;
  let currentStage = -1;

  function localize(element, english, params = {}) {
    element.dataset.i18n = english;
    element.dataset.i18nParams = JSON.stringify(params);
    element.textContent = window.CellI18n.t(english, params);
  }

  function render() {
    const stage = Math.min(4, Math.floor(elapsed / 2800));
    if (stage !== currentStage) {
      currentStage = stage;
      root.dataset.stage = String(stage);
      localize(status, stages[stage]);
      nodes.forEach((node, index) => {
        node.dataset.state = index < stage ? 'done' : index === stage ? 'running' : 'waiting';
        localize(node.querySelector('[data-motion-note]'), index < stage ? done[index] : index === stage ? running[index] : waiting[index]);
      });
      wires.forEach(wire => { wire.dataset.active = String(Number(wire.dataset.motionWire) === stage); });
      carriers.forEach(cell => { cell.textContent = stage >= 2 ? cell.dataset.motionCarrier : '\u2014'; });
      results.forEach(cell => { localize(cell, stage >= 4 ? 'Summary ready' : stage >= 3 ? 'Saved' : stage >= 2 ? 'Matched' : stage >= 1 ? 'Received' : 'Pending'); });
      localize(count, '{count} / {total} processed', { count: stage >= 3 ? 3 : 0, total: 3 });
    }
    progress.style.transform = `scaleX(${elapsed / duration})`;
    const seconds = Math.floor(elapsed / 1000);
    time.textContent = `00:${String(seconds).padStart(2, '0')} / 00:16`;
    timeline.setAttribute('aria-valuenow', String(seconds));
  }

  function tick(now) {
    if (last !== null) elapsed = (elapsed + Math.min(now - last, 100)) % duration;
    last = now;
    render();
    frame = requestAnimationFrame(tick);
  }

  // Suspend both the timeline and CSS packets when the demo is off screen.
  function syncPlayback() {
    cancelAnimationFrame(frame);
    last = null;
    const stopped = paused || !visible || document.hidden;
    root.dataset.paused = String(stopped);
    toggle.dataset.paused = String(paused);
    const label = paused ? 'Play agent demo' : 'Pause agent demo';
    toggle.dataset.i18nAriaLabel = label;
    toggle.dataset.i18nTitle = label;
    toggle.setAttribute('aria-label', window.CellI18n.t(label));
    toggle.title = window.CellI18n.t(label);
    if (!stopped) frame = requestAnimationFrame(tick);
  }
  toggle.addEventListener('click', () => { paused = !paused; syncPlayback(); });
  root.querySelector('[data-motion-replay]').addEventListener('click', () => {
    elapsed = 0;
    paused = false;
    render();
    syncPlayback();
  });
  document.addEventListener('visibilitychange', syncPlayback);
  reduced.addEventListener('change', () => {
    paused = reduced.matches;
    if (paused) elapsed = 12000;
    render();
    syncPlayback();
  });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      syncPlayback();
    }, { threshold: 0.1 }).observe(root);
  }
  render();
  syncPlayback();
})();

/* Explicit UI messages only: records, user input and AI output are never scanned. */
(() => {
  'use strict';
  const key = 'cell-ai-data-language';
  const dictionaries = Object.create(null);
  const valid = value => value === 'en' || value === 'zh-CN';
  const ownedHost = host => /^(?:www\.|app\.)?cellaidata\.com$/.test(host);
  const readLocal = () => { try { return localStorage.getItem(key); } catch { return null; } };
  const readCookie = () => { try { return document.cookie.split('; ').find(item => item.startsWith(key + '='))?.slice(key.length + 1); } catch { return null; } };
  const query = new URL(location.href).searchParams.get('lang');
  const cookie = readCookie();
  const local = readLocal();
  let language = valid(query) ? query : valid(cookie) ? cookie : valid(local) ? local : /^zh(?:-|$)/i.test(navigator.languages?.[0] || navigator.language || '') ? 'zh-CN' : 'en';
  const rendered = new WeakMap();
  let observer;
  const locale = () => language === 'zh-CN' ? 'zh-CN' : 'en-US';
  const messageParams = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  function t(message, params = {}) {
    params = messageParams(params);
    const template = language === 'zh-CN' ? dictionaries[message] || message : message;
    return String(template).replace(/\{(\w+)\}/g, (match, name) => Object.hasOwn(params, name) ? String(params[name]) : match);
  }
  function render(root = document) {
    const selectors = '[data-i18n], [data-i18n-placeholder], [data-i18n-title], [data-i18n-aria-label]';
    const elements = [...(root.matches?.(selectors) ? [root] : []), ...root.querySelectorAll(selectors)];
    for (const element of elements) {
      if (element.closest('[translate="no"], [data-i18n-skip]')) continue;
      let params = {};
      try { params = messageParams(JSON.parse(element.getAttribute('data-i18n-params') || '{}')); } catch { /* Keep original message on malformed params. */ }
      if (element.hasAttribute('data-i18n')) {
        const value = t(element.getAttribute('data-i18n'), params);
        if (element.textContent !== value) element.textContent = value;
        rendered.set(element, value);
      }
      for (const name of ['placeholder', 'title', 'aria-label']) {
        const source = element.getAttribute('data-i18n-' + name);
        if (source !== null) {
          const value = t(source, params);
          if (element.getAttribute(name) !== value) element.setAttribute(name, value);
        }
      }
    }
    document.documentElement.lang = language;
    document.querySelectorAll('[data-language-picker]').forEach(select => { select.value = language; });
  }
  function persist() {
    try { localStorage.setItem(key, language); } catch { /* Session-only fallback. */ }
    try {
      const domain = ownedHost(location.hostname) ? '; Domain=cellaidata.com' : '';
      document.cookie = key + '=' + language + '; Path=/; Max-Age=31536000; SameSite=Lax' + domain + (location.protocol === 'https:' ? '; Secure' : '');
    } catch { /* Navigation links carry the preference when storage is unavailable. */ }
  }
  function navigationLanguage(root = document) {
    root.querySelectorAll('a[href]').forEach(link => {
      if (link.closest('[translate="no"], [data-i18n-skip]') || link.hasAttribute('download')) return;
      const raw = link.getAttribute('href');
      if (raw.startsWith('#')) return;
      try {
        const url = new URL(raw, location.href);
        if (!/^https?:$/.test(url.protocol)) return;
        if (url.origin !== location.origin && !(ownedHost(url.hostname) && ownedHost(location.hostname))) return;
        if (!/^\/(?:agent\/?|workflow\/?|data\/?|portal\/?|analytics\.html|index\.html)?$/.test(url.pathname)) return;
        url.searchParams.set('lang', language);
        if (link.href !== url.href) link.href = url.href;
      } catch { /* Not a navigation URL. */ }
    });
  }
  function setLanguage(value) {
    if (!valid(value)) return;
    language = value;
    persist();
    applyLanguage(value);
  }
  function applyLanguage(value) {
    language = value;
    const url = new URL(location.href);
    if (url.searchParams.has('lang')) {
      url.searchParams.set('lang', value);
      history.replaceState(history.state, '', url.href);
    }
    render();
    navigationLanguage();
    window.dispatchEvent(new CustomEvent('cell-language-change', { detail: { language } }));
  }
  window.CellI18n = {
    t, render, setLanguage,
    get lang() { return language; },
    get locale() { return locale(); },
    register(dictionary) { Object.assign(dictionaries, dictionary); if (document.readyState !== 'loading') render(); },
    formatDate(date, options = {}) {
      if (date == null || date === '') return '';
      const value = new Date(date);
      const granular = ['year', 'month', 'day', 'hour', 'minute', 'second', 'weekday', 'timeZoneName', 'era', 'fractionalSecondDigits', 'dayPeriod'].some(name => name in options);
      const format = granular ? options : { dateStyle: 'medium', timeStyle: 'short', ...options };
      if (Number.isNaN(value.getTime())) return String(date);
      try { return new Intl.DateTimeFormat(locale(), format).format(value); }
      catch { return String(date); }
    },
    text(element, message, params = {}) {
      element.setAttribute('data-i18n', message);
      element.setAttribute('data-i18n-params', JSON.stringify(messageParams(params)));
      render(element);
    },
  };
  document.documentElement.lang = language;
  if (valid(query)) persist();
  function start() {
    render();
    navigationLanguage();
    document.addEventListener('change', event => { if (event.target.matches('[data-language-picker]')) setLanguage(event.target.value); });
    observer = new MutationObserver(records => {
      observer.disconnect();
      try {
      // Drop stale source keys if application code intentionally replaces a status.
      for (const record of records) {
        const element = record.type === 'characterData' ? record.target.parentElement?.closest('[data-i18n]') : record.target;
        if (['childList', 'characterData'].includes(record.type) && element && rendered.has(element) && element.textContent !== rendered.get(element)) {
          const changedKey = records.some(item => item.target === element && item.type === 'attributes' && ['data-i18n', 'data-i18n-params'].includes(item.attributeName));
          if (!changedKey) {
            element.removeAttribute('data-i18n');
            element.removeAttribute('data-agent-i18n');
            rendered.delete(element);
          }
        }
      }
      for (const record of records) {
        if (record.type === 'attributes') render(record.target);
        for (const node of record.addedNodes || []) if (node.nodeType === 1) render(node);
      }
      navigationLanguage();
      } finally { observe(); }
    });
    function observe() { observer.observe(document.body, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['href', 'data-i18n', 'data-i18n-params', 'data-i18n-placeholder', 'data-i18n-title', 'data-i18n-aria-label'] }); }
    observe();
    window.addEventListener('storage', event => { if (event.key === key && valid(event.newValue)) applyLanguage(event.newValue); });
    const syncCookie = () => { const saved = readCookie(); if (valid(saved) && saved !== language) applyLanguage(saved); };
    window.addEventListener('pageshow', syncCookie);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) syncCookie(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true }); else start();
})();

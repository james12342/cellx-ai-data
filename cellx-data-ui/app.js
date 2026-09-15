(() => {
  'use strict';
  const API = '/ext-api/data-explorer';
  const TOKEN_KEY = 'cellx-workflow-management-token';
  const catalogNotes = new Set([
    'Admin access only; tenant authorization is unsupported.',
    'Company and agent grouping comes from registry drafts, not runtime saved workflows.',
    'A matching physical name does not verify registry deployment, ownership or schema equivalence.',
    'Company and agent lists include only registry table bindings.',
    'Sensitive and system tables are masked. Text is masked except approved operational columns; free text, JSON, binary and long strings are always masked.',
    'Masked columns cannot be searched, filtered or sorted. Column policy is conservative, not a content classification guarantee.',
    'Tables without an unmasked primary key have no guaranteed paging order.',
  ]);
  const $ = id => document.getElementById(id);
  const state = { token: '', tables: [], companies: new Map(), selected: null, metadata: null, page: 1, pageSize: 50, search: '', sort: '', direction: 'asc', hasMore: false, busy: false };
  const requests = new Map();
  const raw = value => value == null ? (value === null ? 'null' : '') : typeof value === 'object' ? JSON.stringify(value) : String(value);
  function message(element, key, params = {}, tone = '') {
    element.dataset.i18n = key;
    element.dataset.i18nParams = JSON.stringify(params);
    element.dataset.tone = tone;
    element.textContent = window.CellI18n.t(key, params);
  }
  function clearMessage(element) {
    delete element.dataset.i18n;
    delete element.dataset.i18nParams;
    element.textContent = '';
    delete element.dataset.tone;
  }
  function userText(tag, value, className = '') {
    const element = document.createElement(tag);
    element.textContent = raw(value);
    element.setAttribute('translate', 'no');
    element.dataset.i18nSkip = '';
    if (className) element.className = className;
    return element;
  }
  function label(tag, key, className = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    message(element, key);
    return element;
  }
  function abortAll() {
    requests.forEach(controller => controller.abort());
    requests.clear();
  }
  class ApiError extends Error {
    constructor(status, code = '') { super(code); this.status = status; }
  }
  async function request(scope, endpoint, params = {}) {
    requests.get(scope)?.abort();
    const controller = new AbortController();
    requests.set(scope, controller);
    const url = new URL(API + endpoint, location.origin);
    Object.entries(params).forEach(([key, value]) => { if (value !== '') url.searchParams.set(key, value); });
    try {
      const response = await fetch(url, { method: 'GET', headers: { 'X-Workflow-Admin-Token': state.token, Accept: 'application/json' }, cache: 'no-store', signal: controller.signal });
      let data;
      try { data = await response.json(); } catch { throw new ApiError(response.ok ? 502 : response.status); }
      if (!response.ok || data.ok !== true) throw new ApiError(response.status, typeof data.code === 'string' ? data.code : '');
      if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError');
      return data;
    } finally {
      if (requests.get(scope) === controller) requests.delete(scope);
    }
  }
  function failure(element, error) {
    if (error.name === 'AbortError') return;
    const key = ({ 401: 'Access denied. A valid admin token is required.', 403: 'Access forbidden for this request.', 400: 'Invalid query. Check the search and sort settings.', 404: 'Table or endpoint not found.', 503: 'Database service unavailable.', 502: 'Unexpected server response.' })[error.status] || 'Unable to load data. Check the connection and retry.';
    message(element, error.message ? '{message} Code: {code}' : key, error.message ? { message: window.CellI18n.t(key), code: error.message } : {}, 'error');
    // Keep the code opaque while refreshing the surrounding message on language changes.
    element.errorKey = error.message ? key : null;
    element.errorCode = error.message;
    if (error.status === 401 || error.status === 403) message($('connectionStatus'), key, {}, 'error');
  }
  function physicalState(table) {
    if (table.physical_exists === true) return table.planned ? 'Planned + actual' : 'Actual';
    if (table.physical_exists === false && table.planned) return 'Planned';
    return 'Unknown';
  }
  function resetDetail() {
    state.selected = null;
    state.metadata = null;
    state.busy = false;
    $('tableDetail').hidden = true;
    $('noSelection').hidden = false;
    for (const id of ['recordsStatus', 'metadataStatus', 'schemaStatus', 'relationsStatus', 'pageInfo']) clearMessage($(id));
    for (const id of ['recordsTable', 'schemaTable', 'relationsTable']) {
      $(id).tHead.replaceChildren(); $(id).tBodies[0].replaceChildren();
    }
  }
  function renderCatalog() {
    const filter = $('tableFilter').value.trim().toLocaleLowerCase();
    const groups = new Map();
    for (const table of state.tables) {
      const agents = table.agents?.length ? table.agents : [null];
      const companyId = table.company_id;
      const companyName = table.company_name ?? state.companies.get(companyId) ?? companyId;
      for (const agent of agents) {
        const name = agent ? raw(agent.name ?? agent.id) : '';
        if (filter && !table.name.toLocaleLowerCase().includes(filter) && !name.toLocaleLowerCase().includes(filter) && !raw(companyName).toLocaleLowerCase().includes(filter)) continue;
        const key = JSON.stringify([companyId ?? null, agent ? agent.id ?? name : null]);
        if (!groups.has(key)) groups.set(key, { name, agent, companyId, companyName, tables: [] });
        groups.get(key).tables.push(table);
      }
    }
    $('tableList').replaceChildren();
    const companies = new Map();
    for (const group of groups.values()) {
      const companyKey = group.companyId ?? null;
      if (!companies.has(companyKey)) {
        const company = document.createElement('details'); company.open = true; company.className = 'company-group';
        const heading = document.createElement('summary');
        heading.append(group.companyName != null ? userText('span', group.companyName) : label('span', 'Company not linked'));
        company.append(heading); companies.set(companyKey, company); $('tableList').append(company);
      }
      const details = document.createElement('details'); details.open = true; details.className = 'agent-group';
      const summary = document.createElement('summary');
      summary.append(group.agent ? userText('span', group.name) : label('span', 'Unlinked tables'));
      details.append(summary);
      for (const table of group.tables) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'table-choice';
        button.setAttribute('aria-current', String(state.selected?.name === table.name));
        button.append(userText('span', table.name, 'table-label'), label('span', physicalState(table), 'table-state'));
        button.addEventListener('click', () => selectTable(table));
        details.append(button);
      }
      companies.get(companyKey).append(details);
    }
    if (!groups.size && state.tables.length) $('tableList').append(label('p', 'No matching tables.', 'status'));
  }
  async function loadCatalog() {
    abortAll(); resetDetail(); state.tables = []; state.companies.clear(); renderCatalog(); $('catalogNotes').replaceChildren();
    clearMessage($('catalogStatus'));
    if (!state.token) { message($('connectionStatus'), 'Admin token required.'); return; }
    message($('connectionStatus'), 'Connecting...');
    message($('catalogStatus'), 'Loading tables...');
    $('tableList').setAttribute('aria-busy', 'true');
    try {
      const data = await request('catalog', '/catalog');
      if (!Array.isArray(data.tables) || !Array.isArray(data.planned_tables)) throw new ApiError(502);
      for (const company of data.companies || []) state.companies.set(company.id, company.name);
      const tables = new Map();
      for (const table of data.tables) {
        if (typeof table.name !== 'string') throw new ApiError(502);
        tables.set(table.name, { ...table, planned: table.association === 'registry_planned' });
      }
      for (const planned of data.planned_tables) {
        if (typeof planned.name !== 'string') throw new ApiError(502);
        const actual = tables.get(planned.name);
        const agents = new Map([...(actual?.agents || []), ...(planned.agents || [])].map(agent => [agent.id ?? agent.name, agent]));
        tables.set(planned.name, { ...planned, ...actual, planned: true, agents: [...agents.values()] });
      }
      state.tables = [...tables.values()].sort((a, b) => a.name.localeCompare(b.name));
      message($('connectionStatus'), 'Connected · read only');
      if (!state.tables.length) message($('catalogStatus'), 'No tables available.');
      else if (data.registry_available === false) message($('catalogStatus'), 'Registry unavailable. Showing physical tables only.');
      else clearMessage($('catalogStatus'));
      renderCatalog();
      if (Array.isArray(data.limitations) && data.limitations.length) {
        const notes = document.createElement('details'); notes.append(label('summary', 'Catalog notes'));
        data.limitations.forEach(note => notes.append(catalogNotes.has(note) ? label('p', note) : userText('p', note)));
        $('catalogNotes').append(notes);
      }
    } catch (error) {
      failure($('catalogStatus'), error);
      if (error.name !== 'AbortError') message($('connectionStatus'), 'Not connected', {}, 'error');
    } finally { if (!requests.has('catalog')) $('tableList').setAttribute('aria-busy', 'false'); }
  }
  function renderFacts(table) {
    $('tableFacts').replaceChildren(label('span', physicalState(table), 'badge'));
    const companyName = table.company_name ?? state.companies.get(table.company_id) ?? table.company_id;
    const company = document.createElement('span');
    if (companyName != null) company.append(label('span', 'Company'), document.createTextNode(': '), userText('span', companyName));
    else company.append(label('span', 'Company not linked'));
    $('tableFacts').append(company);
    if (table.all_columns_masked === true) $('tableFacts').append(label('span', 'All columns protected', 'protected-value'));
    for (const agent of table.agents || []) {
      const fact = document.createElement('span');
      fact.append(userText('span', agent.name ?? agent.id));
      for (const value of [agent.state, agent.use_state]) if (value != null) fact.append(document.createTextNode(' · '), userText('span', value));
      $('tableFacts').append(fact);
    }
  }
  function renderTable(id, headers, rows, translateHeaders = true, columns = []) {
    const table = $(id); const heading = document.createElement('tr');
    headers.forEach(header => { const th = translateHeaders ? label('th', header) : userText('th', header); th.scope = 'col'; heading.append(th); });
    table.tHead.replaceChildren(heading);
    table.tBodies[0].replaceChildren();
    for (const values of rows) {
      const tr = document.createElement('tr');
      for (const [index, value] of values.entries()) {
        const td = document.createElement('td');
        if (columns[index]?.masked === true && value === '[REDACTED]') {
          const protectedValue = label('span', 'Protected', 'protected-value');
          protectedValue.title = '[REDACTED]';
          td.append(protectedValue);
        } else if (id === 'schemaTable' && index >= 2 && typeof value === 'boolean') {
          td.append(label('span', value ? 'Yes' : 'No'));
        } else td.append(userText('div', value, 'cell-value'));
        tr.append(td);
      }
      table.tBodies[0].append(tr);
    }
  }
  function renderMetadata(table) {
    const columns = Array.isArray(table.columns) ? table.columns : [];
    const relations = Array.isArray(table.relations) ? table.relations : [];
    renderFacts(table);
    renderTable('schemaTable', ['Column', 'Type', 'Nullable', 'Primary key', 'Masked'], columns.map(column => [column.name, column.type, column.nullable, column.primary_key, column.masked]));
    renderTable('relationsTable', ['Column', 'Referenced table', 'Referenced column'], relations.map(relation => [relation.column, relation.referenced_table, relation.referenced_column]));
    if (!columns.length) message($('schemaStatus'), 'No schema available.'); else clearMessage($('schemaStatus'));
    if (!relations.length) message($('relationsStatus'), 'No relations reported.'); else clearMessage($('relationsStatus'));
    const options = [label('option', 'Default order')]; options[0].value = '';
    for (const column of columns) if (!column.masked && typeof column.name === 'string') {
      const option = userText('option', column.name); option.value = column.name; options.push(option);
    }
    $('sortColumn').replaceChildren(...options);
    if (options.some(option => option.value === state.sort)) $('sortColumn').value = state.sort;
    else state.sort = '';
  }
  function pagination() {
    const limit = Math.min(1000, Math.floor(10000 / state.pageSize) + 1);
    $('previousPage').disabled = state.busy || state.page <= 1;
    $('nextPage').disabled = state.busy || !state.hasMore || state.page >= limit;
    $('pageSize').disabled = state.busy || !state.metadata?.physical_exists;
    $('recordControls').querySelectorAll('input,select,button').forEach(element => { element.disabled = state.busy || !state.metadata?.physical_exists; });
  }
  async function selectTable(table) {
    requests.get('metadata')?.abort(); requests.get('rows')?.abort();
    resetDetail(); state.selected = table; state.page = 1; state.search = ''; state.sort = ''; state.direction = 'asc'; state.hasMore = false;
    $('recordSearch').value = ''; $('sortDirection').value = 'asc';
    $('tableName').textContent = table.name;
    $('noSelection').hidden = true; $('tableDetail').hidden = false;
    renderCatalog(); renderFacts(table); setView('records'); pagination();
    if (table.physical_exists === false) {
      state.metadata = table; renderMetadata(table);
      message($('recordsStatus'), 'Planned table. No physical table exists yet.');
      return;
    }
    message($('metadataStatus'), 'Loading schema...');
    try {
      const data = await request('metadata', '/table', { table: table.name });
      if (!data.table || data.table.name !== table.name || !Array.isArray(data.table.columns)) throw new ApiError(502);
      state.metadata = { ...table, ...data.table };
      renderMetadata(state.metadata); clearMessage($('metadataStatus'));
      await loadRows();
    } catch (error) { failure($('metadataStatus'), error); }
  }
  async function loadRows() {
    if (!state.metadata?.physical_exists) return;
    state.busy = true; state.hasMore = false; pagination();
    $('recordsTable').tBodies[0].replaceChildren(); $('recordsTable').tHead.replaceChildren();
    $('recordsTable').setAttribute('aria-busy', 'true'); clearMessage($('pageInfo'));
    message($('recordsStatus'), 'Loading records...');
    try {
      const data = await request('rows', '/rows', { table: state.selected.name, page: state.page, page_size: state.pageSize, search: state.search, sort: state.sort, direction: state.direction });
      if (!Array.isArray(data.rows) || !Array.isArray(data.columns) || typeof data.has_more !== 'boolean') throw new ApiError(502);
      const columns = data.columns.map(column => column.name);
      renderTable('recordsTable', columns, data.rows.map(row => columns.map(name => row[name])), false, data.columns);
      state.hasMore = data.has_more;
      if (Number.isInteger(data.page) && data.page > 0) state.page = data.page;
      if (!data.rows.length) message($('recordsStatus'), state.search ? 'No matching records.' : 'No records.');
      else clearMessage($('recordsStatus'));
      message($('pageInfo'), 'Page {page} · {count} rows', { page: state.page, count: data.rows.length });
      if (data.has_more && state.page >= Math.min(1000, Math.floor(10000 / state.pageSize) + 1)) message($('recordsStatus'), 'Query limit reached. Narrow your search.');
    } catch (error) { failure($('recordsStatus'), error); }
    finally { if (!requests.has('rows')) { state.busy = false; $('recordsTable').setAttribute('aria-busy', 'false'); pagination(); } }
  }
  function setView(view) {
    document.querySelectorAll('[data-view]').forEach(tab => {
      const selected = tab.dataset.view === view;
      tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
      $(tab.dataset.view + 'Panel').hidden = !selected;
    });
  }
  $('connectionForm').addEventListener('submit', event => {
    event.preventDefault(); state.token = $('adminToken').value.trim();
    try { if (state.token) sessionStorage.setItem(TOKEN_KEY, state.token); else sessionStorage.removeItem(TOKEN_KEY); } catch { /* The token remains in memory when session storage is unavailable. */ }
    loadCatalog();
  });
  $('disconnect').addEventListener('click', () => {
    abortAll(); state.token = ''; $('adminToken').value = ''; state.tables = []; resetDetail(); renderCatalog();
    try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* Storage may be unavailable. */ }
    clearMessage($('catalogStatus')); $('catalogNotes').replaceChildren(); message($('connectionStatus'), 'Disconnected');
  });
  $('refreshCatalog').addEventListener('click', loadCatalog);
  $('tableFilter').addEventListener('input', renderCatalog);
  $('refreshTable').addEventListener('click', () => { if (state.selected) selectTable(state.selected); });
  $('recordControls').addEventListener('submit', event => {
    event.preventDefault(); state.search = $('recordSearch').value.trim(); state.sort = $('sortColumn').value; state.direction = $('sortDirection').value; state.page = 1; loadRows();
  });
  $('pageSize').addEventListener('change', () => { state.pageSize = Number($('pageSize').value); state.page = 1; loadRows(); });
  $('previousPage').addEventListener('click', () => { if (!state.busy && state.page > 1) { state.page--; loadRows(); } });
  $('nextPage').addEventListener('click', () => { if (!state.busy && state.hasMore) { state.page++; loadRows(); } });
  const tabs = [...document.querySelectorAll('[data-view]')];
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => setView(tab.dataset.view));
    tab.addEventListener('keydown', event => {
      const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
      if (next < 0) return;
      event.preventDefault(); setView(tabs[next].dataset.view); tabs[next].focus();
    });
  });
  window.addEventListener('cell-language-change', () => {
    document.querySelectorAll('[data-tone="error"]').forEach(element => {
      if (element.errorKey) message(element, '{message} Code: {code}', { message: window.CellI18n.t(element.errorKey), code: element.errorCode }, 'error');
    });
  });
  try { state.token = sessionStorage.getItem(TOKEN_KEY) || ''; } catch { /* Start disconnected. */ }
  $('adminToken').value = state.token;
  loadCatalog();
})();

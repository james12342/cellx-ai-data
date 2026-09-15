const API_BASE = "https://app.cellaidata.com/ext-api";

function localize(element, english, params = {}) {
  element.dataset.i18n = english;
  element.dataset.i18nParams = JSON.stringify(params);
  element.textContent = window.CellI18n.t(english, params);
}

let updatedAt = null;
let privacyNote = "";

function renderUpdatedStatus() {
  localize(els.status, "Updated {date}. {note}", {
    date: window.CellI18n.formatDate(updatedAt, { dateStyle: "medium", timeStyle: "medium" }),
    note: privacyNote,
  });
}

function renderError(error) {
  updatedAt = null;
  localize(els.status, error.message ? "{message}" : "Could not load analytics.", { message: error.message });
}

const els = {
  days: document.querySelector("[data-days]"),
  token: document.querySelector("[data-token]"),
  refresh: document.querySelector("[data-refresh]"),
  totalVisits: document.querySelector("[data-total-visits]"),
  uniqueVisitors: document.querySelector("[data-unique-visitors]"),
  uniqueIps: document.querySelector("[data-unique-ips]"),
  recentCount: document.querySelector("[data-recent-count]"),
  dailyBars: document.querySelector("[data-daily-bars]"),
  pages: document.querySelector("[data-pages]"),
  referrers: document.querySelector("[data-referrers]"),
  locations: document.querySelector("[data-locations]"),
  recentTable: document.querySelector("[data-recent-table]"),
  status: document.querySelector("[data-status]"),
};

function text(value, fallback = "") {
  return String(value ?? fallback);
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function hostOrPath(value) {
  const raw = text(value, "Direct / unknown");
  try {
    const url = new URL(raw);
    return url.hostname + url.pathname;
  } catch {
    return raw || "Direct / unknown";
  }
}

function cell(value) {
  const td = document.createElement("td");
  const raw = text(value);
  if (/^https?:\/\//i.test(raw)) {
    const link = document.createElement("a");
    link.href = raw;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = raw;
    td.appendChild(link);
  } else {
    td.textContent = raw;
  }
  return td;
}

function renderBars(container, rows, labelKey, valueKey) {
  container.innerHTML = "";
  const max = Math.max(...rows.map(row => Number(row[valueKey] || 0)), 1);
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "muted-line";
    localize(empty, "No data yet.");
    container.appendChild(empty);
    return;
  }
  rows.forEach(row => {
    const line = document.createElement("div");
    line.className = "bar-row";
    const label = document.createElement("span");
    label.title = text(row[labelKey]);
    if (row[labelKey]) label.textContent = hostOrPath(row[labelKey]);
    else localize(label, "Direct / unknown");
    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${Math.max(4, (Number(row[valueKey] || 0) / max) * 100)}%`;
    track.appendChild(fill);
    const value = document.createElement("strong");
    value.textContent = formatNumber(row[valueKey]);
    line.append(label, track, value);
    container.appendChild(line);
  });
}

function renderRecent(rows) {
  els.recentTable.innerHTML = "";
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 9;
    localize(td, "No visits recorded yet.");
    tr.appendChild(td);
    els.recentTable.appendChild(tr);
    return;
  }
  rows.forEach(row => {
    const tr = document.createElement("tr");
    const location = [row.city, row.region, row.country].filter(Boolean).join(", ");
    [
      row.created_at,
      row.ip_address,
      row.page_path,
      row.referrer,
      location,
      row.timezone,
      row.language,
      row.screen,
      row.user_agent,
    ].forEach((value, index) => {
      const td = cell(value);
      if (!value && index === 3) localize(td, "Direct / unknown");
      if (!value && index === 4) localize(td, "Unknown");
      tr.appendChild(td);
    });
    els.recentTable.appendChild(tr);
  });
}

async function loadAnalytics() {
  const days = els.days.value || "7";
  const token = els.token.value.trim();
  localStorage.setItem("cell-ai-data-analytics-days", days);
  if (token) localStorage.setItem("cell-ai-data-analytics-token", token);
  updatedAt = null;
  localize(els.status, "Loading analytics...");
  const headers = token ? { "X-Analytics-Token": token } : {};
  const response = await fetch(`${API_BASE}/analytics/summary?days=${encodeURIComponent(days)}`, { headers });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.message || "");
  }
  els.totalVisits.textContent = formatNumber(data.totals?.visits);
  els.uniqueVisitors.textContent = formatNumber(data.totals?.unique_visitors);
  els.uniqueIps.textContent = formatNumber(data.totals?.unique_ips);
  els.recentCount.textContent = formatNumber(data.recent?.length);
  renderBars(els.dailyBars, data.daily || [], "day", "visits");
  renderBars(els.pages, data.topPages || [], "page", "visits");
  renderBars(els.referrers, data.referrers || [], "referrer", "visits");
  renderBars(els.locations, data.locations || [], "location", "visits");
  renderRecent(data.recent || []);
  updatedAt = new Date();
  privacyNote = data.privacyNote || "";
  renderUpdatedStatus();
}

els.days.value = localStorage.getItem("cell-ai-data-analytics-days") || els.days.value;
els.token.value = localStorage.getItem("cell-ai-data-analytics-token") || "";
els.refresh.addEventListener("click", () => loadAnalytics().catch(renderError));
els.days.addEventListener("change", () => loadAnalytics().catch(renderError));
window.addEventListener("cell-language-change", () => {
  if (updatedAt) renderUpdatedStatus();
});

loadAnalytics().catch(renderError);

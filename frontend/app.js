const API_BASE = '/api';

let allShowtimes = [];
let lastUpdated = {};
let staleVenues = [];

// ── Initialise ────────────────────────────────────────────────────────────────
async function init() {
  try {
    const res = await fetch(`${API_BASE}/showtimes`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    allShowtimes = data.showtimes || [];
    lastUpdated = data.last_updated || {};
    staleVenues = data.stale_venues || [];
  } catch (err) {
    document.getElementById('loading').textContent = `Error loading showtimes: ${err.message}`;
    return;
  }

  document.getElementById('loading').classList.add('hidden');
  populateDateFilter();
  renderStaleWarning();
  renderFooter();
  render();

  document.getElementById('groupFilter').addEventListener('change', render);
  document.getElementById('dayFilter').addEventListener('change', render);
  document.getElementById('venueFilter').addEventListener('change', render);
}

// ── Date filter options ────────────────────────────────────────────────────────
function populateDateFilter() {
  const sel = document.getElementById('dayFilter');
  // Collect unique dates from data
  const dates = [...new Set(allShowtimes.map(s => s.show_date))].sort();
  dates.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = formatDateLabel(d);
    sel.appendChild(opt);
  });
}

// ── Filtering ─────────────────────────────────────────────────────────────────
function getFilteredShowtimes() {
  const group = document.getElementById('groupFilter').value;
  const dayVal = document.getElementById('dayFilter').value;
  const venueVal = document.getElementById('venueFilter').value;
  const today = todayISO();

  return allShowtimes.filter(s => {
    if (venueVal !== 'all' && s.venue !== venueVal) return false;
    if (dayVal === 'today') return s.show_date === today;
    if (dayVal === 'week') return s.show_date >= today && s.show_date <= addDays(today, 6);
    if (dayVal !== 'all') return s.show_date === dayVal;
    return true;
  });
}

// ── Main render ───────────────────────────────────────────────────────────────
function render() {
  const group = document.getElementById('groupFilter').value;
  const filtered = getFilteredShowtimes();
  const container = document.getElementById('showtime-list');

  if (filtered.length === 0) {
    container.innerHTML = '<p style="color:#7f8c8d;padding:32px;font-size:12px;">No showtimes found for the selected filters.</p>';
    return;
  }

  if (group === 'by-movie') {
    container.innerHTML = renderByMovie(filtered);
  } else {
    container.innerHTML = renderByDay(filtered);
  }
}

// ── By-Day view ───────────────────────────────────────────────────────────────
function renderByDay(showtimes) {
  const byDate = groupBy(showtimes, s => s.show_date);
  return [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dateStr, entries]) => {
      const sorted = entries.sort((a, b) => a.show_time.localeCompare(b.show_time));
      return `
        <div class="day" data-date="${dateStr}">
          <h2>${formatDateLabel(dateStr)}</h2>
          ${sorted.map(s => movieRow(s, showtimes)).join('')}
        </div>`;
    }).join('');
}

// ── By-Movie view ─────────────────────────────────────────────────────────────
function renderByMovie(showtimes) {
  const byTitle = groupBy(showtimes, s => s.title);
  return [...byTitle.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([title, entries]) => {
      const sorted = entries.sort((a, b) =>
        a.show_date.localeCompare(b.show_date) || a.show_time.localeCompare(b.show_time)
      );
      return `
        <div class="movie-group">
          <h3>${escHtml(title)}</h3>
          ${sorted.map(s => movieRow(s, showtimes)).join('')}
        </div>`;
    }).join('');
}

// ── Movie row ─────────────────────────────────────────────────────────────────
function movieRow(s, allForContext) {
  const titleHtml = s.film_url
    ? `<a href="${escAttr(s.film_url)}" target="_blank" rel="noopener">${escHtml(s.title)}</a>`
    : `<span class="title-text">${escHtml(s.title)}</span>`;

  // Show Other Times button only if there are other screenings of the same film
  const others = allForContext.filter(x => x.title === s.title && x.id !== s.id);
  const otherTimesBtn = others.length > 0
    ? `<button class="other-times-btn" onclick="showOtherTimes(${JSON.stringify(s.title)}, ${JSON.stringify(s.id)})">Other Times (${others.length})</button>`
    : '';

  // Share button
  const shareUrl = `${window.location.origin}${window.location.pathname}#${s.id}`;
  const shareBtn = `<button class="share-btn" onclick="copyShareLink('${escAttr(s.id)}', this)" title="Copy link">Copy Link</button>`;

  return `
    <div class="movie" id="movie-${s.id}" data-id="${s.id}">
      <span class="movie-title">${titleHtml}</span>
      <div class="movie-info">
        <span class="movie-time">${formatTime(s.show_time)}</span>
        <span class="movie-cinema" data-venue="${escAttr(s.venue)}">${escHtml(s.venue)}</span>
        ${otherTimesBtn}
        ${shareBtn}
      </div>
    </div>`;
}

// ── Other Times dialog ────────────────────────────────────────────────────────
function showOtherTimes(title, currentId) {
  const others = allShowtimes.filter(s => s.title === title);

  const titleEl = document.getElementById('other-times-title');
  const listEl = document.getElementById('other-times-list');
  const dialog = document.getElementById('other-times-dialog');
  const overlay = document.getElementById('dialog-overlay');

  titleEl.textContent = title;
  listEl.innerHTML = others
    .sort((a, b) => a.show_date.localeCompare(b.show_date) || a.show_time.localeCompare(b.show_time))
    .map(s => {
      const isCurrent = s.id === currentId;
      const label = `${formatDateLabel(s.show_date)} · ${formatTime(s.show_time)} · ${s.venue}`;
      const href = s.film_url || '#';
      return `<a class="other-times-link${isCurrent ? ' active' : ''}"
                 href="${escAttr(href)}"
                 target="_blank" rel="noopener"
                 onclick="closeOtherTimes()">${escHtml(label)}</a>`;
    }).join('');

  dialog.classList.remove('hidden');
  overlay.classList.remove('hidden');
}

function closeOtherTimes() {
  document.getElementById('other-times-dialog').classList.add('hidden');
  document.getElementById('dialog-overlay').classList.add('hidden');
}

// ── Share / copy link ─────────────────────────────────────────────────────────
function copyShareLink(id, btn) {
  const url = `${window.location.origin}${window.location.pathname}#movie-${id}`;
  navigator.clipboard.writeText(url).then(() => {
    btn.classList.add('copied');
    setTimeout(() => btn.classList.remove('copied'), 2000);
  }).catch(() => {
    btn.classList.add('error');
    setTimeout(() => btn.classList.remove('error'), 2000);
  });
}

// ── Stale warning ─────────────────────────────────────────────────────────────
function renderStaleWarning() {
  const el = document.getElementById('stale-warning');
  if (staleVenues.length === 0) return;
  el.textContent = `⚠ Data may be outdated for: ${staleVenues.join(', ')}`;
  el.classList.remove('hidden');
}

// ── Footer ────────────────────────────────────────────────────────────────────
function renderFooter() {
  const el = document.getElementById('footer');
  const lines = Object.entries(lastUpdated).map(([venue, ts]) => {
    const d = new Date(ts);
    const fmt = isNaN(d) ? ts : d.toLocaleString();
    return `${venue}: ${fmt}`;
  });
  el.innerHTML = lines.join('<br>') + '<br><br>Data sourced from SIFF, Northwest Film Forum, and Grand Illusion Cinema.';
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function groupBy(arr, keyFn) {
  const map = new Map();
  for (const item of arr) {
    const key = keyFn(item);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return map;
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function addDays(isoDate, n) {
  const d = new Date(isoDate + 'T00:00:00');
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function formatDateLabel(isoDate) {
  // isoDate = "2026-03-21"
  const d = new Date(isoDate + 'T00:00:00');
  const today = todayISO();
  const tomorrow = addDays(today, 1);
  if (isoDate === today) return `Today · ${d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}`;
  if (isoDate === tomorrow) return `Tomorrow · ${d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}`;
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

function formatTime(isoTime) {
  // isoTime = "19:30:00" or "19:30"
  const [h, m] = isoTime.split(':').map(Number);
  const period = h >= 12 ? 'pm' : 'am';
  const hour = h % 12 || 12;
  return `${hour}:${String(m).padStart(2, '0')}${period}`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(str) {
  return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Hash-based deep link scroll ───────────────────────────────────────────────
function scrollToHash() {
  if (!window.location.hash) return;
  const id = window.location.hash.slice(1);
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('highlight');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
init().then(() => scrollToHash());

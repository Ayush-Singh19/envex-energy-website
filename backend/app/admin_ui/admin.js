/* Envex Energy admin dashboard.
 *
 * Vanilla JS, no build step. Talks to /api/v1 on the same origin; the session is an
 * httpOnly cookie the browser sends automatically.
 *
 * Security: every piece of lead data is rendered through h(), which creates text nodes.
 * innerHTML is used only for the static SVG icons defined below.
 */
'use strict';

const API = '/api/v1';

// ============================================================ icons (static markup)
const ICONS = {
  phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.9.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
  wa: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2a9.9 9.9 0 0 0-8.5 14.98L2 22l5.16-1.5A9.9 9.9 0 1 0 12.04 2zm0 18.1a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.06.89.9-2.98-.2-.31a8.2 8.2 0 1 1 6.84 3.73zm4.5-6.14c-.25-.12-1.46-.72-1.69-.8-.23-.08-.39-.12-.55.12-.16.25-.63.8-.78.97-.14.16-.29.18-.53.06-.25-.12-1.04-.38-1.98-1.22-.73-.65-1.23-1.46-1.37-1.7-.14-.25-.02-.38.11-.5.11-.11.25-.29.37-.43.12-.15.16-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.55-1.33-.76-1.82-.2-.48-.4-.41-.55-.42h-.47a.9.9 0 0 0-.65.3c-.22.25-.86.84-.86 2.05s.88 2.38 1 2.54c.12.17 1.73 2.64 4.2 3.7.59.25 1.05.4 1.4.52.59.19 1.13.16 1.55.1.47-.07 1.46-.6 1.66-1.18.21-.58.21-1.07.15-1.18-.06-.1-.22-.16-.47-.28z"/></svg>',
  mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 5-5m-5 5-5-5M4 21h16"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
  today: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
  list: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
};
function icon(name, label) {
  const s = document.createElement('span');
  s.className = 'icon';
  s.innerHTML = ICONS[name]; // static SVG from the table above, never user data
  if (label) { s.setAttribute('role', 'img'); s.setAttribute('aria-label', label); }
  else s.setAttribute('aria-hidden', 'true');
  return s;
}

// ============================================================ DOM helper
// Children that aren't Nodes become text nodes, so lead data can never become markup.
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'value') el.value = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

// ============================================================ API client
class ApiError extends Error {
  constructor(status, code, message, fields) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields || {};
  }
}
async function api(path, { method = 'GET', body } = {}) {
  let res;
  try {
    res = await fetch(API + path, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'network', 'Can’t reach the server. Check your internet connection and try again.');
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON error page */ }
  if (!res.ok) {
    const err = (data && data.error) || {};
    if (res.status === 401 && path !== '/auth/login') sessionEnded(err.message);
    if (res.status === 403 && err.code === 'password_change_required') openPasswordModal(true);
    throw new ApiError(res.status, err.code || 'error', err.message || 'Something went wrong. Please try again.', err.fields);
  }
  return data;
}

// ============================================================ dates & formatting
const DAY = 86400000;
const startOfDay = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
const addDays = (n) => { const x = startOfDay(new Date()); x.setDate(x.getDate() + n); return x; };
const daysFromToday = (d) => Math.round((startOfDay(d) - startOfDay(new Date())) / DAY);
const parseDay = (s) => { if (!s) return null; const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const fmtDate = (d) => d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
const fmtDateTime = (d) => d.toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' });
function ago(iso) {
  const d = new Date(iso);
  const m = Math.round((Date.now() - d) / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m} min ago`;
  const days = -daysFromToday(d);
  if (days === 0) return `${Math.round(m / 60)} h ago`;
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return fmtDate(d);
}
function waiting(iso) {
  const m = Math.round((Date.now() - new Date(iso)) / 60000);
  if (m < 60) return `waiting ${Math.max(m, 1)} min`;
  const hrs = Math.round(m / 60);
  if (hrs < 24) return `waiting ${hrs} h`;
  const days = Math.round(hrs / 24);
  return `waiting ${days} day${days > 1 ? 's' : ''}`;
}
function followInfo(s) {
  const d = parseDay(s);
  if (!d) return null;
  const n = daysFromToday(d);
  if (n < 0) return { text: `Overdue · ${-n} day${n < -1 ? 's' : ''}`, cls: 'overdue' };
  if (n === 0) return { text: 'Follow up today', cls: 'today' };
  if (n === 1) return { text: 'Tomorrow', cls: 'later' };
  return { text: fmtDate(d), cls: 'later' };
}
const fmtPhone = (p) => (p.startsWith('+91') && p.length === 13 ? `+91 ${p.slice(3, 8)} ${p.slice(8)}` : p);
const firstName = (n) => n.trim().split(/\s+/)[0];
const project = (l) => (l.system_size ? `${l.project_type} · ${l.system_size}` : l.project_type);

// ============================================================ domain
const STATUSES = [
  { id: 'new', label: 'New' },
  { id: 'called', label: 'Called' },
  { id: 'site_visit', label: 'Site visit' },
  { id: 'quote_sent', label: 'Quote sent' },
  { id: 'won', label: 'Won' },
  { id: 'lost', label: 'Lost' },
  { id: 'not_relevant', label: 'Not relevant' },
];
const statusLabel = (id) => (STATUSES.find((s) => s.id === id) || { label: id }).label;
const CLOSED = new Set(['won', 'lost', 'not_relevant']);
const PAGE_SIZE = 50;

// ============================================================ state
const S = {
  me: null,
  view: 'today',
  tab: 'all',
  q: '',
  today: null,
  list: null, // { items, total, counts, page }
  openId: null,
  detail: null,
  lastFocus: null,
  listSeq: 0,
  detailSeq: 0,
};
const app = document.getElementById('app');
const modalRoot = document.getElementById('modal-root');

let toastTimer;
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3800);
}
const fail = (err) => toast(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');

// ============================================================ contact links
// Real links: tel: opens the phone's dialler, wa.me opens WhatsApp with a ready message.
function callLink(l, cls, withText) {
  return h('a', { class: cls, href: l.tel_url, title: `Call ${fmtPhone(l.phone)}`, 'aria-label': `Call ${l.name}` },
    icon('phone'), withText ? 'Call' : null);
}
function waLink(l, cls, withText) {
  return h('a', { class: cls, href: l.whatsapp_url, target: '_blank', rel: 'noopener noreferrer', title: 'WhatsApp with a ready message', 'aria-label': `WhatsApp ${l.name}` },
    icon('wa'), withText ? 'WhatsApp' : null);
}
function stopRowClick(el) { el.addEventListener('click', (e) => e.stopPropagation()); return el; }
const rowActions = (l) => [stopRowClick(callLink(l, 'icon-btn call')), stopRowClick(waLink(l, 'icon-btn wa'))];

// ============================================================ actions
async function changeLead(id, patch, message) {
  try {
    const detail = await api(`/admin/enquiries/${id}`, { method: 'PATCH', body: patch });
    if (S.openId === id) { S.detail = detail; renderDrawer(); }
    toast(message(detail));
  } catch (err) {
    fail(err);
  }
  await reloadView();
}
const setStatus = (l, status) => changeLead(l.id, { status }, (d) => `${firstName(d.name)} marked as ${statusLabel(status)}.`);
const setFollowUp = (l, day) => changeLead(l.id, { follow_up_date: day ? isoDay(day) : null },
  () => (day ? `Follow-up set for ${fmtDate(day)}.` : 'Follow-up cleared.'));

async function addNote(l, text, button) {
  button.disabled = true;
  try {
    S.detail = await api(`/admin/enquiries/${l.id}/notes`, { method: 'POST', body: { note: text } });
    renderDrawer();
    toast('Note added.');
  } catch (err) {
    fail(err);
    button.disabled = false;
  }
}

async function deleteLead(l) {
  // A native confirm is enough here and keeps the page within its strict CSP.
  if (!window.confirm(`Delete the enquiry from ${l.name} (${l.reference})? This can't be undone.`)) return;
  try {
    await api(`/admin/enquiries/${l.id}`, { method: 'DELETE' });
    closeLead();
    toast(`Enquiry ${l.reference} deleted.`);
    reloadView();
  } catch (err) {
    fail(err);
  }
}

async function openLead(id) {
  if (!S.openId) S.lastFocus = document.activeElement;
  S.openId = id;
  S.detail = null;
  renderDrawer();
  const seq = ++S.detailSeq;
  try {
    const detail = await api(`/admin/enquiries/${id}`);
    if (seq !== S.detailSeq || S.openId !== id) return;
    S.detail = detail;
    renderDrawer();
  } catch (err) {
    if (err.status !== 401) { fail(err); closeLead(); }
  }
}
function closeLead() {
  S.openId = null;
  S.detail = null;
  renderDrawer();
  if (S.lastFocus && document.contains(S.lastFocus)) S.lastFocus.focus();
}

function go(view, tab) {
  S.view = view;
  if (tab) S.tab = tab;
  if (view === 'leads') S.list = null;
  renderShell();
  window.scrollTo(0, 0);
  reloadView();
}

async function exportCsv(button) {
  button.disabled = true;
  try {
    const res = await fetch(`${API}/admin/enquiries/export.csv`, { credentials: 'same-origin' });
    if (res.status === 401) { sessionEnded(); return; }
    if (!res.ok) throw new ApiError(res.status, 'export_failed', 'The export didn’t work. Please try again.');
    const blob = await res.blob();
    const name = (res.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/);
    const a = h('a', { href: URL.createObjectURL(blob), download: name ? name[1] : 'envex-leads.csv' });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    toast('Downloaded. The file opens in Excel.');
  } catch (err) {
    fail(err);
  } finally {
    button.disabled = false;
  }
}

async function signOut() {
  try { await api('/auth/logout', { method: 'POST' }); } catch { /* signing out anyway */ }
  resetState();
  renderLogin();
}
function sessionEnded(message) {
  if (!S.me) return;
  resetState();
  renderLogin(message || 'Your session has ended. Please sign in again.');
}
function resetState() {
  Object.assign(S, { me: null, view: 'today', tab: 'all', q: '', today: null, list: null, openId: null, detail: null });
  delete modalRoot.dataset.forced;
  modalRoot.replaceChildren();
  document.body.classList.remove('locked');
}

// ============================================================ shared UI bits
function statusSelect(l, big) {
  const sel = h('select', {
    class: `status-select st-${l.status}${big ? ' lg' : ''}`,
    'aria-label': `Status for ${l.name}`,
    onchange: (e) => { e.target.className = `status-select st-${e.target.value}${big ? ' lg' : ''}`; setStatus(l, e.target.value); },
  }, STATUSES.map((s) => h('option', { value: s.id, selected: s.id === l.status }, s.label)));
  return stopRowClick(sel);
}
function followChip(l) {
  if (CLOSED.has(l.status)) return null;
  const f = followInfo(l.follow_up_date);
  return f ? h('span', { class: `chip ${f.cls}` }, f.text) : null;
}
const repeatChip = (l) => (l.is_duplicate ? h('span', { class: 'chip repeat', title: 'This phone number sent an enquiry before' }, 'Repeat') : null);

// ============================================================ login
function renderLogin(notice) {
  app.replaceChildren(loginView(notice));
  const email = document.getElementById('email');
  if (email) email.focus();
}
function loginView(notice) {
  const email = h('input', { class: 'input', id: 'email', type: 'email', autocomplete: 'username', required: true, maxlength: '254' });
  const pass = h('input', { class: 'input', id: 'password', type: 'password', autocomplete: 'current-password', required: true, maxlength: '200' });
  const errBox = h('div', { class: 'form-error', role: 'alert', hidden: true });
  const submit = h('button', { class: 'btn btn-primary btn-block', type: 'submit' }, 'Sign in');
  const form = h('form', {
    onsubmit: async (e) => {
      e.preventDefault();
      errBox.hidden = true;
      if (!email.value.trim() || !pass.value) {
        errBox.textContent = 'Enter your email and password.';
        errBox.hidden = false;
        return;
      }
      submit.disabled = true;
      submit.textContent = 'Signing in…';
      try {
        S.me = await api('/auth/login', { method: 'POST', body: { email: email.value.trim(), password: pass.value } });
        enterApp();
      } catch (err) {
        errBox.textContent = err.message;
        errBox.hidden = false;
        pass.value = '';
        pass.focus();
        submit.disabled = false;
        submit.textContent = 'Sign in';
      }
    },
  },
    notice ? h('div', { class: 'login-notice', role: 'status' }, notice) : null,
    errBox,
    h('div', { class: 'field' }, h('label', { for: 'email' }, 'Email'), email),
    h('div', { class: 'field' }, h('label', { for: 'password' }, 'Password'), pass),
    submit,
  );
  return h('div', { class: 'login' },
    h('div', { class: 'login-card' },
      h('div', { class: 'brand' }, h('span', { class: 'brand-mark' }, icon('sun')), h('span', { class: 'brand-name' }, 'Envex ', h('span', null, 'Energy'))),
      h('h1', null, 'Sign in to your leads'),
      h('p', { class: 'sub' }, 'Enquiries from the website, in one place.'),
      form,
      h('p', { class: 'login-foot' }, 'After 5 wrong passwords the account locks for 15 minutes.'),
    ),
  );
}

// ============================================================ shell
function renderShell() {
  const navBtn = (view, label, ic) => h('button', {
    type: 'button', 'aria-current': S.view === view ? 'page' : null, onclick: () => go(view),
  }, ic ? icon(ic) : null, label, view === 'today' ? h('span', { class: 'count-pill', 'data-waiting': '', hidden: true }) : null);

  const menu = h('details', { class: 'menu' },
    h('summary', { 'aria-label': 'Account menu' }, (S.me.full_name || S.me.email).slice(0, 1).toUpperCase()),
    h('div', { class: 'menu-pop' },
      h('div', { class: 'who' }, h('b', null, S.me.full_name), h('span', null, S.me.email)),
      h('button', { type: 'button', onclick: (e) => { e.target.closest('details').open = false; openPasswordModal(); } }, 'Change password'),
      h('button', { type: 'button', onclick: signOut }, 'Sign out'),
    ),
  );

  app.replaceChildren(
    h('header', { class: 'topbar' },
      h('div', { class: 'topbar-inner' },
        h('div', { class: 'brand' }, h('span', { class: 'brand-mark' }, icon('sun')), h('span', { class: 'brand-name' }, 'Envex ', h('span', null, 'Energy')), h('span', { class: 'brand-tag' }, 'Leads')),
        h('nav', { class: 'topnav', 'aria-label': 'Main' }, navBtn('today', 'Today'), navBtn('leads', 'All leads')),
        h('div', { class: 'spacer' }),
        menu,
      ),
    ),
    h('main', { id: 'main' }, h('p', { class: 'loading' }, 'Loading…')),
    h('nav', { class: 'bottomnav', 'aria-label': 'Main' }, navBtn('today', 'Today', 'today'), navBtn('leads', 'All leads', 'list')),
    h('div', { id: 'drawer-root' }),
  );
}
function updateWaitingPill(n) {
  document.querySelectorAll('[data-waiting]').forEach((pill) => {
    pill.textContent = n;
    pill.hidden = !n;
    pill.setAttribute('aria-label', `${n} waiting for a call`);
  });
}

async function reloadView() {
  if (!S.me) return;
  try {
    if (S.view === 'today') {
      S.today = await api('/admin/today');
      updateWaitingPill(S.today.kpis.waiting_for_call);
      renderMain();
    } else {
      await loadList({ keepLoaded: true });
    }
  } catch (err) {
    if (err.status !== 401) fail(err);
  }
}

function renderMain() {
  const main = document.getElementById('main');
  if (!main) return;
  if (S.view === 'today') {
    main.replaceChildren(S.today ? todayView(S.today) : h('p', { class: 'loading' }, 'Loading…'));
  } else {
    main.replaceChildren(leadsView());
    renderResults();
  }
}

// ============================================================ today
function todayView(t) {
  const k = t.kpis;
  const kpi = (cls, label, value, hint, onclick) => h('button', { class: `kpi ${cls}`, type: 'button', onclick },
    h('span', { class: 'label' }, label), h('span', { class: 'value' }, value), h('span', { class: 'hint' }, hint));
  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const miniItem = (l, chip, phoneLine) => h('li', { class: 'mini-item' },
    h('button', { class: 'main', type: 'button', onclick: () => openLead(l.id) },
      h('b', null, l.name, l.is_duplicate ? [' ', repeatChip(l)] : null),
      h('span', null, `${project(l)} · ${l.location}`),
      phoneLine ? h('span', { class: 'phone-only wait-line' }, phoneLine) : null,
    ),
    chip,
    h('div', { class: 'acts' }, rowActions(l)),
  );

  return h('div', null,
    h('div', { class: 'page-head' },
      h('div', null,
        h('h1', null, `${greet}, ${firstName(S.me.full_name)}`),
        h('p', null, new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })),
      ),
    ),
    h('div', { class: 'kpis' },
      kpi('blue', 'New this week', k.new_this_week, 'Enquiries in the last 7 days', () => go('leads', 'all')),
      kpi('amber', 'Waiting for a call', k.waiting_for_call, k.waiting_for_call ? 'Nobody has called them yet' : 'All caught up', () => go('leads', 'new')),
      kpi('navy', 'Quotes out', k.quotes_out, 'Waiting for the customer', () => go('leads', 'quote_sent')),
      kpi('green', 'Won this month', k.won_this_month, k.month_label, () => go('leads', 'won')),
    ),
    h('div', { class: 'today-grid' },
      h('section', { class: 'panel-card', 'aria-labelledby': 'h-call' },
        h('header', null, h('div', null, h('h2', { id: 'h-call' }, 'Call these first'), h('p', null, 'New enquiries, longest waiting at the top'))),
        t.call_first.length
          ? h('ul', { class: 'mini-list' }, t.call_first.map((l) => miniItem(l, h('span', { class: 'chip wait desktop-only' }, waiting(l.created_at)), waiting(l.created_at))))
          : h('div', { class: 'empty' }, h('b', null, 'Everyone has been called.'), 'New enquiries will show up here.'),
      ),
      h('section', { class: 'panel-card', 'aria-labelledby': 'h-follow' },
        h('header', null, h('div', null, h('h2', { id: 'h-follow' }, 'Follow-ups'),
          h('p', null, t.later_this_week ? `Due today or overdue. ${t.later_this_week} more later this week.` : 'Due today or overdue'))),
        t.follow_ups.length
          ? h('ul', { class: 'mini-list' }, t.follow_ups.map((l) => {
            const f = followInfo(l.follow_up_date);
            return miniItem(l, h('span', { class: `chip ${f.cls} desktop-only` }, f.cls === 'today' ? 'Today' : f.text), f.cls === 'today' ? 'Due today' : f.text);
          }))
          : h('div', { class: 'empty' }, h('b', null, 'Nothing due today.'), 'Set a follow-up date on a lead to see it here.'),
      ),
    ),
    h('div', { class: 'clicks-line' },
      h('span', null, 'This week on the website:'),
      h('span', null, h('b', null, t.clicks_this_week.call), ' taps on Call'),
      h('span', null, h('b', null, t.clicks_this_week.whatsapp), ' taps on WhatsApp'),
      h('span', null, h('b', null, t.clicks_this_week.quote), ' clicks on Get a Quote'),
    ),
  );
}

// ============================================================ leads
async function loadList({ append = false, keepLoaded = false } = {}) {
  const seq = ++S.listSeq;
  const page = append ? S.list.page + 1 : 1;
  // After an edit, reload as many rows as were on screen so the list doesn't jump.
  const size = keepLoaded && S.list ? Math.min(100, Math.max(PAGE_SIZE, S.list.items.length)) : PAGE_SIZE;
  const params = new URLSearchParams({ status: S.tab, page: String(page), page_size: String(size) });
  if (S.q.trim()) params.set('q', S.q.trim());
  const data = await api(`/admin/enquiries?${params}`);
  if (seq !== S.listSeq) return; // a newer search already answered
  S.list = {
    items: append ? S.list.items.concat(data.items) : data.items,
    total: data.total,
    counts: data.counts,
    page: append ? page : Math.ceil(data.items.length / PAGE_SIZE) || 1,
  };
  updateWaitingPill(data.counts.new || 0);
  if (!document.getElementById('results')) renderMain();
  else { renderTabs(); renderResults(); }
}

let searchTimer;
function leadsView() {
  const search = h('input', {
    class: 'input', type: 'search', value: S.q, placeholder: 'Search name, phone, email or place',
    'aria-label': 'Search leads', maxlength: '100',
    oninput: (e) => {
      S.q = e.target.value;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadList().catch(fail), 250);
    },
  });
  const exportBtn = h('button', { class: 'btn', type: 'button' }, icon('download'), h('span', { class: 'desktop-only' }, 'Export to Excel'), h('span', { class: 'sr-only' }, 'Export to Excel'));
  exportBtn.addEventListener('click', () => exportCsv(exportBtn));

  return h('div', null,
    h('div', { class: 'page-head' },
      h('div', null, h('h1', null, 'All leads'), h('p', null, 'Newest first. Tap a lead to see everything about it.')),
    ),
    h('div', { class: 'toolbar' }, h('div', { class: 'search' }, icon('search'), search), exportBtn),
    h('div', { class: 'tabs', id: 'tabs', role: 'toolbar', 'aria-label': 'Filter by status' }),
    h('div', { id: 'results' }, h('p', { class: 'loading' }, 'Loading…')),
  );
}
function renderTabs() {
  const box = document.getElementById('tabs');
  if (!box) return;
  const counts = (S.list && S.list.counts) || {};
  const tab = (id, label) => h('button', {
    class: 'tab', type: 'button', 'aria-pressed': String(S.tab === id),
    onclick: () => { S.tab = id; S.list = null; renderResults(); renderTabs(); loadList().catch(fail); },
  }, label, h('span', { class: 'n' }, counts[id] ?? ''));
  box.replaceChildren(tab('all', 'All'), ...STATUSES.map((s) => tab(s.id, s.label)));
}
function renderResults() {
  renderTabs();
  const box = document.getElementById('results');
  if (!box) return;
  if (!S.list) { box.replaceChildren(h('p', { class: 'loading' }, 'Loading…')); return; }
  const list = S.list.items;
  if (!list.length) {
    box.replaceChildren(h('div', { class: 'panel-card' }, h('div', { class: 'empty flush' },
      h('b', null, S.q.trim() ? 'No leads match your search.' : 'No leads here yet.'),
      S.q.trim() ? 'Try a name, the last digits of a phone number, or a town.' : 'They will appear as soon as someone enquires.')));
    return;
  }

  const table = h('div', { class: 'table-wrap' },
    h('table', null,
      h('thead', null, h('tr', null,
        h('th', null, 'Lead'), h('th', null, 'Project'), h('th', null, 'Location'), h('th', null, 'Received'),
        h('th', null, 'Follow-up'), h('th', null, 'Status'), h('th', null, h('span', { class: 'sr-only' }, 'Actions')),
      )),
      h('tbody', null, list.map((l) => h('tr', {
        onclick: () => openLead(l.id), tabindex: '0', onkeydown: (e) => { if (e.key === 'Enter' && e.target === e.currentTarget) openLead(l.id); },
      },
        h('td', null,
          h('div', { class: 'name-line' }, h('span', { class: 'name' }, l.name), repeatChip(l)),
          l.company ? h('div', { class: 'sub' }, l.company) : null,
        ),
        h('td', null, l.project_type, l.system_size ? h('div', { class: 'sub' }, l.system_size) : null),
        h('td', null, l.location),
        h('td', { title: fmtDateTime(new Date(l.created_at)) }, ago(l.created_at)),
        h('td', null, followChip(l) || h('span', { class: 'sub' }, '–')),
        h('td', null, statusSelect(l)),
        h('td', null, h('div', { class: 'acts' }, rowActions(l))),
      ))),
    ),
  );

  const cards = h('div', { class: 'cards' }, list.map((l) => h('article', { class: 'lead-card' },
    h('div', { class: 'top' },
      h('button', { class: 'open', type: 'button', onclick: () => openLead(l.id) },
        h('b', null, l.name),
        h('div', { class: 'meta' }, project(l)),
        h('div', { class: 'meta' }, `${l.location} · ${ago(l.created_at)}`),
      ),
      statusSelect(l),
    ),
    (followChip(l) || repeatChip(l)) ? h('div', { class: 'chips' }, followChip(l), repeatChip(l)) : null,
    h('div', { class: 'row-acts' }, callLink(l, 'btn', true), waLink(l, 'btn btn-wa', true)),
  )));

  const more = list.length < S.list.total
    ? h('div', { class: 'more' }, h('button', {
      class: 'btn', type: 'button',
      onclick: (e) => { e.target.disabled = true; loadList({ append: true }).catch(fail); },
    }, `Show more (${S.list.total - list.length} left)`))
    : null;

  // replaceChildren() would render a null as the text "null", so drop empties first.
  box.replaceChildren(...[
    S.q.trim() ? h('p', { class: 'result-count' }, `${S.list.total} lead${S.list.total === 1 ? '' : 's'} found`) : null,
    table, cards, more,
  ].filter(Boolean));
}

// ============================================================ detail drawer
function drawer() {
  const l = S.detail;
  if (!l) {
    return [
      h('div', { class: 'scrim', onclick: closeLead }),
      h('aside', { class: 'drawer', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Lead details' },
        h('div', { class: 'drawer-head' }, h('button', { class: 'icon-btn', type: 'button', id: 'close-drawer', onclick: closeLead }, icon('x', 'Close'))),
        h('p', { class: 'loading' }, 'Loading…'),
      ),
    ];
  }

  const dateInput = h('input', {
    class: 'input', type: 'date', id: 'follow', value: l.follow_up_date || '',
    onchange: (e) => setFollowUp(l, parseDay(e.target.value)),
  });
  const quickDate = (label, n) => h('button', { type: 'button', onclick: () => setFollowUp(l, addDays(n)) }, label);
  const flag = !CLOSED.has(l.status) && followInfo(l.follow_up_date);

  const noteBox = h('textarea', { class: 'textarea', id: 'note', placeholder: 'What happened? e.g. “Called, wants a quote with battery.”', maxlength: '2000' });
  const noteBtn = h('button', { class: 'btn btn-sm btn-primary', type: 'button' }, 'Add note');
  noteBtn.addEventListener('click', () => { const t = noteBox.value.trim(); if (t) addNote(l, t, noteBtn); else noteBox.focus(); });

  return [
    h('div', { class: 'scrim', onclick: closeLead }),
    h('aside', { class: 'drawer', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'lead-name' },
      h('div', { class: 'drawer-head' },
        h('button', { class: 'icon-btn', type: 'button', id: 'close-drawer', onclick: closeLead }, icon('x', 'Close')),
        h('span', { class: 'ref', title: 'Same reference the customer sees in WhatsApp' }, l.reference),
        h('span', { class: 'drawer-when' }, `Received ${fmtDateTime(new Date(l.created_at))}`),
      ),
      h('div', { class: 'drawer-body' },
        h('div', null,
          h('h2', { id: 'lead-name' }, l.name),
          l.company ? h('div', { class: 'company' }, l.company) : null,
        ),
        h('div', { class: 'quick' },
          callLink(l, 'btn btn-primary', true),
          waLink(l, 'btn btn-wa', true),
          h('a', { class: 'btn btn-email', href: l.mailto_url }, icon('mail'), 'Email'),
        ),
        l.original ? h('div', { class: 'notice' },
          h('span', null, `Repeat enquiry. This number also wrote ${ago(l.original.created_at).toLowerCase()}.`),
          h('button', { class: 'link', type: 'button', onclick: () => openLead(l.original.id) }, 'Open earlier enquiry'),
        ) : null,
        l.newer ? h('div', { class: 'notice' },
          h('span', null, `${firstName(l.name)} wrote again ${ago(l.newer.created_at).toLowerCase()}.`),
          h('button', { class: 'link', type: 'button', onclick: () => openLead(l.newer.id) }, 'Open newer enquiry'),
        ) : null,
        h('div', { class: 'two' },
          h('div', { class: 'box' }, h('h3', null, 'Status'), statusSelect(l, true)),
          h('div', { class: 'box' },
            h('h3', null, h('label', { for: 'follow' }, 'Follow-up date')),
            dateInput,
            flag && flag.cls !== 'later' ? h('div', { class: 'follow-flag' }, h('span', { class: `chip ${flag.cls}` }, flag.text)) : null,
            h('div', { class: 'quick-dates' },
              quickDate('Today', 0), quickDate('Tomorrow', 1), quickDate('In 3 days', 3), quickDate('Next week', 7),
              l.follow_up_date ? h('button', { type: 'button', onclick: () => setFollowUp(l, null) }, 'Clear') : null,
            ),
          ),
        ),
        l.message ? h('div', { class: 'box' }, h('h3', null, 'Their message'), h('p', { class: 'message' }, l.message)) : null,
        h('div', { class: 'box' },
          h('h3', null, 'Details'),
          h('dl', { class: 'facts' },
            h('dt', null, 'Phone'), h('dd', null, h('a', { href: l.tel_url }, fmtPhone(l.phone))),
            h('dt', null, 'Email'), h('dd', null, h('a', { href: l.mailto_url }, l.email)),
            h('dt', null, 'Location'), h('dd', null, l.location),
            h('dt', null, 'Project'), h('dd', null, l.project_type),
            h('dt', null, 'System size'), h('dd', null, l.system_size || 'Not given'),
          ),
        ),
        h('div', { class: 'box' },
          h('h3', null, h('label', { for: 'note' }, 'Notes')),
          noteBox,
          h('div', { class: 'note-actions' }, noteBtn),
          l.notes.length ? h('ul', { class: 'note-list' }, l.notes.map((n) => h('li', { class: 'note' },
            h('p', null, n.note),
            h('small', null, fmtDateTime(new Date(n.created_at)), n.admin_name ? [' · ', h('b', null, n.admin_name)] : null),
          ))) : null,
        ),
        h('div', { class: 'box' },
          h('h3', null, 'History'),
          h('ul', { class: 'timeline' }, l.history.map((t) => h('li', null,
            h('div', null, t.text),
            h('small', null, fmtDateTime(new Date(t.at)), t.by ? ` · ${t.by}` : ''),
          ))),
        ),
        h('div', { class: 'box danger-box' },
          h('h3', null, 'Remove data'),
          h('p', { class: 'danger-note' }, 'If the customer asks for their details to be removed, delete the enquiry. This can\u2019t be undone; the history keeps only its reference.'),
          h('button', { class: 'btn btn-danger btn-sm', type: 'button', onclick: () => deleteLead(l) }, 'Delete this enquiry'),
        ),
      ),
    ),
  ];
}
function renderDrawer() {
  const root = document.getElementById('drawer-root');
  if (!root) return;
  const open = !!S.openId;
  const prev = root.querySelector('.drawer');
  const keepScroll = prev && S.detail && prev.dataset.id === S.detail.id ? prev.scrollTop : 0;
  root.replaceChildren(...(open ? drawer() : []));
  document.body.classList.toggle('locked', open);
  if (!open) return;
  const d = root.querySelector('.drawer');
  if (S.detail) d.dataset.id = S.detail.id;
  if (keepScroll) d.scrollTop = keepScroll;
  else document.getElementById('close-drawer').focus();
}

// ============================================================ change password
// A seed password (new account, or reset from the command line) must be replaced before
// anything else: the API refuses admin calls until then, and this modal can't be dismissed.
function enterApp() {
  renderShell();
  if (S.me.must_change_password) openPasswordModal(true);
  else reloadView();
}

function openPasswordModal(forced = false) {
  if (forced && modalRoot.dataset.forced === 'true') return; // already showing
  const field = (id, label, auto) => {
    const input = h('input', { class: 'input', id, type: 'password', autocomplete: auto, maxlength: '200' });
    const err = h('div', { class: 'field-error', hidden: true });
    return { input, err, el: h('div', { class: 'field' }, h('label', { for: id }, label), input, err) };
  };
  const cur = field('pw-cur', 'Current password', 'current-password');
  const nw = field('pw-new', 'New password (at least 12 characters)', 'new-password');
  const cf = field('pw-conf', 'Type the new password again', 'new-password');
  const err = h('div', { class: 'form-error', role: 'alert', hidden: true });
  const submit = h('button', { class: 'btn btn-primary', type: 'submit' }, 'Change password');
  const close = () => { if (!forced) modalRoot.replaceChildren(); };
  const show = (f, msg) => { f.err.textContent = msg; f.err.hidden = !msg; };

  const form = h('form', {
    onsubmit: async (e) => {
      e.preventDefault();
      [cur, nw, cf].forEach((f) => show(f, ''));
      err.hidden = true;
      if (!cur.input.value) return show(cur, 'Enter your current password.');
      if (nw.input.value.length < 12) return show(nw, 'Use at least 12 characters.');
      if (nw.input.value !== cf.input.value) return show(cf, 'The new passwords don’t match.');
      submit.disabled = true;
      try {
        await api('/auth/change-password', { method: 'POST', body: { current_password: cur.input.value, new_password: nw.input.value } });
        delete modalRoot.dataset.forced;
        modalRoot.replaceChildren();
        toast('Password changed. Other devices have been signed out.');
        if (forced) { S.me.must_change_password = false; reloadView(); }
      } catch (ex) {
        submit.disabled = false;
        if (ex.fields && ex.fields.current_password) show(cur, ex.fields.current_password);
        else if (ex.fields && ex.fields.new_password) show(nw, ex.fields.new_password);
        else { err.textContent = ex.message; err.hidden = false; }
      }
    },
  },
    err, cur.el, nw.el, cf.el,
    h('div', { class: 'modal-actions' },
      forced ? h('button', { class: 'btn', type: 'button', onclick: signOut }, 'Sign out') : h('button', { class: 'btn', type: 'button', onclick: close }, 'Cancel'),
      submit),
  );
  modalRoot.replaceChildren(
    h('div', { class: 'scrim modal-scrim', onclick: close }),
    h('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'pw-title' },
      h('h2', { id: 'pw-title' }, forced ? 'Choose a new password' : 'Change password'),
      h('p', { class: 'sub' }, forced
        ? 'This account is using a temporary password. Choose your own to continue. Avoid common words, sequences and the company name.'
        : 'Other devices will be signed out.'),
      form,
    ),
  );
  if (forced) modalRoot.dataset.forced = 'true';
  cur.input.focus();
}

// ============================================================ global handlers & boot
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  if (modalRoot.dataset.forced === 'true') return; // the forced password change can't be skipped
  if (modalRoot.childElementCount) modalRoot.replaceChildren();
  else if (S.openId) closeLead();
});
document.addEventListener('click', (e) => {
  const open = document.querySelector('details.menu[open]');
  if (open && !open.contains(e.target)) open.open = false;
});
// Coming back to the tab after a while: refresh so new leads show up.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && S.me && !S.openId) reloadView();
});

(async function boot() {
  try {
    S.me = await api('/auth/me');
  } catch {
    renderLogin();
    return;
  }
  enterApp();
})();

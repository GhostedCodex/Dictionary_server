/* ── State ─────────────────────────────────────────────────────────────────── */
let token = localStorage.getItem('dict_token') || null;
let role = localStorage.getItem('dict_role') || null;
let username = localStorage.getItem('dict_user') || null;
let allEntries = [];

/* ── API helper ─────────────────────────────────────────────────────────────── */
async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;
    if (body) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
    const r = await fetch(path, opts);
    return { ok: r.ok, status: r.status, data: await r.json() };
}

/* ── Toast ───────────────────────────────────────────────────────────────────── */
let _toastTimer;
function toast(msg, type = 'ok') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'show ' + type;
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => { el.className = ''; }, 2800);
}

/* ── Page switching ──────────────────────────────────────────────────────────── */
function showAuth() {
    document.getElementById('auth-page').style.display = 'grid';
    document.getElementById('app-page').classList.remove('visible');
}
function showApp() {
    document.getElementById('auth-page').style.display = 'none';
    document.getElementById('app-page').classList.add('visible');
    document.getElementById('app-page').style.display = 'flex';
}

/* ── Auth tabs ───────────────────────────────────────────────────────────────── */
document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        document.querySelectorAll('.auth-form').forEach(f => f.style.display = 'none');
        document.getElementById(target + '-form').style.display = 'block';
        document.getElementById('auth-err').classList.remove('show');
    });
});

function authError(msg) {
    const el = document.getElementById('auth-err');
    el.textContent = msg;
    el.classList.add('show');
}

/* ── Signup ──────────────────────────────────────────────────────────────────── */
document.getElementById('signup-btn').addEventListener('click', async () => {
    const u = document.getElementById('su-username').value.trim();
    const p = document.getElementById('su-password').value;
    const p2 = document.getElementById('su-password2').value;
    if (!u || !p) return authError('Please fill in all fields.');
    if (p !== p2) return authError('Passwords do not match.');
    const { ok, data } = await api('POST', '/api/signup', { username: u, password: p });
    if (!ok) return authError(data.error || 'Signup failed.');
    saveSession(data);
    initApp();
});

document.getElementById('su-username').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('su-password').focus(); });
document.getElementById('su-password').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('su-password2').focus(); });
document.getElementById('su-password2').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('signup-btn').click(); });

/* ── Login ───────────────────────────────────────────────────────────────────── */
document.getElementById('login-btn').addEventListener('click', async () => {
    const u = document.getElementById('li-username').value.trim();
    const p = document.getElementById('li-password').value;
    if (!u || !p) return authError('Please fill in all fields.');
    const { ok, data } = await api('POST', '/api/login', { username: u, password: p });
    if (!ok) return authError(data.error || 'Login failed.');
    saveSession(data);
    initApp();
});

document.getElementById('li-username').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('li-password').focus(); });
document.getElementById('li-password').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('login-btn').click(); });

/* ── Session ─────────────────────────────────────────────────────────────────── */
function saveSession(data) {
    token = data.token; role = data.role; username = data.username;
    localStorage.setItem('dict_token', token);
    localStorage.setItem('dict_role', role);
    localStorage.setItem('dict_user', username);
}

function logout() {
    token = role = username = null;
    localStorage.removeItem('dict_token');
    localStorage.removeItem('dict_role');
    localStorage.removeItem('dict_user');
    allEntries = [];
    showAuth();
}

/* ── Init app ────────────────────────────────────────────────────────────────── */
function initApp() {
    // Set username and role in topbar
    document.getElementById('topbar-username').textContent = username;
    const badge = document.getElementById('topbar-badge');
    badge.textContent = role === 'admin' ? 'Admin' : 'User';
    badge.className = 'topbar-user-badge ' + (role === 'admin' ? 'badge-admin' : 'badge-user');

    // Show or hide admin panel
    document.getElementById('admin-panel').style.display = role === 'admin' ? 'block' : 'none';
    // Hide delete column for non-admins
    document.querySelectorAll('.col-del').forEach(el => {
        el.style.display = role === 'admin' ? '' : 'none';
    });

    showApp();
    loadEntries();
    loadServerInfo();
    setInterval(loadEntries, 15000);
}

/* ── Load entries ────────────────────────────────────────────────────────────── */
async function loadEntries() {
    const { ok, data } = await api('GET', '/api/entries');
    if (!ok) {
        if (data.status === 401) { logout(); return; }
        return;
    }
    allEntries = data.entries || [];
    document.getElementById('entry-count').textContent = allEntries.length + ' words';
    renderTable(allEntries);
}

/* ── Render table ────────────────────────────────────────────────────────────── */
function renderTable(entries) {
    const tbody = document.getElementById('entries-body');
    if (!entries.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state"><span>∅</span>No entries found.</td></tr>`;
        return;
    }
    tbody.innerHTML = entries.map(e => {
        const delCell = role === 'admin'
            ? `<td class="td-del col-del"><button class="btn-del" onclick="event.stopPropagation();doDelete('${e.word}')" title="delete">✕</button></td>`
            : `<td class="td-del col-del" style="display:none"></td>`;
        return `
    <tr onclick="selectWord('${e.word}')">
      <td class="td-word">${e.word}</td>
      <td class="td-def">${e.definition}</td>
      <td class="td-ts">${fmt(e.added_at) || '<span class="td-null">—</span>'}</td>
      <td class="td-ts">${fmt(e.updated_at) || '<span class="td-null">—</span>'}</td>
      <td class="td-ts">${fmt(e.last_searched_at) || '<span class="td-null">never</span>'}</td>
      ${delCell}
    </tr>`;
    }).join('');
}

/* ── Filter ──────────────────────────────────────────────────────────────────── */
document.getElementById('filter-input').addEventListener('input', function () {
    const q = this.value.toLowerCase();
    renderTable(allEntries.filter(e =>
        e.word.includes(q) || e.definition.toLowerCase().includes(q)
    ));
});

/* ── Search ──────────────────────────────────────────────────────────────────── */
async function doSearch() {
    const word = document.getElementById('search-input').value.trim();
    if (!word) return;
    const box = document.getElementById('search-result');
    box.className = 'result-box'; box.textContent = 'searching…';
    const { ok, status, data } = await api('GET', `/api/search?word=${encodeURIComponent(word)}`);
    if (status === 404) { box.className = 'result-box missed'; box.textContent = `"${word}" not found`; }
    else if (!ok) { box.className = 'result-box error'; box.textContent = data.error || 'error'; }
    else { box.className = 'result-box found'; box.textContent = data.definition; loadEntries(); }
}

function clearSearch() {
    document.getElementById('search-input').value = '';
    const box = document.getElementById('search-result');
    box.className = 'result-box'; box.textContent = 'Type a word and press Search.';
}

function selectWord(word) {
    document.getElementById('search-input').value = word;
    doSearch();
    document.querySelectorAll('tbody tr').forEach(tr => tr.classList.remove('selected'));
    const rows = document.querySelectorAll('tbody tr');
    rows.forEach(tr => { if (tr.querySelector('.td-word')?.textContent === word) tr.classList.add('selected'); });
}

document.getElementById('search-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

/* ── Add (admin only) ─────────────────────────────────────────────────────────── */
async function doAdd() {
    const word = document.getElementById('add-word').value.trim();
    const def = document.getElementById('add-def').value.trim();
    if (!word || !def) return toast('Word and definition are required.', 'err');
    const { ok, data } = await api('POST', '/api/add', { word, definition: def });
    if (ok) {
        toast(`"${word}" saved.`);
        document.getElementById('add-word').value = '';
        document.getElementById('add-def').value = '';
        loadEntries();
    } else {
        toast(data.error || 'Failed to add.', 'err');
    }
}

document.getElementById('add-word').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('add-def').focus();
});

/* ── Delete (admin only) ──────────────────────────────────────────────────────── */
async function doDelete(word) {
    const { ok, data } = await api('POST', '/api/delete', { word });
    if (ok) { toast(`"${word}" deleted.`); loadEntries(); }
    else toast(data.error || 'Failed to delete.', 'err');
}

/* ── Server info ─────────────────────────────────────────────────────────────── */
async function loadServerInfo() {
    const { ok, data } = await api('GET', '/api/info');
    if (!ok) return;
    document.getElementById('footer-tcp').textContent = `TCP → ${data.server_ip}:${data.dict_port}`;
    document.getElementById('footer-http').textContent = `HTTP → ${data.server_ip}:${data.ui_port}`;
}

/* ── Timestamp formatter ──────────────────────────────────────────────────────── */
function fmt(iso) {
    if (!iso) return null;
    return new Date(iso).toLocaleString(undefined, {
        month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
}

/* ── Boot ────────────────────────────────────────────────────────────────────── */
window.addEventListener('DOMContentLoaded', async () => {
    if (!token) { showAuth(); return; }
    const { ok, data } = await api('GET', '/api/me');
    if (!ok) { logout(); return; }
    username = data.username; role = data.role;
    localStorage.setItem('dict_role', role);
    localStorage.setItem('dict_user', username);
    initApp();
});
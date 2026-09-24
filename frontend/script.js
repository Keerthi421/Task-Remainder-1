/* ── Config & state ─────────────────────────────────────────── */
const API = "";
const token = localStorage.getItem('token');
if (!token) window.location.href = '/login';

let allTasks      = [];
let activeTag     = 'all';
let currentView   = 'list';
let calYear       = new Date().getFullYear();
let calMonth      = new Date().getMonth(); // 0-based
let calFilterDate = null;     // YYYY-MM-DD string or null
let templates     = [];

const $ = id => document.getElementById(id);

function hdr() { return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }; }

function logout() { localStorage.removeItem('token'); window.location.href = '/'; }

/* ── Toast ───────────────────────────────────────────────────── */
let _toastT;
function notify(msg, ms = 3500) {
  clearTimeout(_toastT);
  $('toast').textContent = msg;
  $('toast').style.display = 'block';
  _toastT = setTimeout(() => $('toast').style.display = 'none', ms);
}

/* ── Escape HTML ─────────────────────────────────────────────── */
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Date formatter ──────────────────────────────────────────── */
function fmtDate(d) {
  return new Date(d).toLocaleString('en-IN',{
    month:'short',day:'numeric',year:'numeric',
    hour:'numeric',minute:'2-digit',hour12:true
  }).replace(',',' ·');
}

function isOverdue(task) {
  return task.status === 'pending' && new Date(task.due_date) < new Date();
}

/* ── User / profile ──────────────────────────────────────────── */
async function fetchMe() {
  try {
    const r = await fetch(`${API}/users/me`, { headers: hdr() });
    if (r.status === 401) { logout(); return; }
    const u = await r.json();
    const el = $('nav-email');
    if (el) el.textContent = u.email;
  } catch(_) {}
}

async function fetchProfile() {
  try {
    const r = await fetch(`${API}/users/profile`, { headers: hdr() });
    if (!r.ok) return;
    const p = await r.json();
    $('nav-pts').textContent = p.points;
    $('nav-lvl').textContent = p.level;
    $('nav-badge').style.display = 'inline-flex';
  } catch(_) {}
}

/* ── Stats ───────────────────────────────────────────────────── */
async function fetchStats() {
  try {
    const r = await fetch(`${API}/tasks/stats`, { headers: hdr() });
    if (!r.ok) return;
    const s = await r.json();
    $('s-total').textContent  = s.total;
    $('s-pend').textContent   = s.pending;
    $('s-today').textContent  = s.completed_today;
    $('s-over').textContent   = s.overdue;
    $('s-streak').textContent = s.streak + (s.streak > 0 ? ' 🔥' : '');
    $('nav-pts').textContent  = s.points;
    $('nav-lvl').textContent  = s.level;
    $('nav-badge').style.display = 'inline-flex';
  } catch(_) {}
}

/* ── Templates ───────────────────────────────────────────────── */
async function fetchTemplates() {
  try {
    const r = await fetch(`${API}/templates`, { headers: hdr() });
    if (!r.ok) return;
    templates = await r.json();
    renderTemplates();
  } catch(_) {}
}

function renderTemplates() {
  const bar = $('tmpl-bar');
  if (!templates.length) { bar.style.display = 'none'; return; }
  bar.style.display = 'flex';
  bar.innerHTML = templates.map(t => `
    <span class="tmpl-chip" onclick="loadTemplate(${t.id})">
      ${esc(t.name)}
      <span class="del" onclick="event.stopPropagation();deleteTemplate(${t.id})">✕</span>
    </span>`).join('');
}

function loadTemplate(id) {
  const t = templates.find(x => x.id === id);
  if (!t) return;
  $('title').value       = t.title;
  $('description').value = t.description;
  $('priority').value    = t.priority;
  $('tags').value        = t.tags;
  // reminder chips
  const mins = (t.reminder_minutes||'0').split(',').map(Number);
  document.querySelectorAll('.reminder-chip input').forEach(cb => {
    cb.checked = mins.includes(Number(cb.value));
    cb.closest('.reminder-chip').classList.toggle('active', cb.checked);
  });
  // sub-tasks
  try {
    const subs = JSON.parse(t.sub_tasks || '[]');
    const builder = $('subtask-builder');
    builder.innerHTML = '';
    subs.forEach(s => addSubtaskField(s.text));
  } catch(_) {}
  notify('Template loaded.');
}

async function deleteTemplate(id) {
  try {
    const r = await fetch(`${API}/templates/${id}`, { method:'DELETE', headers: hdr() });
    if (r.ok) { templates = templates.filter(t => t.id !== id); renderTemplates(); notify('Template deleted.'); }
  } catch(_) {}
}

async function saveAsTemplate() {
  const name = prompt('Template name:', $('title').value || 'My Template');
  if (!name) return;
  const mins = getSelectedReminders();
  const subs = getSubtasks();
  const body = {
    name, title: $('title').value, description: $('description').value,
    priority: $('priority').value, tags: $('tags').value,
    reminder_minutes: mins, sub_tasks: subs
  };
  try {
    const r = await fetch(`${API}/templates`, { method:'POST', headers: hdr(), body: JSON.stringify(body) });
    if (r.ok) { const t = await r.json(); templates.push(t); renderTemplates(); notify('✓ Template saved.'); }
    else notify('Failed to save template.');
  } catch(_) { notify('Error.'); }
}

/* ── Sub-task builder ────────────────────────────────────────── */
function addSubtaskField(value = '') {
  const builder = $('subtask-builder');
  const div = document.createElement('div');
  div.style.cssText = 'display:flex;gap:6px;align-items:center;';
  div.innerHTML = `<input type="text" class="subtask-field" placeholder="Checklist item" value="${esc(value)}" style="flex:1;">
    <button type="button" onclick="this.parentNode.remove()" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:16px;padding:0 4px;">✕</button>`;
  builder.appendChild(div);
}

function getSubtasks() {
  return [...document.querySelectorAll('.subtask-field')]
    .map((el, i) => ({ id: i+1, text: el.value.trim(), done: false }))
    .filter(s => s.text);
}

function getSelectedReminders() {
  return [...document.querySelectorAll('.reminder-chip input:checked')].map(cb => Number(cb.value));
}

/* ── Natural language ────────────────────────────────────────── */
function toggleNL() {
  const on = $('nl-toggle').checked;
  $('nl-area').style.display = on ? 'block' : 'none';
}

async function parseNL() {
  const text = $('nl-input').value.trim();
  if (!text) return;
  const btn = $('nl-btn'), status = $('nl-status');
  btn.disabled = true; btn.textContent = 'Parsing…';
  status.textContent = '';
  try {
    const r = await fetch(`${API}/tasks/parse`, {
      method: 'POST', headers: hdr(), body: JSON.stringify({ text })
    });
    if (r.status === 503) { status.textContent = 'AI not configured (set ANTHROPIC_API_KEY)'; return; }
    const d = await r.json();
    if (d.title)       $('title').value       = d.title;
    if (d.description) $('description').value = d.description;
    if (d.due_date)    $('due_date').value     = d.due_date.slice(0,16);
    if (d.priority)    $('priority').value     = d.priority;
    if (d.tags)        $('tags').value         = d.tags;
    status.textContent = '✓ Filled in';
    $('nl-toggle').checked = false;
    toggleNL();
  } catch(e) {
    status.textContent = 'Error';
  } finally {
    btn.disabled = false; btn.textContent = '✨ Parse';
  }
}

async function aiPriority() {
  const title = $('title').value.trim();
  if (!title) { notify('Enter a title first.'); return; }
  const btn = $('ai-btn');
  btn.disabled = true;
  try {
    const r = await fetch(`${API}/tasks/suggest-priority`, {
      method: 'POST', headers: hdr(),
      body: JSON.stringify({ title, description: $('description').value })
    });
    if (r.status === 503) { notify('Set ANTHROPIC_API_KEY to use AI suggestions.'); return; }
    const d = await r.json();
    if (d.priority) { $('priority').value = d.priority; notify(`AI suggests: ${d.priority} priority`); }
  } catch(_) { notify('AI suggestion failed.'); }
  finally { btn.disabled = false; }
}

/* ── CSV import ──────────────────────────────────────────────── */
async function importCSV(input) {
  const file = input.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  notify('Importing…');
  try {
    const r = await fetch(`${API}/tasks/import`, {
      method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData
    });
    const d = await r.json();
    if (r.ok) { notify(`✓ Imported ${d.length} task${d.length !== 1 ? 's' : ''}.`); fetchTasks(); }
    else notify('Import error: ' + (d.detail || 'Unknown'));
  } catch(_) { notify('Import failed.'); }
  input.value = '';
}

/* ── Tag filter ──────────────────────────────────────────────── */
function buildTagFilter() {
  const tags = new Set();
  allTasks.forEach(t => (t.tags || '').split(',').map(x => x.trim()).filter(Boolean).forEach(x => tags.add(x)));
  const bar = $('tag-filter');
  const existing = new Set([...bar.querySelectorAll('.tag-chip:not([data-tag="all"])')].map(el => el.dataset.tag));
  tags.forEach(tag => {
    if (!existing.has(tag)) {
      const chip = document.createElement('span');
      chip.className = 'tag-chip';
      chip.dataset.tag = tag;
      chip.textContent = tag;
      chip.onclick = () => filterTag(chip);
      bar.appendChild(chip);
    }
  });
}

function filterTag(el) {
  document.querySelectorAll('.tag-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  activeTag = el.dataset.tag;
  calFilterDate = null;
  renderTasks();
}

function getFilteredTasks() {
  let tasks = [...allTasks];
  if (activeTag !== 'all') {
    tasks = tasks.filter(t => (t.tags || '').split(',').map(x => x.trim()).includes(activeTag));
  }
  if (calFilterDate) {
    tasks = tasks.filter(t => t.due_date && t.due_date.startsWith(calFilterDate));
  }
  return tasks.sort((a,b) => a.sort_order - b.sort_order || new Date(a.due_date) - new Date(b.due_date));
}

/* ── Task fetching ───────────────────────────────────────────── */
async function fetchTasks() {
  try {
    const r = await fetch(`${API}/tasks`, { headers: hdr() });
    if (r.status === 401) { logout(); return; }
    if (!r.ok) throw new Error(`API ${r.status}`);
    allTasks = await r.json();
    // Cache in localStorage
    try { localStorage.setItem('tasks_cache', JSON.stringify({ ts: Date.now(), data: allTasks })); } catch(_) {}
    buildTagFilter();
    renderTasks();
    renderCalendar();
    fetchStats();
  } catch(e) {
    // Fallback to cache
    try {
      const cached = JSON.parse(localStorage.getItem('tasks_cache') || 'null');
      if (cached) { allTasks = cached.data; renderTasks(); renderCalendar(); const ago = Math.round((Date.now()-cached.ts)/60000); notify(`Offline — showing data from ${ago}m ago`); }
      else $('tasks-container').innerHTML = `<div class="empty-state"><span class="empty-icon">⚠</span>${esc(e.message)}</div>`;
    } catch(_) {}
  }
}

/* ── Task rendering ──────────────────────────────────────────── */
function renderTasks() {
  const tasks = getFilteredTasks();
  const countEl = $('task-count');
  if (countEl) countEl.textContent = `${tasks.length} task${tasks.length !== 1 ? 's' : ''}`;

  if (!tasks.length) {
    $('tasks-container').innerHTML = `<div class="empty-state"><span class="empty-icon">📋</span>No tasks here. Add one on the left.</div>`;
    return;
  }

  $('tasks-container').innerHTML = tasks.map(task => {
    const overdue = isOverdue(task);
    let subs = [];
    try { subs = JSON.parse(task.sub_tasks || '[]'); } catch(_) {}
    const doneCount = subs.filter(s => s.done).length;
    const subtaskSummary = subs.length ? `<button class="subtask-toggle" onclick="toggleSubtasks(${task.id})">☰ ${doneCount}/${subs.length} done</button>` : '';
    const subtaskList = subs.length ? `
      <div class="subtask-list" id="subs-${task.id}" style="display:none;">
        ${subs.map((s,i) => `<label class="subtask-item">
          <input type="checkbox" ${s.done?'checked':''} onchange="toggleSubtask(${task.id},${i})">
          <span class="${s.done?'done':''}">${esc(s.text)}</span></label>`).join('')}
      </div>` : '';

    return `<div class="task-card ${task.priority}${task.status==='completed'?' completed':''}" data-id="${task.id}">
      <span class="drag-handle" title="Drag to reorder">⠿</span>
      <div class="task-info">
        <p class="task-title${task.status==='completed'?' done':''}">${esc(task.title)}</p>
        ${task.description ? `<p class="task-desc">${esc(task.description)}</p>` : ''}
        <div class="task-meta">
          <span class="meta-tag">📅 ${fmtDate(task.due_date)}</span>
          <span class="meta-tag priority-${task.priority}">${task.priority}</span>
          ${overdue ? '<span class="meta-tag overdue-tag">⚠ Overdue</span>' : ''}
          ${task.assigned_to ? `<span class="meta-tag">👤 ${esc(task.assigned_to)}</span>` : ''}
          ${(task.tags||'').split(',').filter(x=>x.trim()).map(tag=>`<span class="meta-tag">${esc(tag.trim())}</span>`).join('')}
        </div>
        ${subtaskSummary}
        ${subtaskList}
      </div>
      <div class="task-actions">
        <button class="icon-btn" title="${task.status==='pending'?'Mark complete':'Mark pending'}"
          onclick="toggleStatus(${task.id},'${task.status==='pending'?'completed':'pending'}')">${task.status==='pending'?'✔':'↺'}</button>
        <button class="icon-btn share" title="Share link" onclick="shareTask(${task.id})">🔗</button>
        <button class="icon-btn delete" title="Delete" onclick="deleteTask(${task.id})">✕</button>
      </div>
    </div>`;
  }).join('');

  // Drag-to-reorder with SortableJS
  if (typeof Sortable !== 'undefined') {
    Sortable.create($('tasks-container'), {
      animation: 150,
      handle: '.drag-handle',
      onEnd: async (evt) => {
        const cards = [...$('tasks-container').querySelectorAll('.task-card')];
        const items = cards.map((el, i) => ({ id: Number(el.dataset.id), sort_order: i }));
        try {
          await fetch(`${API}/tasks/reorder`, { method:'POST', headers: hdr(), body: JSON.stringify(items) });
          items.forEach(({ id, sort_order }) => { const t = allTasks.find(x => x.id === id); if(t) t.sort_order = sort_order; });
        } catch(_) {}
      }
    });
  }
}

/* ── Sub-task interactions ───────────────────────────────────── */
function toggleSubtasks(taskId) {
  const el = $(`subs-${taskId}`);
  if (el) el.style.display = el.style.display === 'none' ? 'flex' : 'none';
}

async function toggleSubtask(taskId, index) {
  const task = allTasks.find(t => t.id === taskId);
  if (!task) return;
  let subs = [];
  try { subs = JSON.parse(task.sub_tasks || '[]'); } catch(_) { return; }
  subs[index].done = !subs[index].done;
  try {
    const r = await fetch(`${API}/tasks/${taskId}`, {
      method: 'PATCH', headers: hdr(), body: JSON.stringify({ sub_tasks: subs })
    });
    if (r.ok) { task.sub_tasks = JSON.stringify(subs); renderTasks(); }
  } catch(_) {}
}

/* ── Task mutations ──────────────────────────────────────────── */
$('task-form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = $('submit-btn');
  btn.disabled = true; btn.textContent = 'Scheduling…';
  const mins = getSelectedReminders();
  const body = {
    title:            $('title').value,
    description:      $('description').value,
    due_date:         $('due_date').value,
    priority:         $('priority').value,
    tags:             $('tags').value,
    assigned_to:      $('assigned_to').value || null,
    reminder_minutes: mins.length ? mins : [0],
    sub_tasks:        getSubtasks(),
  };
  try {
    const r = await fetch(`${API}/tasks`, { method:'POST', headers: hdr(), body: JSON.stringify(body) });
    if (r.ok) {
      notify('✓ Reminder scheduled!');
      $('task-form').reset();
      $('subtask-builder').innerHTML = '';
      document.querySelectorAll('.reminder-chip').forEach(c => { c.classList.remove('active'); c.querySelector('input').checked = false; });
      document.getElementById('rc-0').querySelector('input').checked = true;
      document.getElementById('rc-0').classList.add('active');
      fetchTasks();
    } else {
      const err = await r.json().catch(() => ({ detail:'Failed' }));
      notify('Error: ' + (err.detail || 'Failed'));
    }
  } catch(_) { notify('Network error.'); }
  finally { btn.disabled = false; btn.textContent = 'Schedule Reminder'; }
});

async function toggleStatus(id, newStatus) {
  try {
    const r = await fetch(`${API}/tasks/${id}`, {
      method:'PATCH', headers: hdr(), body: JSON.stringify({ status: newStatus })
    });
    if (r.ok) { notify(`Marked as ${newStatus}.`); fetchTasks(); }
  } catch(_) { notify('Error.'); }
}

async function deleteTask(id) {
  if (!confirm('Delete this reminder?')) return;
  try {
    const r = await fetch(`${API}/tasks/${id}`, { method:'DELETE', headers: hdr() });
    if (r.ok) { notify('Deleted.'); allTasks = allTasks.filter(t => t.id !== id); renderTasks(); renderCalendar(); fetchStats(); }
  } catch(_) { notify('Error.'); }
}

/* ── Share link ──────────────────────────────────────────────── */
async function shareTask(id) {
  try {
    const r = await fetch(`${API}/tasks/${id}/share`, { method:'POST', headers: hdr() });
    if (!r.ok) { notify('Could not generate link.'); return; }
    const d = await r.json();
    const url = `${location.origin}${d.public_url}`;
    $('share-url').value = url;
    $('share-modal').style.display = 'flex';
  } catch(_) { notify('Error.'); }
}

function closeShare(e) { if (e.target === $('share-modal')) $('share-modal').style.display = 'none'; }

function copyShareUrl() {
  $('share-url').select();
  navigator.clipboard.writeText($('share-url').value).then(() => notify('✓ Link copied!')).catch(() => notify('Copy manually from the box.'));
}

/* ── View toggle ─────────────────────────────────────────────── */
function setView(v) {
  currentView = v;
  $('list-view').style.display = v === 'list' ? 'block' : 'none';
  $('cal-view').style.display  = v === 'calendar' ? 'block' : 'none';
  $('btn-list').classList.toggle('active', v === 'list');
  $('btn-cal').classList.toggle('active', v === 'calendar');
  if (v === 'calendar') renderCalendar();
}

/* ── Calendar ────────────────────────────────────────────────── */
function calNav(dir) { calMonth += dir; if (calMonth > 11) { calMonth = 0; calYear++; } if (calMonth < 0) { calMonth = 11; calYear--; } renderCalendar(); }

function renderCalendar() {
  const label = $('cal-month-label');
  const grid  = $('cal-grid');
  if (!label || !grid) return;

  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  label.textContent = `${monthNames[calMonth]} ${calYear}`;

  // Remove old day cells (keep the 7 header cells)
  [...grid.querySelectorAll('.cal-day')].forEach(el => el.remove());

  const firstDay = new Date(calYear, calMonth, 1).getDay(); // 0=Sun
  const offset   = (firstDay + 6) % 7;                      // Mon=0
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const today    = new Date();

  // Build day → tasks map
  const taskMap = {};
  allTasks.forEach(t => {
    const d = new Date(t.due_date);
    if (d.getFullYear() === calYear && d.getMonth() === calMonth) {
      const key = d.getDate();
      if (!taskMap[key]) taskMap[key] = [];
      taskMap[key].push(t);
    }
  });

  // Blank cells before month start
  for (let i = 0; i < offset; i++) {
    const blank = document.createElement('div');
    blank.className = 'cal-day other-month';
    grid.appendChild(blank);
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const isToday = today.getFullYear()===calYear && today.getMonth()===calMonth && today.getDate()===d;
    const dateStr = `${calYear}-${String(calMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const isSelected = calFilterDate === dateStr;
    const cell = document.createElement('div');
    cell.className = `cal-day${isToday?' today':''}${isSelected?' selected':''}`;
    cell.dataset.date = dateStr;
    cell.innerHTML = `<div class="cal-day-num">${d}</div><div class="cal-dots">${
      (taskMap[d]||[]).slice(0,6).map(t => `<span class="cal-dot ${t.priority}" title="${esc(t.title)}"></span>`).join('')
    }</div>`;
    cell.onclick = () => {
      calFilterDate = calFilterDate === dateStr ? null : dateStr;
      if (calFilterDate) { activeTag = 'all'; document.querySelectorAll('.tag-chip').forEach(c=>c.classList.remove('active')); document.querySelector('.tag-chip[data-tag="all"]').classList.add('active'); }
      renderCalendar();
      setView('list');
      renderTasks();
    };
    grid.appendChild(cell);
  }
}

/* ── Init ────────────────────────────────────────────────────── */
fetchMe();
fetchProfile();
fetchTasks();
fetchTemplates();
setInterval(() => { fetchTasks(); fetchStats(); }, 30000);

const API_BASE = "";
const taskForm = document.getElementById('task-form');
const tasksContainer = document.getElementById('tasks-container');
const toast = document.getElementById('toast');
const token = localStorage.getItem('token');

if (!token) window.location.href = '/login';

function getHeaders() {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
}

function logout() {
  localStorage.removeItem('token');
  window.location.href = '/';
}

/* ── Toast ── */
let toastTimer;
function notify(message, duration = 3200) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.style.display = 'block';
  toastTimer = setTimeout(() => { toast.style.display = 'none'; }, duration);
}

/* ── Fetch current user (to display email in nav) ── */
async function fetchMe() {
  try {
    const res = await fetch(`${API_BASE}/users/me`, { headers: getHeaders() });
    if (res.status === 401) { logout(); return; }
    if (res.ok) {
      const user = await res.json();
      const el = document.getElementById('nav-email');
      if (el) el.textContent = user.email;
    }
  } catch (_) {}
}

/* ── Date formatter ── */
function fmtDate(dateString) {
  return new Date(dateString).toLocaleString('en-IN', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: true
  }).replace(',', ' ·');
}

/* ── Render tasks ── */
function renderPriorityTag(priority) {
  return `<span class="meta-tag priority-${priority}">${priority}</span>`;
}

function renderStatusTag(status) {
  const icon = status === 'completed' ? '✓' : '⏳';
  return `<span class="meta-tag">${icon} ${status}</span>`;
}

/* ── Fetch and display tasks ── */
async function fetchTasks() {
  try {
    const response = await fetch(`${API_BASE}/tasks`, { headers: getHeaders() });
    if (response.status === 401) { logout(); return; }
    if (!response.ok) throw new Error(`API Error ${response.status}`);

    const tasks = await response.json();

    // Update count badge
    const countEl = document.getElementById('task-count');
    if (countEl) countEl.textContent = `${tasks.length} task${tasks.length !== 1 ? 's' : ''}`;

    if (tasks.length === 0) {
      tasksContainer.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">📋</span>
          No tasks yet. Add one on the left to get started.
        </div>`;
      return;
    }

    const sorted = [...tasks].sort((a, b) => new Date(a.due_date) - new Date(b.due_date));

    tasksContainer.innerHTML = sorted.map(task => `
      <div class="task-card ${task.priority}${task.status === 'completed' ? ' completed' : ''}">
        <div class="task-info">
          <p class="task-title">${escHtml(task.title)}</p>
          ${task.description ? `<p class="task-desc">${escHtml(task.description)}</p>` : ''}
          <div class="task-meta">
            <span class="meta-tag">📅 ${fmtDate(task.due_date)}</span>
            ${renderPriorityTag(task.priority)}
            ${renderStatusTag(task.status)}
          </div>
        </div>
        <div class="task-actions">
          <button class="icon-btn" title="${task.status === 'pending' ? 'Mark complete' : 'Mark pending'}"
            onclick="toggleTaskStatus(${task.id}, '${task.status === 'pending' ? 'completed' : 'pending'}')">
            ${task.status === 'pending' ? '✔' : '↺'}
          </button>
          <button class="icon-btn delete" title="Delete" onclick="deleteTask(${task.id})">✕</button>
        </div>
      </div>
    `).join('');
  } catch (error) {
    console.error('Error fetching tasks:', error);
    tasksContainer.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">⚠</span>
        ${escHtml(error.message)}
      </div>`;
  }
}

/* ── HTML escaping ── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Create task ── */
taskForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const submitBtn = taskForm.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Scheduling…';

  const taskData = {
    title:       document.getElementById('title').value,
    description: document.getElementById('description').value,
    due_date:    document.getElementById('due_date').value,
    priority:    document.getElementById('priority').value
  };

  try {
    const response = await fetch(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(taskData)
    });

    if (response.ok) {
      notify('✓ Reminder scheduled successfully!');
      taskForm.reset();
      fetchTasks();
    } else {
      const err = await response.json().catch(() => ({ detail: 'Failed to create task' }));
      notify('Error: ' + (err.detail || 'Failed to create task'));
    }
  } catch (_) {
    notify('Network error. Is the backend running?');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Schedule Reminder';
  }
});

/* ── Delete task ── */
async function deleteTask(id) {
  if (!confirm('Delete this reminder?')) return;
  try {
    const res = await fetch(`${API_BASE}/tasks/${id}`, { method: 'DELETE', headers: getHeaders() });
    if (res.ok) { notify('Reminder deleted.'); fetchTasks(); }
    else notify('Could not delete reminder.');
  } catch (_) { notify('Network error.'); }
}

/* ── Toggle status ── */
async function toggleTaskStatus(id, newStatus) {
  try {
    const res = await fetch(`${API_BASE}/tasks/${id}`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) { notify(`Marked as ${newStatus}.`); fetchTasks(); }
    else notify('Could not update status.');
  } catch (_) { notify('Network error.'); }
}

/* ── Init ── */
fetchMe();
fetchTasks();
setInterval(fetchTasks, 30000);

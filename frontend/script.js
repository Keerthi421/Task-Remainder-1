const API_BASE = "";
const taskForm = document.getElementById('task-form');
const tasksContainer = document.getElementById('tasks-container');
const toast = document.getElementById('toast');

// Show notification
function notify(message, duration = 3000) {
    toast.textContent = message;
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, duration);
}

// Fetch and display tasks
async function fetchTasks() {
    const formatDate = (dateString) => {
        const options = { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: 'numeric', hour12: true };
        return new Date(dateString).toLocaleString('en-US', options).replace(',', ' •');
    };

    try {
        const response = await fetch(`${API_BASE}/tasks`);
        const tasks = await response.json();

        if (tasks.length === 0) {
            tasksContainer.innerHTML = '<div style="text-align: center; color: var(--text-dim); padding: 2rem;">No tasks found. Add one to get started!</div>';
            return;
        }

        tasksContainer.innerHTML = tasks.sort((a, b) => new Date(a.due_date) - new Date(b.due_date)).map(task => `
            <div class="task-card ${task.priority}">
                <div class="task-info">
                    <h3>${task.title}</h3>
                    <p>${task.description || 'No description provided'}</p>
                    <div class="task-meta">
                        <span>📅 Due: ${formatDate(task.due_date)}</span>
                        <span>🔔 Priority: <strong style="text-transform: capitalize;">${task.priority}</strong></span>
                    </div>
                </div>
                <div class="task-actions">
                    <button class="action-btn" onclick="toggleTaskStatus(${task.id}, '${task.status === 'pending' ? 'completed' : 'pending'}')">
                        ${task.status === 'pending' ? '✔️' : '🔄'}
                    </button>
                    <button class="action-btn delete" onclick="deleteTask(${task.id})">🗑️</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error fetching tasks:', error);
        tasksContainer.innerHTML = '<div style="text-align: center; color: #ef4444; padding: 2rem;">Offline: Check if Backend is running.</div>';
    }
}

// Create new task
taskForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const taskData = {
        title: document.getElementById('title').value,
        description: document.getElementById('description').value,
        // Send local time directly instead of converting to UTC
        due_date: document.getElementById('due_date').value,
        priority: document.getElementById('priority').value.toLowerCase(),
        user_email: document.getElementById('user_email').value
    };

    try {
        const response = await fetch(`${API_BASE}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            notify('Notification scheduled successfully!');
            taskForm.reset();
            fetchTasks();
        } else {
            const err = await response.json();
            notify('Error: ' + (err.detail || 'Failed to create task'));
        }
    } catch (error) {
        notify('Network error. Is the backend running?');
    }
});

// Delete task
async function deleteTask(id) {
    if (!confirm('Are you sure you want to delete this task?')) return;

    try {
        const response = await fetch(`${API_BASE}/tasks/${id}`, { method: 'DELETE' });
        if (response.ok) {
            notify('Task deleted.');
            fetchTasks();
        }
    } catch (error) {
        notify('Error deleting task.');
    }
}

// Toggle status
async function toggleTaskStatus(id, newStatus) {
    try {
        const response = await fetch(`${API_BASE}/tasks/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        if (response.ok) {
            notify(`Task marked as ${newStatus}!`);
            fetchTasks();
        }
    } catch (error) {
        notify('Error updating task.');
    }
}

// Initial fetch
fetchTasks();
// Refresh every 30 seconds
setInterval(fetchTasks, 30000);

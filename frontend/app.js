// Configuration
const API_BASE = 'http://127.0.0.1:8000/api/v1'; // Update if backend is hosted elsewhere
let API_TOKEN = localStorage.getItem('ultra_z_token') || null;
let currentConversationId = null;

// DOM Elements
const loginModal = document.getElementById('login-modal');
const dashboard = document.getElementById('dashboard');
const loginForm = document.getElementById('login-form');
const pinInput = document.getElementById('pin-input');
const loginError = document.getElementById('login-error');
const logoutBtn = document.getElementById('logout-btn');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    if (API_TOKEN) {
        showDashboard();
    } else {
        loginModal.classList.add('active');
        pinInput.focus();
    }
    setupNavigation();
    setupEventHandlers();
});

// --- API Wrapper ---
async function apiCall(endpoint, options = {}) {
    const headers = { ...options.headers };
    if (API_TOKEN) {
        headers['Authorization'] = `Bearer ${API_TOKEN}`;
    }
    if (!(options.body instanceof FormData) && options.method && options.method !== 'GET') {
        headers['Content-Type'] = 'application/json';
        if (typeof options.body === 'object') {
            options.body = JSON.stringify(options.body);
        }
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
        if (response.status === 401) {
            handleLogout();
            throw new Error("Unauthorized. Please login again.");
        }
        
        // Handle audio response
        if (response.headers.get('content-type')?.includes('audio')) {
            return response.blob();
        }
        
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'API Error');
        return data;
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

// --- Authentication ---
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pin = pinInput.value;
    if (!pin) return;

    try {
        const data = await apiCall('/auth/pin', { method: 'POST', body: { pin } });
        API_TOKEN = data.access_token;
        localStorage.setItem('ultra_z_token', API_TOKEN);
        loginError.classList.add('hidden');
        showDashboard();
        showToast('Login successful', 'success');
    } catch (error) {
        loginError.classList.remove('hidden');
    }
});

function handleLogout() {
    API_TOKEN = null;
    localStorage.removeItem('ultra_z_token');
    dashboard.classList.add('hidden');
    loginModal.classList.add('active');
    pinInput.value = '';
}
logoutBtn.addEventListener('click', handleLogout);

function showDashboard() {
    loginModal.classList.remove('active');
    dashboard.classList.remove('hidden');
    refreshSystemStatus();
}

// --- Navigation ---
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.view-section');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-target');
            
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(s => {
                if (s.id === targetId) {
                    s.classList.remove('hidden');
                    // Small delay to allow display:block before opacity transition
                    setTimeout(() => s.classList.add('active'), 10);
                } else {
                    s.classList.remove('active');
                    setTimeout(() => s.classList.add('hidden'), 300);
                }
            });

            // Trigger view-specific loads
            if (targetId === 'view-system') refreshSystemStatus();
            if (targetId === 'view-chat') loadConversations();
            if (targetId === 'view-memories') loadMemories();
            if (targetId === 'view-reminders') loadReminders();
        });
    });
}

// --- System Status ---
async function refreshSystemStatus() {
    const apiDot = document.querySelector('#status-api .dot');
    const apiText = document.querySelector('#status-api .status-text');
    try {
        await apiCall('/health');
        apiDot.className = 'dot ok';
        apiText.textContent = 'Online';
    } catch (e) {
        apiDot.className = 'dot error';
        apiText.textContent = 'Offline';
    }

    const llmDot = document.querySelector('#status-llm .dot');
    const llmText = document.querySelector('#status-llm .status-text');
    try {
        const llm = await apiCall('/llm/health');
        if (llm.status === 'ok') {
            llmDot.className = 'dot ok';
            llmText.textContent = `Online (${llm.models.length} models)`;
        } else {
            throw new Error();
        }
    } catch (e) {
        llmDot.className = 'dot error';
        llmText.textContent = 'Offline';
    }

    refreshWakeWordStatus();
}
document.getElementById('refresh-system-btn').addEventListener('click', refreshSystemStatus);

// --- Wake Word ---
async function refreshWakeWordStatus() {
    const wwDot = document.querySelector('#status-wakeword .dot');
    const wwText = document.querySelector('#status-wakeword .status-text');
    const wwBadge = document.getElementById('ww-current-state');
    
    try {
        const ww = await apiCall('/wakeword/status');
        if (ww.running) {
            wwDot.className = 'dot ok';
            wwText.textContent = 'Running';
            wwBadge.textContent = ww.state;
            wwBadge.style.background = 'rgba(16, 185, 129, 0.2)';
            wwBadge.style.color = '#10b981';
        } else {
            wwDot.className = 'dot error';
            wwText.textContent = 'Stopped';
            wwBadge.textContent = 'STOPPED';
            wwBadge.style.background = 'rgba(239, 68, 68, 0.2)';
            wwBadge.style.color = '#ef4444';
        }
    } catch (e) {
        wwDot.className = 'dot unknown';
        wwText.textContent = 'Unknown';
        wwBadge.textContent = 'ERROR';
    }
}

document.getElementById('ww-start-btn').addEventListener('click', () => {
    apiCall('/wakeword/start', { method: 'POST' }).then(() => {
        showToast('Wake word started', 'success');
        refreshWakeWordStatus();
    });
});
document.getElementById('ww-stop-btn').addEventListener('click', () => {
    apiCall('/wakeword/stop', { method: 'POST' }).then(() => {
        showToast('Wake word stopped', 'warning');
        refreshWakeWordStatus();
    });
});
document.getElementById('ww-restart-btn').addEventListener('click', () => {
    apiCall('/wakeword/restart', { method: 'POST' }).then(() => {
        showToast('Wake word restarted', 'success');
        refreshWakeWordStatus();
    });
});

// --- Chat ---
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const convoSelect = document.getElementById('conversation-select');

async function loadConversations() {
    try {
        const convos = await apiCall('/conversations');
        convoSelect.innerHTML = '<option value="new">-- New Conversation --</option>';
        convos.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.textContent = new Date(c.created_at).toLocaleString() + (c.title ? ` - ${c.title}` : '');
            convoSelect.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to load conversations");
    }
}

convoSelect.addEventListener('change', async (e) => {
    const val = e.target.value;
    if (val === 'new') {
        currentConversationId = null;
        chatMessages.innerHTML = '<div class="message system"><div class="avatar"><i class="fa-solid fa-robot"></i></div><div class="bubble">System initialized. Awaiting input.</div></div>';
    } else {
        currentConversationId = val;
        try {
            const convo = await apiCall(`/conversations/${val}`);
            chatMessages.innerHTML = '';
            convo.messages.forEach(m => appendMessage(m.role, m.content));
        } catch (e) {
            showToast('Failed to load conversation', 'error');
        }
    }
});

document.getElementById('new-chat-btn').addEventListener('click', () => {
    convoSelect.value = 'new';
    convoSelect.dispatchEvent(new Event('change'));
});

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = chatInput.value.trim();
    if (!msg) return;
    
    appendMessage('user', msg);
    chatInput.value = '';
    
    // Add temporary loading indicator
    const tempId = 'msg-' + Date.now();
    chatMessages.insertAdjacentHTML('beforeend', `<div id="${tempId}" class="message system"><div class="avatar"><i class="fa-solid fa-robot"></i></div><div class="bubble">Thinking <i class="fa-solid fa-circle-notch fa-spin"></i></div></div>`);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const payload = { message: msg };
        if (currentConversationId) payload.conversation_id = currentConversationId;
        
        const response = await apiCall('/chat', { method: 'POST', body: payload });
        
        // Remove loading
        document.getElementById(tempId).remove();
        
        if (!currentConversationId) {
            currentConversationId = response.conversation_id;
            loadConversations().then(() => convoSelect.value = currentConversationId);
        }
        
        appendMessage('assistant', response.response);
    } catch (error) {
        document.getElementById(tempId).remove();
        appendMessage('system', 'Failed to get response. ' + error.message);
    }
});

function appendMessage(role, content) {
    const isUser = role === 'user';
    const icon = isUser ? 'fa-user' : 'fa-robot';
    const cssClass = isUser ? 'user' : 'system';
    
    const html = `
        <div class="message ${cssClass}">
            <div class="avatar"><i class="fa-solid ${icon}"></i></div>
            <div class="bubble">${escapeHTML(content)}</div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', html);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// --- Memories ---
const memList = document.getElementById('memories-list');
async function loadMemories() {
    try {
        const memories = await apiCall('/memories');
        memList.innerHTML = '';
        if (memories.length === 0) {
            memList.innerHTML = '<li class="loading-text">No memories found.</li>';
            return;
        }
        memories.forEach(m => {
            memList.insertAdjacentHTML('beforeend', `
                <li>
                    <div class="item-content">
                        <div class="item-text">${escapeHTML(m.content)}</div>
                        <div class="item-meta">Category: ${m.category || 'general'} | Importance: ${m.importance}</div>
                    </div>
                    <button class="btn icon-btn text-btn" onclick="deleteMemory(${m.id})"><i class="fa-solid fa-trash"></i></button>
                </li>
            `);
        });
    } catch (e) {
        memList.innerHTML = '<li class="loading-text" style="color:var(--danger-color)">Error loading memories.</li>';
    }
}
document.getElementById('refresh-memories-btn').addEventListener('click', loadMemories);
document.getElementById('add-memory-btn').addEventListener('click', async () => {
    const input = document.getElementById('new-memory-input');
    if (!input.value) return;
    try {
        await apiCall('/memories', { method: 'POST', body: { content: input.value, importance: 3 } });
        input.value = '';
        loadMemories();
        showToast('Memory added', 'success');
    } catch (e) {}
});
window.deleteMemory = async (id) => {
    try {
        await apiCall(`/memories/${id}`, { method: 'DELETE' });
        loadMemories();
        showToast('Memory deleted', 'success');
    } catch (e) {}
};

// --- Reminders ---
const remList = document.getElementById('reminders-list');
async function loadReminders() {
    try {
        const reminders = await apiCall('/reminders?only_open=false');
        remList.innerHTML = '';
        if (reminders.length === 0) {
            remList.innerHTML = '<li class="loading-text">No reminders found.</li>';
            return;
        }
        reminders.forEach(r => {
            const timeStr = new Date(r.remind_at).toLocaleString();
            const statusColor = r.status === 'open' ? 'var(--warning-color)' : 'var(--success-color)';
            remList.insertAdjacentHTML('beforeend', `
                <li>
                    <div class="item-content">
                        <div class="item-text">${escapeHTML(r.title)}</div>
                        <div class="item-meta">
                            <span style="color:${statusColor}">[${r.status.toUpperCase()}]</span> 
                            At: ${timeStr}
                        </div>
                    </div>
                </li>
            `);
        });
    } catch (e) {
        remList.innerHTML = '<li class="loading-text" style="color:var(--danger-color)">Error loading reminders.</li>';
    }
}
document.getElementById('refresh-reminders-btn').addEventListener('click', loadReminders);
document.getElementById('add-reminder-btn').addEventListener('click', async () => {
    const titleInput = document.getElementById('new-reminder-input');
    const timeInput = document.getElementById('new-reminder-time');
    if (!titleInput.value || !timeInput.value) return showToast('Fill all fields', 'error');
    
    try {
        await apiCall('/reminders', { 
            method: 'POST', 
            body: { title: titleInput.value, remind_at: new Date(timeInput.value).toISOString() } 
        });
        titleInput.value = '';
        timeInput.value = '';
        loadReminders();
        showToast('Reminder set', 'success');
    } catch (e) {}
});

// --- Voice ---
document.getElementById('stt-file').addEventListener('change', (e) => {
    const name = e.target.files[0] ? e.target.files[0].name : 'No file selected';
    document.getElementById('stt-filename').textContent = name;
});

document.getElementById('stt-btn').addEventListener('click', async () => {
    const file = document.getElementById('stt-file').files[0];
    if (!file) return showToast('Select an audio file first', 'error');
    
    const formData = new FormData();
    formData.append('file', file);
    
    const resDiv = document.getElementById('stt-result');
    const resP = resDiv.querySelector('p');
    resDiv.classList.remove('hidden');
    resP.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Transcribing...';
    
    try {
        const res = await apiCall('/voice/transcribe', { method: 'POST', body: formData });
        resP.textContent = res.text;
    } catch (e) {
        resP.textContent = 'Error transcribing: ' + e.message;
    }
});

document.getElementById('tts-btn').addEventListener('click', async () => {
    const text = document.getElementById('tts-input').value;
    if (!text) return;
    
    try {
        const blob = await apiCall('/voice/speak', { 
            method: 'POST', 
            body: { text: text, voice: 'auto', language: 'auto' } 
        });
        
        const audioUrl = URL.createObjectURL(blob);
        const container = document.getElementById('tts-audio-container');
        const audioEl = document.getElementById('tts-audio');
        
        audioEl.src = audioUrl;
        container.classList.remove('hidden');
        audioEl.play();
    } catch (e) {
        showToast('TTS failed. Piper models might not be configured.', 'error');
    }
});

// --- Utils ---
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? 'fa-check-circle' : 'fa-triangle-exclamation';
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> ${escapeHTML(message)}`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
}

/**
 * Persistent Chat & AI Companion Controller.
 * Session management (New, Rename, Archive, Delete, Search) and Supervisor streaming with citations.
 */

class ChatController {
  constructor() {
    this.sessions = [];
    this.activeSessionId = null;
    this.messages = [];
  }

  async render(container) {
    container.innerHTML = `
      <div class="chat-layout">
        <!-- Sidebar -->
        <div class="chat-sidebar">
          <button class="btn-aerospace" style="width:100%; justify-content:center;" onclick="window.chatController.handleNewSession()">
            ➕ New Conversation
          </button>

          <input type="text" class="input-aerospace" placeholder="Search sessions..." oninput="window.chatController.filterSessions(this.value)">

          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-top:6px;">
            Saved Sessions
          </div>

          <div id="chat-session-list" style="display:flex; flex-direction:column; gap:6px; overflow-y:auto; flex:1;">
            Loading sessions...
          </div>
        </div>

        <!-- Main Chat Area -->
        <div class="chat-main">
          <div style="padding:12px 16px; border-bottom:1px solid var(--color-border); display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-weight:700; font-size:14px;" id="chat-active-title">AI Health Companion</div>
              <div style="font-size:11px; color:var(--text-muted);" id="chat-active-meta">LangGraph Supervisor Swarm</div>
            </div>
            <div style="display:flex; gap:6px;">
              <button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="window.chatController.handleRenameSession()">✏️ Rename</button>
              <button class="btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="window.chatController.handleArchiveSession()">📦 Archive</button>
              <button class="btn-secondary" style="padding:4px 8px; font-size:11px; color:var(--color-rose);" onclick="window.chatController.handleDeleteSession()">🗑️ Delete</button>
            </div>
          </div>

          <div class="chat-messages-container" id="chat-msg-box">
            <div style="color:var(--text-muted); text-align:center; padding:40px;">Select or start a new conversation.</div>
          </div>

          <!-- Composer -->
          <div style="padding:12px 16px; border-top:1px solid var(--color-border); display:flex; gap:8px;">
            <input type="text" class="input-aerospace" id="chat-input" placeholder="Ask your personal medical AI companion..." onkeydown="if(event.key==='Enter') window.chatController.handleSend()">
            <button class="btn-aerospace" onclick="window.chatController.handleSend()">Send</button>
          </div>
        </div>
      </div>
    `;

    await this.loadSessions();
  }

  async loadSessions() {
    const listDiv = document.getElementById('chat-session-list');
    if (!listDiv) return;
    try {
      this.sessions = await window.api.listSessions();
      if (!this.sessions || this.sessions.length === 0) {
        listDiv.innerHTML = '<div style="font-size:11px; color:var(--text-muted); text-align:center; padding:10px;">No saved sessions.</div>';
        return;
      }
      listDiv.innerHTML = this.sessions.map(s => `
        <div class="mission-card-solid" style="padding:8px; cursor:pointer; font-size:12px; ${s.id === this.activeSessionId ? 'border-color:var(--color-cyan);' : ''}" onclick="window.chatController.selectSession('${s.id}')">
          <div style="font-weight:600; color:var(--text-bright); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${s.title}</div>
          <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--text-muted); margin-top:2px;">
            <span>${s.message_count || 0} msgs</span>
            <span>${new Date(s.updated_at || s.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
          </div>
        </div>
      `).join('');

      if (!this.activeSessionId && this.sessions.length > 0) {
        this.selectSession(this.sessions[0].id);
      }
    } catch (e) {
      listDiv.innerHTML = `<div style="color:var(--color-rose); font-size:11px;">Error: ${e.message}</div>`;
    }
  }

  async selectSession(sessionId) {
    this.activeSessionId = sessionId;
    const session = this.sessions.find(s => s.id === sessionId);
    if (session) {
      const titleEl = document.getElementById('chat-active-title');
      if (titleEl) titleEl.innerText = session.title;
    }
    await this.loadMessages(sessionId);
    this.loadSessions();
  }

  async loadMessages(sessionId) {
    const box = document.getElementById('chat-msg-box');
    if (!box) return;
    box.innerHTML = '<div style="color:var(--text-muted); text-align:center;">Loading conversation...</div>';
    try {
      this.messages = await window.api.getMessages(sessionId);
      if (!this.messages || this.messages.length === 0) {
        box.innerHTML = `
          <div class="chat-bubble assistant">
            Hello Astronaut! I am your TRUSTLINE AI Companion, backed by the LangGraph Supervisor Swarm.
            I continuously cross-reference your live cardiovascular telemetry, space radiation dosimetry, and verified clinical history.
            How are you feeling today?
          </div>
        `;
        return;
      }
      box.innerHTML = this.messages.map(m => `
        <div class="chat-bubble ${m.sender === 'USER' ? 'user' : 'assistant'}">
          <div>${m.content}</div>
          ${m.provider ? `<div style="font-size:10px; opacity:0.75; margin-top:4px; font-family:var(--font-mono);">⚡ Routed via: ${m.provider}</div>` : ''}
        </div>
      `).join('');
      box.scrollTop = box.scrollHeight;
    } catch (e) {
      box.innerHTML = `<div style="color:var(--color-rose);">Failed to load messages: ${e.message}</div>`;
    }
  }

  async handleSend() {
    const input = document.getElementById('chat-input');
    if (!input || !input.value.trim()) return;
    const text = input.value.trim();
    input.value = '';

    if (!this.activeSessionId) {
      const newS = await window.api.createSession('Health Ingestion Session');
      this.activeSessionId = newS.id;
      await this.loadSessions();
    }

    const box = document.getElementById('chat-msg-box');
    box.innerHTML += `<div class="chat-bubble user">${text}</div>`;
    box.scrollTop = box.scrollHeight;

    const thinkingId = 'thinking-' + Date.now();
    box.innerHTML += `<div class="chat-bubble assistant" id="${thinkingId}"><span style="color:var(--color-amber);">Supervisor reasoning across multi-agent evidence...</span></div>`;
    box.scrollTop = box.scrollHeight;

    try {
      const reply = await window.api.sendMessage(this.activeSessionId, text);
      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) {
        thinkingEl.innerHTML = `
          <div>${reply.content}</div>
          ${reply.provider ? `<div style="font-size:10px; opacity:0.75; margin-top:4px; font-family:var(--font-mono);">⚡ Routed via: ${reply.provider}</div>` : ''}
        `;
      }
      box.scrollTop = box.scrollHeight;
    } catch (err) {
      const thinkingEl = document.getElementById(thinkingId);
      if (thinkingEl) thinkingEl.innerHTML = `<span style="color:var(--color-rose);">Error: ${err.message}</span>`;
    }
  }

  async handleNewSession() {
    const title = prompt('Enter title for new conversation:', 'Flight Health Check');
    if (!title) return;
    const s = await window.api.createSession(title);
    this.activeSessionId = s.id;
    await this.loadSessions();
    await this.loadMessages(s.id);
  }

  async handleRenameSession() {
    if (!this.activeSessionId) return;
    const title = prompt('Enter new session title:');
    if (!title) return;
    await window.api.patchSession(this.activeSessionId, title);
    await this.loadSessions();
  }

  async handleArchiveSession() {
    if (!this.activeSessionId) return;
    await window.api.patchSession(this.activeSessionId, null, 'ARCHIVED');
    alert('Session archived.');
    await this.loadSessions();
  }

  async handleDeleteSession() {
    if (!this.activeSessionId) return;
    if (!confirm('Are you sure you want to permanently delete this chat session?')) return;
    await window.api.deleteSession(this.activeSessionId);
    this.activeSessionId = null;
    await this.loadSessions();
  }

  filterSessions(query) {
    const listDiv = document.getElementById('chat-session-list');
    if (!listDiv) return;
    const filtered = this.sessions.filter(s => s.title.toLowerCase().includes(query.toLowerCase()));
    listDiv.innerHTML = filtered.map(s => `
      <div class="mission-card-solid" style="padding:8px; cursor:pointer; font-size:12px; ${s.id === this.activeSessionId ? 'border-color:var(--color-cyan);' : ''}" onclick="window.chatController.selectSession('${s.id}')">
        <div style="font-weight:600; color:var(--text-bright); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${s.title}</div>
      </div>
    `).join('');
  }
}

window.chatController = new ChatController();

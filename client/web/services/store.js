const STORE_KEY = 'lt';

let _saveTimer = null;
function _debouncedSave(data) {
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => _save(data), 50);
}

function _save(data) {
  const payload = {
    sessions: data.sessions,
    activeId: data.activeId,
    messages: data.messages,
    forks: data.forks,
    theme: data.theme
  };
  if (typeof LT !== 'undefined' && LT.save) {
    LT.save(STORE_KEY, payload);
  } else {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(payload));
    } catch (e) {
      console.warn('[store] Failed to save:', e);
    }
  }
}

function _uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function _now() {
  return Date.now();
}

const store = {
  sessions: [],
  activeId: null,
  messages: {},
  forks: {},
  theme: 'light',
  generating: false,

  init() {
    let raw = null;
    if (typeof LT !== 'undefined' && LT.load) {
      raw = LT.load(STORE_KEY);
    } else {
      try {
        const saved = localStorage.getItem(STORE_KEY);
        if (saved) raw = JSON.parse(saved);
      } catch (e) {
        console.warn('[store] Failed to load:', e);
      }
    }

    if (raw && typeof raw === 'object') {
      this.sessions = Array.isArray(raw.sessions) ? raw.sessions : [];
      this.activeId = raw.activeId || null;
      this.messages = raw.messages && typeof raw.messages === 'object' ? raw.messages : {};
      this.forks = raw.forks && typeof raw.forks === 'object' ? raw.forks : {};
      this.theme = raw.theme || 'light';
    }

    if (this.theme === 'dark') {
      document.documentElement.classList.add('dark');
    }

    if (!this.sessions.length) {
      this.create('New Chat');
    }

    return this;
  },

    create(title) {
      const id = _uid();
      const session = {
        id,
        title: title || 'New Chat',
        createdAt: _now(),
        updatedAt: _now()
      };
      this.sessions.unshift(session);
      this.activeId = id;
      this.messages[id] = [];
      this.forks[id] = null;
      _save(this);

      // Auto-trim previous active session
      if (window.Perf) window.Perf.trimMessages(this);

      return session;
    },

    addMsg(sid, { role, content }) {
      if (!this.messages[sid]) {
        this.messages[sid] = [];
      }
      const msg = {
        role,
        content,
        timestamp: _now()
      };
      this.messages[sid].push(msg);

      const session = this.sessions.find(s => s.id === sid);
      if (session) {
        session.updatedAt = _now();
        if (!session.title || session.title === 'New Chat') {
          const preview = (content || '').replace(/\s+/g, ' ').trim().slice(0, 40);
          if (preview) session.title = preview;
        }
      }

      _debouncedSave(this);

      // Auto-archive when exceeding LRU
      if (window.Perf && this.messages[sid].length > (window.Perf.LRU_SIZE || 50)) {
        window.Perf.trimMessages(this);
      }

      return msg;
    },

  remove(id) {
    const idx = this.sessions.findIndex(s => s.id === id);
    if (idx === -1) return;

    this.sessions.splice(idx, 1);
    delete this.messages[id];
    delete this.forks[id];

    if (this.activeId === id) {
      this.activeId = this.sessions.length > 0 ? this.sessions[0].id : null;
    }

    if (!this.sessions.length) {
      this.create('New Chat');
    }

    _save(this);
  },

  rename(id, title) {
    const session = this.sessions.find(s => s.id === id);
    if (!session) return;
    session.title = title;
    session.updatedAt = _now();
    _save(this);
  },

  setActive(id) {
    if (this.sessions.some(s => s.id === id)) {
      this.activeId = id;
    }
  },

  addMsg(sid, { role, content }) {
    if (!this.messages[sid]) {
      this.messages[sid] = [];
    }
    const msg = {
      role,
      content,
      timestamp: _now()
    };
    this.messages[sid].push(msg);

    const session = this.sessions.find(s => s.id === sid);
    if (session) {
      session.updatedAt = _now();
      if (!session.title || session.title === 'New Chat') {
        const preview = (content || '').replace(/\s+/g, ' ').trim().slice(0, 40);
        if (preview) session.title = preview;
      }
    }

    _debouncedSave(this);
    return msg;
  },

  updateLast(sid, content) {
    const msgs = this.messages[sid];
    if (!msgs || !msgs.length) return;
    msgs[msgs.length - 1].content = content;
    msgs[msgs.length - 1].timestamp = _now();
    _debouncedSave(this);
  },

  removeMsgFrom(sid, idx) {
    const msgs = this.messages[sid];
    if (!msgs || idx < 0 || idx >= msgs.length) return;
    this.messages[sid] = msgs.slice(0, idx);
    _save(this);
  },

  getMsgs(sid) {
    return this.messages[sid] || [];
  },

  active() {
    return this.sessions.find(s => s.id === this.activeId) || null;
  },

  stats() {
    const msgs = (this.messages && typeof this.messages === 'object') ? this.messages : {};
    let count = 0, tokens = 0;
    for (const arr of Object.values(msgs)) {
      if (Array.isArray(arr)) { count += arr.length; arr.forEach(m => tokens += Math.ceil((m.content || '').length / 3)); }
    }
    const sessions = Array.isArray(this.sessions) ? this.sessions.length : 0;
    return { sessions, messages: count, tokens };
  },

  fork(fromId, atIndex, title) {
    const srcMsgs = this.messages[fromId];
    if (!srcMsgs) return null;

    const id = _uid();
    const session = {
      id,
      title: title || 'Forked Chat',
      createdAt: _now(),
      updatedAt: _now()
    };

    this.sessions.unshift(session);
    this.activeId = id;

    const sliced = srcMsgs.slice(0, atIndex + 1).map(m => ({ ...m }));
    this.messages[id] = sliced;

    this.forks[id] = { fromId, atIndex };

    _save(this);
    return session;
  },

  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    if (this.theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    _save(this);
    return this.theme;
  },

  search(q) {
    if (!q || !q.trim()) return [];
    const term = q.toLowerCase();
    const results = [];

    for (const session of this.sessions) {
      const msgs = this.messages[session.id] || [];
      for (let i = 0; i < msgs.length; i++) {
        const content = (msgs[i].content || '').toLowerCase();
        if (content.includes(term)) {
          results.push({
            sessionId: session.id,
            sessionTitle: session.title,
            msgIndex: i,
            role: msgs[i].role,
            snippet: msgs[i].content.slice(0, 120)
          });
        }
      }
      if ((session.title || '').toLowerCase().includes(term)) {
        results.push({
          sessionId: session.id,
          sessionTitle: session.title,
          msgIndex: -1,
          role: null,
          snippet: session.title
        });
      }
    }

    return results;
  },

    export(sid) {
      const msgs = this.messages[sid];
      const session = this.sessions.find(s => s.id === sid);

      if (!msgs || !session) return null;

      const lines = [];
      lines.push(`# ${session.title}`);
      lines.push(`> Exported: ${new Date().toISOString()}`);
      lines.push('');

      for (const msg of msgs) {
        lines.push(`## ${msg.role === 'user' ? 'You' : 'Assistant'}`);
        lines.push('');
        lines.push(msg.content);
        lines.push('');
      }

      const text = lines.join('\n');

      return {
        text,
        filename: `livingtree-${session.title.replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, '_').slice(0, 40)}.md`,
        download() {
          const blob = new Blob([text], { type: 'text/markdown' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = this.filename;
          a.click();
          URL.revokeObjectURL(url);
        }
      };
    },

    /* ── Pinned messages ── */
    pinned: {},
    togglePin(sid, msgIdx) {
      if (!this.pinned[sid]) this.pinned[sid] = new Set();
      if (this.pinned[sid].has(msgIdx)) this.pinned[sid].delete(msgIdx);
      else this.pinned[sid].add(msgIdx);
      _save(this);
    },
    getPinned(sid) {
      const pins = this.pinned[sid];
      const msgs = this.messages[sid];
      if (!pins || !msgs) return [];
      return [...pins].map(i => msgs[i]).filter(Boolean);
    },

    /* ── Auto theme ── */
    initAutoTheme() {
      const saved = localStorage.getItem('lt_theme');
      if (saved) { this.theme = saved; this._applyTheme(); return; }
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        this.theme = 'dark';
      } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
        this.theme = 'light';
      }
      // Listen for system changes
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('lt_theme')) {
          this.theme = e.matches ? 'dark' : 'light';
          this._applyTheme();
        }
      });
      this._applyTheme();
    },
    _applyTheme() {
      if (this.theme === 'dark') document.documentElement.classList.add('dark');
      else document.documentElement.classList.remove('dark');
    },

    /* ── Generate share URL for card ── */
    shareCard(cardId, cardData) {
      const key = 'lt_shared_cards';
      let data = {};
      try { data = JSON.parse(localStorage.getItem(key) || '{}'); } catch(e) {}
      data[cardId] = cardData;
      localStorage.setItem(key, JSON.stringify(data));
      return `${window.location.origin}/card.html?id=${cardId}`;
    },

    /* ── Notifications ── */
    notifyEnabled: false,
    requestNotify() {
      if (!('Notification' in window)) return;
      Notification.requestPermission().then(p => {
        this.notifyEnabled = p === 'granted';
      });
    },
    notify(title, body) {
      if (this.notifyEnabled && 'Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, icon: '/favicon.ico' });
      }
    },
  };

window.LT = window.LT || {};
window.LT.store = store;

/* ═══════════════════════════════════
   LivingTree — Performance Optimizer
   Streaming DOM, IndexedDB archive, document pipeline
   ═══════════════════════════════════ */

const Perf = {
  /* ── Streaming DOM: append-only via Range API ── */
  _streamEl: null, _streamContent: '', _streamRAF: null,
  _batchChunks: [],

  initStream(container) {
    this._streamEl = container;
    this._streamContent = '';
    this._batchChunks = [];
  },

  appendChunk(chunk) {
    this._batchChunks.push(chunk);
    if (!this._streamRAF) {
      this._streamRAF = requestAnimationFrame(() => this._flushBatch());
    }
  },

  _flushBatch() {
    if (!this._batchChunks.length) { this._streamRAF = null; return; }
    const text = this._batchChunks.join('');
    this._batchChunks = [];
    this._streamRAF = null;

    this._streamContent += text;
    // Use Range API for append-only — avoids innerHTML full replacement
    if (this._streamEl) {
      const range = document.createRange();
      const frag = range.createContextualFragment(LT.renderer.md(this._streamContent));
      this._streamEl.textContent = '';
      this._streamEl.appendChild(frag);
      // Fallback: innerHTML for complex markdown
      if (!this._streamEl.children.length) {
        this._streamEl.innerHTML = LT.renderer.md(this._streamContent);
      }
    }
  },

  /* ── Message Archive: IndexedDB for old messages ── */
  _db: null,
  _dbReady: false,

  async _openDB() {
    if (this._dbReady) return this._db;
    return new Promise((resolve, reject) => {
      const req = indexedDB.open('lt_archive', 1);
      req.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('messages')) {
          db.createObjectStore('messages', { keyPath: 'key' });
        }
      };
      req.onsuccess = e => { this._db = e.target.result; this._dbReady = true; resolve(this._db); };
      req.onerror = () => resolve(null);
    });
  },

  async archiveMessages(sessionId, messages) {
    const db = await this._openDB();
    if (!db) return;
    const tx = db.transaction('messages', 'readwrite');
    const store = tx.objectStore('messages');
    store.put({ key: `msgs_${sessionId}`, data: messages, ts: Date.now() });
  },

  async loadArchived(sessionId) {
    const db = await this._openDB();
    if (!db) return null;
    return new Promise(resolve => {
      const tx = db.transaction('messages', 'readonly');
      const store = tx.objectStore('messages');
      const req = store.get(`msgs_${sessionId}`);
      req.onsuccess = () => resolve(req.result?.data || null);
      req.onerror = () => resolve(null);
    });
  },

  /* ── Message LRU: keep only recent N in memory ── */
  LRU_SIZE: 50,

  trimMessages(store) {
    if (!store || !store.activeId) return;
    const msgs = store.messages[store.activeId];
    if (!msgs || msgs.length <= this.LRU_SIZE) return;

    // Archive old messages
    this.archiveMessages(store.activeId, msgs.slice(0, -this.LRU_SIZE));
    // Keep only recent
    store.messages[store.activeId] = msgs.slice(-this.LRU_SIZE);
    store.save();
  },

  async loadFullHistory(store) {
    if (!store || !store.activeId) return;
    const archived = await this.loadArchived(store.activeId);
    if (archived) {
      store.messages[store.activeId] = [...archived, ...(store.messages[store.activeId] || [])];
      store.save();
    }
  },

  /* ── Document lazy load ── */
  docLoadQueue: [],

  queueDocLoad(docId) {
    if (this.docLoadQueue.includes(docId)) return;
    this.docLoadQueue.push(docId);
    this._processDocQueue();
  },

  async _processDocQueue() {
    if (this._docProcessing) return;
    this._docProcessing = true;
    while (this.docLoadQueue.length) {
      const docId = this.docLoadQueue.shift();
      // Pre-warm OnlyOffice API
      if (window.OnlyOffice) OnlyOffice.init();
    }
    this._docProcessing = false;
  },

  /* ── Debounced scroll handler ── */
  _scrollTimer: null,
  onScroll(callback, wait = 50) {
    clearTimeout(this._scrollTimer);
    this._scrollTimer = setTimeout(callback, wait);
  },

  /* ── Skeleton loader ── */
  showSkeleton(container, count = 3) {
    container.innerHTML = Array(count).fill(
      '<div class="skeleton" style="height:40px;margin:4px 0"></div>'
    ).join('');
  },

  /* ── Measure and report ── */
  measure(label) {
    if (window.performance && performance.mark) {
      performance.mark(label + '_start');
      return () => {
        performance.mark(label + '_end');
        try { performance.measure(label, label + '_start', label + '_end'); } catch(e) {}
      };
    }
    return () => {};
  },
};

window.Perf = Perf;

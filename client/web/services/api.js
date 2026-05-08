let _abortController = null;

const api = {
  base: '/api/web',

  _authHeaders() {
    const token = localStorage.getItem('lt_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  },

  _abort() {
    if (_abortController) {
      _abortController.abort();
      _abortController = null;
    }
  },

  async streamChat(messages, onChunk, onDone, onError) {
    this._abort();
    _abortController = new AbortController();

    try {
      const response = await fetch(`${this.base}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ messages }),
        signal: _abortController.signal
      });

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        const err = new Error(`API error ${response.status}: ${text}`);
        if (onError) onError(err);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              if (onDone) onDone();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              const content = parsed.content || parsed.text || parsed.delta || '';
              if (content && onChunk) onChunk(content);
            } catch {
              if (onChunk) onChunk(data);
            }
          }
        }
      }

      if (buffer.trim() && onChunk) {
        onChunk(buffer.trim());
      }

      if (onDone) onDone();
    } catch (err) {
      if (err.name === 'AbortError') {
        if (onDone) onDone();
        return;
      }
      console.error('[api] streamChat error:', err);
      if (onError) onError(err);
    } finally {
      _abortController = null;
    }
  },

  send(input, onChunk, onDone, onError) {
    const store = window.LT && window.LT.store;
    if (!store || !store.activeId) {
      if (onError) onError(new Error('No active session'));
      return Promise.resolve();
    }

    const sid = store.activeId;

    store.addMsg(sid, { role: 'user', content: input });

    const msgs = store.getMsgs(sid);

    store.generating = true;

    let fullContent = '';

    return this.streamChat(
      msgs,
      (chunk) => {
        fullContent += chunk;
        if (onChunk) onChunk(chunk);
      },
      () => {
        if (fullContent) {
          store.addMsg(sid, { role: 'agent', content: fullContent });
        }
        store.generating = false;
        if (onDone) onDone(fullContent);
      },
      (err) => {
        store.generating = false;
        if (onError) onError(err);
      }
    );
  },

  stop() {
    this._abort();
    const store = window.LT && window.LT.store;
    if (store) {
      store.generating = false;
    }
  },

  async simulate(input, onChunk, onDone) {
    // Fallback: simple error message, no demo data
    if (onChunk) onChunk('抱歉，AI 服务暂不可用。请检查后端是否已启动。');
    if (onDone) onDone('抱歉，AI 服务暂不可用。请检查后端是否已启动。');
    const store = window.LT && window.LT.store;
    if (store) store.generating = false;
  },

  /* ── Backend data endpoints ── */

  async health() {
    try { const r = await fetch('/api/health'); return await r.json() } catch { return null }
  },

  async status() {
    try { const r = await fetch('/api/status', { headers: this._authHeaders() }); return await r.json() } catch { return null }
  },

  async tools() {
    try { const r = await fetch('/api/tools', { headers: this._authHeaders() }); return await r.json() } catch { return [] }
  },

  async skills() {
    try { const r = await fetch('/api/skills', { headers: this._authHeaders() }); return await r.json() } catch { return [] }
  },

  async bootProgress() {
    try { const r = await fetch('/api/boot/progress'); return await r.json() } catch { return null }
  },

  async cells() {
    try { const r = await fetch('/api/cells'); return await r.json() } catch { return [] }
  },

  async metrics() {
    try { const r = await fetch('/api/metrics'); return await r.json() } catch { return null }
  }
};

window.LT = window.LT || {};
window.LT.api = api;

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
  },

  /* ── Code Mode File Operations ── */

  async codeListFiles(dirPath = '', project = '') {
    try {
      let url = `${this.base}/../code/files?path=${encodeURIComponent(dirPath)}`;
      if (project) url += `&project=${encodeURIComponent(project)}`;
      const r = await fetch(url, { headers: this._authHeaders() });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeListFiles:', e); return null; }
  },

  async codeReadFile(filePath, project = '') {
    try {
      let url = `${this.base}/../code/file?path=${encodeURIComponent(filePath)}`;
      if (project) url += `&project=${encodeURIComponent(project)}`;
      const r = await fetch(url, { headers: this._authHeaders() });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeReadFile:', e); return null; }
  },

  async codeWriteFile(filePath, content, project = '') {
    try {
      let url = `${this.base}/../code/file`;
      if (project) url += `?project=${encodeURIComponent(project)}`;
      const r = await fetch(url, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ path: filePath, content })
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeWriteFile:', e); return null; }
  },

  async codeDeleteFile(filePath) {
    try {
      const r = await fetch(`${this.base}/../code/file?path=${encodeURIComponent(filePath)}`, {
        method: 'DELETE',
        headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeDeleteFile:', e); return null; }
  },

  async codeDiff(filePath, oldContent, newContent) {
    try {
      const r = await fetch(`${this.base}/../code/diff`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ path: filePath, old_content: oldContent, new_content: newContent })
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeDiff:', e); return null; }
  },

  async codeApplyDiff(filePath, oldContent, newContent) {
    try {
      const r = await fetch(`${this.base}/../code/apply-diff`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ path: filePath, old_content: oldContent, new_content: newContent })
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeApplyDiff:', e); return null; }
  },

  async codeSearchFiles(query, project = '') {
    try {
      let url = `${this.base}/../code/search?q=${encodeURIComponent(query)}`;
      if (project) url += `&project=${encodeURIComponent(project)}`;
      const r = await fetch(url, { headers: this._authHeaders() });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeSearchFiles:', e); return null; }
  },

  /* ── Project Management ── */

  async codeListProjects() {
    try {
      const r = await fetch(`${this.base}/../code/projects`, { headers: this._authHeaders() });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeListProjects:', e); return null; }
  },

  async codeCreateProject(name, githubUrl = '') {
    try {
      const r = await fetch(`${this.base}/../code/projects`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ name, github_url: githubUrl })
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeCreateProject:', e); return null; }
  },

  async codeDeleteProject(name) {
    try {
      const r = await fetch(`${this.base}/../code/projects/${encodeURIComponent(name)}`, {
        method: 'DELETE', headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeDeleteProject:', e); return null; }
  },

  async codeSyncProject(name) {
    try {
      const r = await fetch(`${this.base}/../code/projects/${encodeURIComponent(name)}/sync`, {
        method: 'POST', headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeSyncProject:', e); return null; }
  },

  /* ── GitHub ── */

  async githubAuth() {
    try {
      const r = await fetch(`${this.base}/../code/github/auth`, { headers: this._authHeaders() });
      return await r.json();
    } catch (e) { console.warn('[api] githubAuth:', e); return null; }
  },

  async githubStatus() {
    try {
      const r = await fetch(`${this.base}/../code/github/status`, { headers: this._authHeaders() });
      return await r.json();
    } catch (e) { console.warn('[api] githubStatus:', e); return null; }
  },

  async githubRepos() {
    try {
      const r = await fetch(`${this.base}/../code/github/repos`, { headers: this._authHeaders() });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] githubRepos:', e); return null; }
  },

  async githubClone(repoUrl, projectName, branch = 'main') {
    try {
      const r = await fetch(`${this.base}/../code/github/clone`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ repo_url: repoUrl, project_name: projectName, branch })
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] githubClone:', e); return null; }
  },
};

window.LT = window.LT || {};
window.LT.api = api;

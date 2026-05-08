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

  async codeCreateProject(name, githubUrl = '', workspaceId = '') {
    try {
      const r = await fetch(`${this.base}/../code/projects`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ name, github_url: githubUrl, workspace_id: workspaceId })
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

  async codeScanProject(name) {
    try {
      const r = await fetch(`${this.base}/../code/projects/${encodeURIComponent(name)}/scan`, {
        headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] codeScanProject:', e); return null; }
  },

  /* ── Audit Log ── */

  async auditLogs(operation, risk, project, limit, offset) {
    try {
      const params = new URLSearchParams();
      if (operation) params.set('operation', operation);
      if (risk) params.set('risk', risk);
      if (project) params.set('project', project);
      if (limit) params.set('limit', String(limit));
      if (offset) params.set('offset', String(offset));
      const r = await fetch(`${this.base}/../audit/logs?${params}`, {
        headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] auditLogs:', e); return null; }
  },

  async auditMetrics() {
    try {
      const r = await fetch(`${this.base}/../audit/metrics`, {
        headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] auditMetrics:', e); return null; }
  },

  /* ── Workspace ── */

  async workspaceList() {
    try {
      const r = await fetch(`${this.base}/../workspaces`, { headers: this._authHeaders() });
      return await r.json();
    } catch (e) { console.warn('[api] workspaceList:', e); return []; }
  },

  async workspaceCreate(name) {
    try {
      const r = await fetch(`${this.base}/../workspaces`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ name })
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] workspaceCreate:', e); return null; }
  },

  async workspaceDelete(wsId) {
    try {
      const r = await fetch(`${this.base}/../workspaces/${encodeURIComponent(wsId)}`, {
        method: 'DELETE', headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] workspaceDelete:', e); return null; }
  },

  async workspaceInviteMember(wsId, userId, role) {
    try {
      const r = await fetch(`${this.base}/../workspaces/${encodeURIComponent(wsId)}/members`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ user_id: userId, role })
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] workspaceInviteMember:', e); return null; }
  },

  async workspaceRemoveMember(wsId, userId) {
    try {
      const r = await fetch(`${this.base}/../workspaces/${encodeURIComponent(wsId)}/members/${encodeURIComponent(userId)}`, {
        method: 'DELETE', headers: this._authHeaders()
      });
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    } catch (e) { console.warn('[api] workspaceRemoveMember:', e); return null; }
  },

  async workspaceMembers(wsId) {
    try {
      const r = await fetch(`${this.base}/../workspaces/${encodeURIComponent(wsId)}/members`, { headers: this._authHeaders() });
      return await r.json();
    } catch (e) { console.warn('[api] workspaceMembers:', e); return []; }
  },

  /* ── Skills ── */

  async skillList(workspaceId = '', tag = '', search = '') {
    try {
      const params = new URLSearchParams();
      if (workspaceId) params.set('workspace_id', workspaceId);
      if (tag) params.set('tag', tag);
      if (search) params.set('search', search);
      const r = await fetch(`${this.base}/../skills?${params}`, { headers: this._authHeaders() });
      return await r.json();
    } catch (e) { console.warn('[api] skillList:', e); return []; }
  },

  async skillGet(name, workspaceId = '') {
    try {
      const params = new URLSearchParams();
      if (workspaceId) params.set('workspace_id', workspaceId);
      const r = await fetch(`${this.base}/../skills/${encodeURIComponent(name)}?${params}`, { headers: this._authHeaders() });
      return await r.json();
    } catch (e) { console.warn('[api] skillGet:', e); return null; }
  },

  async skillCreateOrUpdate(name, body, description, tags, workspaceId, sourceProject) {
    try {
      const r = await fetch(`${this.base}/../skills`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
        body: JSON.stringify({ name, body, description, tags, workspace_id: workspaceId, source_project: sourceProject })
      });
      return await r.json();
    } catch (e) { console.warn('[api] skillCreateOrUpdate:', e); return null; }
  },

  async skillDelete(name, workspaceId = '') {
    try {
      const params = new URLSearchParams();
      if (workspaceId) params.set('workspace_id', workspaceId);
      const r = await fetch(`${this.base}/../skills/${encodeURIComponent(name)}?${params}`, {
        method: 'DELETE', headers: this._authHeaders()
      });
      return await r.json();
    } catch (e) { console.warn('[api] skillDelete:', e); return null; }
  },

  async skillSuggestions(workspaceId = '') {
    try {
      const params = new URLSearchParams();
      if (workspaceId) params.set('workspace_id', workspaceId);
      const r = await fetch(`${this.base}/../skills/suggestions?${params}`, { headers: this._authHeaders() });
      return await r.json();
    } catch (e) { console.warn('[api] skillSuggestions:', e); return []; }
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

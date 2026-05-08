/* ═══════════════════════════════════
   LivingTree Web — LT-Office Service
   Manages document editor iframe integration
   ═══════════════════════════════════ */

const LTOffice = {
  _editor: null,
  _docId: null,
  _iframe: null,
  _loaded: false,
  _apiScriptLoaded: false,

  /* ── Initialize OnlyOffice API script ── */
  init() {
    if (this._apiScriptLoaded) return;
    const script = document.createElement('script');
    script.src = 'http://localhost:9000/web-apps/apps/api/documents/api.js';
    script.onload = () => { this._apiScriptLoaded = true; };
    document.head.appendChild(script);
  },

  /* ── Open a document in the editor ── */
  async open(docId, containerId) {
    this._docId = docId;
    const container = document.getElementById(containerId);
    if (!container) return;

    // Show loading
      container.innerHTML = '<div class="lto-loading"><div class="lto-loading-spinner"></div><span>加载 LT-Office 编辑器...</span></div>';

    try {
      const resp = await fetch(`/api/doc/config/${docId}`);
      if (!resp.ok) throw new Error(`Config failed: ${resp.status}`);
      const config = await resp.json();

      // Override height
      config.height = '100%';
      config.width = '100%';

      // Wait for API script
      await this._waitForApi();

      // Clean previous
      this.destroy();
      container.innerHTML = '';

      this._editor = new DocsAPI.DocEditor(containerId, config);
      this._loaded = true;
      this._iframe = container.querySelector('iframe');

      LT.emit('doc:opened', { docId });
    } catch (err) {
      console.error('[LT-Office] Failed to open:', err);
      container.innerHTML = `<div class="lto-error">编辑器加载失败: ${err.message}</div>`;
    }
  },

  async _waitForApi(maxWait = 10000) {
    if (window.DocsAPI) return;
    const start = Date.now();
    while (!window.DocsAPI) {
      if (Date.now() - start > maxWait) throw new Error('OnlyOffice API timeout');
      await new Promise(r => setTimeout(r, 200));
    }
  },

  /* ── Create a new document from AI content ── */
  async createFromAI(content, title) {
    try {
      const resp = await fetch('/api/doc/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, title: title || 'AI Generated' }),
      });
      if (!resp.ok) throw new Error(`Create failed: ${resp.status}`);
      const data = await resp.json();
      return data.doc_id;
    } catch (err) {
      console.error('[LT-Office] Create failed:', err);
      LT.emit('notify', { msg: '文档创建失败', type: 'error' });
      return null;
    }
  },

  /* ── Stream content into currently open document ── */
  insertText(text) {
    if (!this._editor || !this._iframe) return;
    try {
      // Use postMessage to communicate with OnlyOffice
      this._iframe.contentWindow.postMessage({
        type: 'insertText',
        text: text,
      }, '*');
    } catch (e) {
      // OnlyOffice iframe may not support this directly
    }
  },

  /* ── Annotate with RAG citations ── */
  async annotateCitations(docId, citations) {
    try {
      await fetch('/api/doc/annotate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, citations }),
      });
      // Reopen to show annotations
      this.open(docId, 'oo-editor-container');
    } catch (err) {
      console.error('[OnlyOffice] Annotate failed:', err);
    }
  },

  /* ── Fill template fields ── */
  async fillTemplate(docId, fields) {
    try {
      const resp = await fetch('/api/doc/template/fill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, fields }),
      });
      const data = await resp.json();
      LT.emit('notify', { msg: `已填充 ${data.filled} 个字段`, type: 'success' });
      // Refresh the document
      this.open(docId, 'oo-editor-container');
      return data;
    } catch (err) {
      console.error('[OnlyOffice] Template fill failed:', err);
    }
  },

  /* ── Get document content ── */
  async getContent(docId) {
    try {
      const resp = await fetch(`/api/doc/content/${docId}`);
      return await resp.json();
    } catch { return null; }
  },

  /* ── List documents ── */
  async listDocs() {
    try {
      const resp = await fetch('/api/doc/list');
      return await resp.json();
    } catch { return []; }
  },

  /* ── Delete document ── */
  async deleteDoc(docId) {
    try {
      await fetch(`/api/doc/${docId}`, { method: 'DELETE' });
      LT.emit('notify', { msg: '文档已删除', type: 'success' });
    } catch (err) {
      LT.emit('notify', { msg: '删除失败', type: 'error' });
    }
  },

  /* ── Submit review ── */
  async submitReview(docId, action, comments) {
    try {
      const resp = await fetch(`/api/doc/review/${docId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, comments }),
      });
      return await resp.json();
    } catch { return null; }
  },

  /* ── Cleanup ── */
  destroy() {
    if (this._editor && this._editor.destroyEditor) {
      try { this._editor.destroyEditor(); } catch (e) {}
    }
    this._editor = null;
    this._loaded = false;
    this._iframe = null;
  },

  /* ── Toggle split-screen mode ── */
  toggleSplit() {
    const app = document.querySelector('.app');
    if (app) app.classList.toggle('split');
    const panel = document.getElementById('lto-panel');
    if (panel) panel.classList.toggle('open');
  },
};

window.LTOffice = LTOffice;

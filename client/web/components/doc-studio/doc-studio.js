/* LivingTree Web — Document Studio Component
   OnlyOffice-powered document editor with AI integration */

class DocStudio extends Component {
  constructor(el, props = {}) {
    super(el, props);
    this._docId = null;
    this._mode = 'editor'; // editor | template | review
    this._docs = [];
    this._citations = [];
    this._templateFields = {};
    this._reviewComments = [];
  }

  async init() {
    this.render();
    this.on('doc:open', (d) => this._openDoc(d.docId));
    this.on('doc:create', (d) => this._createDoc(d.content, d.title));
    this.on('studio:list', () => this._loadDocList());
    this.on('studio:template', (d) => this._enterTemplateMode(d.docId));
    this.on('studio:review', (d) => this._enterReviewMode(d.docId));

    OnlyOffice.init();
    this._loadDocList();
  }

  template() {
    if (this._mode === 'list') return this._listTemplate();
    if (this._mode === 'template') return this._templateTemplate();
    if (this._mode === 'review') return this._reviewTemplate();
    return this._editorTemplate();
  }

  /* ── Editor View ── */
  _editorTemplate() {
    return `
<div class="ds-toolbar">
  <div class="ds-toolbar-left">
    <button class="ds-btn ds-btn-icon" data-action="list" title="文档列表">
      <svg width="14" height="14" viewBox="0 0 14 14"><rect x="1" y="2" width="12" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M4 5h7M4 8h5" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>
    </button>
    <span class="ds-title" id="ds-title">文档编辑器</span>
  </div>
  <div class="ds-toolbar-right">
    <button class="ds-btn" data-action="template" title="模板填充">
      <svg width="14" height="14" viewBox="0 0 14 14"><rect x="2" y="3" width="10" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M5 6.5h4M5 8.5h3" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
      <span>模板</span>
    </button>
    <button class="ds-btn" data-action="review" title="审查">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M7 1l2.5 5 5.5.8-4 3.9 1 5.3-5-2.6-5 2.6 1-5.3-4-3.9 5.5-.8z" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>
      <span>审查</span>
    </button>
    <button class="ds-btn" data-action="refresh" title="刷新文档">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M2 7a5 5 0 019-3M12 7a5 5 0 01-9 3" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><path d="M12 1v3H9M2 13v-3h3" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
    </button>
    <button class="ds-btn ds-btn-close" data-action="close" title="关闭分屏">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
  </div>
</div>
<div class="ds-editor-body">
  <div class="ds-editor-view" id="oo-editor-container"></div>
  <div class="ds-panel-right" id="ds-ai-panel">
    <div class="ds-ai-panel-header">AI 助手</div>
    <div class="ds-ai-panel-chat" id="ds-ai-chat"></div>
    <div class="ds-ai-panel-input">
      <textarea id="ds-ai-input" placeholder="输入 AI 指令... (选中文本后可用)" rows="2"></textarea>
      <button class="ds-btn-send" id="ds-ai-send">发送</button>
    </div>
  </div>
</div>`;
  }

  /* ── Document List View ── */
  _listTemplate() {
    const items = this._docs.length
      ? this._docs.map(d => `
          <div class="ds-list-item">
            <div class="ds-list-item-icon">📄</div>
            <div class="ds-list-item-info">
              <div class="ds-list-item-name">${LT.esc(d.title)}</div>
              <div class="ds-list-item-meta">${new Date(d.updated_at * 1000).toLocaleString('zh-CN')}</div>
            </div>
            <div class="ds-list-item-actions">
              <button class="ds-btn-sm" data-action="open" data-id="${d.doc_id}">编辑</button>
              <button class="ds-btn-sm ds-btn-danger" data-action="delete" data-id="${d.doc_id}">删除</button>
            </div>
          </div>`).join('')
      : '<div class="ds-empty">暂无文档。在对话中点击"在 OnlyOffice 中编辑"，或发送内容创建新文档。</div>';

    return `
<div class="ds-toolbar">
  <div class="ds-toolbar-left">
    <button class="ds-btn ds-btn-icon" data-action="back" title="返回编辑器">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M9 3L5 7l4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
    <span class="ds-title">我的文档</span>
  </div>
  <div class="ds-toolbar-right">
    <button class="ds-btn ds-btn-close" data-action="close">关闭</button>
  </div>
</div>
<div class="ds-editor-body">
  <div class="ds-list">${items}</div>
</div>`;
  }

  /* ── Template Fill View ── */
  _templateTemplate() {
    const fields = Object.entries(this._templateFields).map(([k, v]) => `
      <div class="form-group">
        <label class="form-label">${k.replace(/_/g, ' ')}</label>
        <input type="text" class="form-input" id="tf-${k}" value="${LT.esc(v || '')}" placeholder="输入 ${k}...">
      </div>`).join('');

    return `
<div class="ds-toolbar">
  <div class="ds-toolbar-left">
    <button class="ds-btn ds-btn-icon" data-action="back" title="返回编辑器">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M9 3L5 7l4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
    <span class="ds-title">智能模板填充</span>
  </div>
</div>
<div class="ds-editor-body">
  <div class="ds-panel" style="max-width:600px;margin:20px auto">
    <div class="ds-section-title">检测到 ${Object.keys(this._templateFields).length} 个占位字段</div>
    ${fields || '<p style="color:var(--text-tertiary)">未检测到模板字段</p>'}
    <div class="ds-actions" style="margin-top:20px">
      <button class="form-btn form-btn-primary" data-action="fill">AI 智能填充</button>
      <button class="form-btn form-btn-secondary" data-action="manual-fill">手动填充</button>
    </div>
  </div>
</div>`;
  }

  /* ── Review View ── */
  _reviewTemplate() {
    const resolutions = this._reviewResolutions || [];
    const items = resolutions.length
      ? resolutions.map(r => `
          <div class="ds-review-item ds-review-${r.type}">
            <div class="ds-review-type">${r.type === 'delete' ? '🗑️ 删除' : r.type === 'modify' ? '✏️ 修改' : '➕ 补充'}</div>
            <div class="ds-review-text">${LT.esc(r.reason || r.content || '')}</div>
            <div class="ds-review-actions">
              <button class="ds-btn-sm" data-action="approve" data-idx="${resolutions.indexOf(r)}">✅ 采纳</button>
              <button class="ds-btn-sm ds-btn-danger" data-action="reject" data-idx="${resolutions.indexOf(r)}">❌ 拒绝</button>
            </div>
          </div>`).join('')
      : '<div class="ds-empty">暂无审查建议</div>';

    return `
<div class="ds-toolbar">
  <div class="ds-toolbar-left">
    <button class="ds-btn ds-btn-icon" data-action="back" title="返回编辑器">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M9 3L5 7l4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
    <span class="ds-title">AI 审查仲裁</span>
  </div>
  <div class="ds-toolbar-right">
    <button class="ds-btn" data-action="approve-all">✅ 全部采纳</button>
    <button class="ds-btn ds-btn-close" data-action="back">返回</button>
  </div>
</div>
<div class="ds-editor-body">
  <div class="ds-panel" style="max-width:700px;margin:20px auto">
    <div class="ds-section-title">审查意见 (${resolutions.length} 条建议)</div>
    ${items}
  </div>
</div>`;
  }

  /* ── Actions ── */
  async _openDoc(docId) {
    this._docId = docId;
    this._mode = 'editor';
    this.render();
    this._bindToolbar();
    OnlyOffice.open(docId, 'oo-editor-container');

    const info = await OnlyOffice.getContent(docId);
    if (info) {
      document.getElementById('ds-title').textContent = info.title;
      this._templateFields = {};
      info.template_fields?.forEach(f => { this._templateFields[f] = ''; });
    }
  }

  async _createDoc(content, title) {
    const docId = await OnlyOffice.createFromAI(content, title);
    if (docId) {
      OnlyOffice.toggleSplit();
      this._openDoc(docId);
    }
  }

  async _loadDocList() {
    this._docs = await OnlyOffice.listDocs();
    this._mode = 'list';
    this.render();
    this._bindToolbar();
  }

  _enterTemplateMode(docId) {
    this._docId = docId;
    this._mode = 'template';
    this.render();
    this._bindToolbar();
  }

  _enterReviewMode(docId) {
    this._docId = docId;
    this._mode = 'review';
    this.render();
    this._bindToolbar();
  }

  async _aiFillTemplate() {
    // Auto-fill with AI: call backend to suggest values
    if (!this._docId) return;
    const content = await OnlyOffice.getContent(this._docId);
    // For now, fill with placeholders
    const fields = {};
    Object.keys(this._templateFields).forEach(k => {
      fields[k] = `[${k} - AI 自动填充]`;
    });
    await OnlyOffice.fillTemplate(this._docId, fields);
    this._mode = 'editor';
    this._openDoc(this._docId);
  }

  async _manualFillTemplate() {
    const fields = {};
    document.querySelectorAll('[id^="tf-"]').forEach(el => {
      fields[el.id.replace('tf-', '')] = el.value;
    });
    await OnlyOffice.fillTemplate(this._docId, fields);
    this._mode = 'editor';
    this._openDoc(this._docId);
  }

  async _submitReview(action) {
    const result = await OnlyOffice.submitReview(this._docId, action, this._reviewComments);
    if (result) {
      this._reviewResolutions = result.resolutions;
      this._mode = 'review';
      this.render();
      this._bindToolbar();
    }
  }

  _bindToolbar() {
    const E = this.el;
    E.querySelectorAll('[data-action]').forEach(btn => {
      btn.onclick = () => {
        const action = btn.dataset.action;
        const id = btn.dataset.id;
        const idx = btn.dataset.idx;

        switch (action) {
          case 'list': this._loadDocList(); break;
          case 'open': this._openDoc(id); OnlyOffice.toggleSplit(); break;
          case 'delete': OnlyOffice.deleteDoc(id); this._loadDocList(); break;
          case 'back': this._docId ? this._openDoc(this._docId) : this._loadDocList(); break;
          case 'close': OnlyOffice.toggleSplit(); break;
          case 'template': this._enterTemplateMode(this._docId); break;
          case 'review': this._submitReview('review'); break;
          case 'fill': this._aiFillTemplate(); break;
          case 'manual-fill': this._manualFillTemplate(); break;
          case 'refresh': this._docId && this._openDoc(this._docId); break;
          case 'approve-all': this._submitReview('approve'); break;
          case 'approve': this._handleReviewDecision(idx, true); break;
          case 'reject': this._handleReviewDecision(idx, false); break;
        }
      };
    });
  }

  _handleReviewDecision(idx, approved) {
    if (!this._reviewResolutions) return;
    const r = this._reviewResolutions[idx];
    if (r) {
      r.approved = approved;
      this.render();
      this._bindToolbar();
    }
  }

  render() {
    if (this.el) {
      this.el.innerHTML = this.template();
    }
  }

  destroy() {
    OnlyOffice.destroy();
    super.destroy();
  }
}

LT.register('doc-studio', DocStudio);

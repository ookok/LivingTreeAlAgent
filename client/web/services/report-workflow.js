/* ═══════════════════════════════════
   LivingTree — Report Workflow Engine
   Stepper, section cards, checkpoint resume
   ═══════════════════════════════════ */

const ReportWorkflow = {
  _active: null,
  _checkpointKey: 'lt_report_checkpoint',

  /* ── Workflow state ── */
  states: {
    idle:       { icon: '⏳', label: '等待中', pct: 0 },
    collecting: { icon: '📥', label: '数据收集', pct: 15 },
    analyzing:  { icon: '🔬', label: '智能分析', pct: 30 },
    drafting:   { icon: '✍️', label: '草拟章节', pct: 55 },
    reviewing:  { icon: '🔍', label: 'AI审阅', pct: 75 },
    formatting: { icon: '📐', label: '格式排版', pct: 90 },
    exporting:  { icon: '📤', label: '导出文档', pct: 98 },
    done:       { icon: '✅', label: '完成', pct: 100 },
  },
  steps: ['collecting', 'analyzing', 'drafting', 'reviewing', 'formatting', 'exporting'],

  init(reportTitle) {
    this._active = {
      title: reportTitle || '报告生成',
      currentStep: 0,
      sections: [],
      startTime: Date.now(),
      status: 'idle',
    };
    this._saveCheckpoint();
    return this._active;
  },

  advance(step) {
    if (!this._active) return;
    const idx = this.steps.indexOf(step);
    if (idx >= 0) this._active.currentStep = Math.max(this._active.currentStep, idx);
    this._active.status = step;
    this._saveCheckpoint();
  },

  addSection(id, title, content) {
    if (!this._active) return;
    const existing = this._active.sections.find(s => s.id === id);
    if (existing) { existing.content = content; existing.updatedAt = Date.now(); }
    else { this._active.sections.push({ id, title, content, status: 'generated', createdAt: Date.now() }); }
    this._saveCheckpoint();
  },

  complete() {
    if (!this._active) return;
    this._active.currentStep = this.steps.length;
    this._active.status = 'done';
    this._active.endTime = Date.now();
    this._saveCheckpoint();
  },

  /* ── Render stepper in chat ── */
  renderStepper() {
    const wf = this._active;
    if (!wf) return '';
    return `
<div class="wf-stepper">
  <div class="wf-stepper-header">
    <span class="wf-stepper-icon">📄</span>
    <span class="wf-stepper-title">${LT.esc(wf.title)}</span>
    <span class="wf-stepper-time">${this._elapsed()}</span>
  </div>
  <div class="wf-stepper-bar">
    <div class="wf-stepper-fill" style="width:${this._pct()}%">
      <span class="wf-stepper-fill-label">${this._pct()}%</span>
    </div>
  </div>
  <div class="wf-stepper-steps">
    ${this.steps.map((s, i) => {
      const st = this.states[s];
      const done = i < wf.currentStep;
      const current = i === wf.currentStep;
      const cls = done ? 'done' : current ? 'current' : '';
      return `<div class="wf-step ${cls}">
        <div class="wf-step-dot">${done ? '✓' : st.icon}</div>
        <div class="wf-step-label">${st.label}</div>
      </div>`;
    }).join('')}
  </div>
</div>`;
  },

  /* ── Render section cards ── */
  renderSections() {
    const wf = this._active;
    if (!wf || !wf.sections.length) return '';
    return `<div class="wf-sections">
      ${wf.sections.map(s => `
        <div class="wf-section-card">
          <div class="wf-section-header">
            <span class="wf-section-status">📝</span>
            <span class="wf-section-title">${LT.esc(s.title)}</span>
            <span class="wf-section-time">${new Date(s.createdAt).toLocaleTimeString('zh-CN', {hour:'2-digit', minute:'2-digit'})}</span>
          </div>
          <div class="wf-section-preview">${LT.renderer.md(s.content.slice(0, 500))}</div>
          <div class="wf-section-actions">
            <button class="card-btn" onclick="ReportWorkflow.editSection('${s.id}')">✏️ 编辑</button>
            <button class="card-btn" onclick="ReportWorkflow.regenerateSection('${s.id}')">🔄 重生成</button>
            <button class="card-btn card-btn-primary" onclick="LT.emit('doc:create',{content:'${LT.renderer.esc(s.content).replace(/'/g, "\\'")}',title:'${s.title}'})">📄 导入OnlyOffice</button>
          </div>
        </div>`).join('')}
    </div>`;
  },

  editSection(id) {
    const s = this._active?.sections.find(s => s.id === id);
    if (!s) return;
    LT.emit('doc:create', { content: s.content, title: s.title });
    LT.emit('notify', { msg: `已打开"${s.title}"在 OnlyOffice 中编辑`, type: 'success' });
  },

  regenerateSection(id) {
    LT.emit('notify', { msg: '重新生成中...', type: 'info' });
    // Re-trigger generation for this section via AI
  },

  /* ── Render completion summary ── */
  renderSummary() {
    const wf = this._active;
    if (!wf || wf.status !== 'done') return '';
    const elapsed = ((wf.endTime - wf.startTime) / 1000).toFixed(1);
    return `
<div class="wf-summary">
  <div class="wf-summary-header">✅ 报告生成完成</div>
  <div class="wf-summary-stats">
    <div class="wf-summary-stat"><strong>${wf.sections.length}</strong> 章节</div>
    <div class="wf-summary-stat"><strong>${elapsed}s</strong> 耗时</div>
    <div class="wf-summary-stat"><strong>${this._totalChars()}</strong> 字符</div>
  </div>
  <button class="card-btn card-btn-primary" style="width:100%;margin-top:8px" onclick="ReportWorkflow.exportAll()">
    📄 导出完整报告
  </button>
</div>`;
  },

  exportAll() {
    const wf = this._active;
    if (!wf) return;
    const full = `# ${wf.title}\n\n` + wf.sections.map(s => `## ${s.title}\n\n${s.content}`).join('\n\n---\n\n');
    LT.emit('doc:create', { content: full, title: wf.title });
    LT.emit('notify', { msg: '完整报告已导入 OnlyOffice', type: 'success' });
  },

  /* ── Checkpoint: save & resume ── */
  _saveCheckpoint() {
    if (!this._active) return;
    try {
      localStorage.setItem(this._checkpointKey, JSON.stringify(this._active));
      // Also save to IndexedDB for large content
      if (window.Perf) Perf.archiveMessages('__report_checkpoint', [{
        role: 'system', content: JSON.stringify(this._active), timestamp: Date.now()
      }]);
    } catch(e) {}
  },

  resume() {
    try {
      const raw = localStorage.getItem(this._checkpointKey);
      if (raw) {
        this._active = JSON.parse(raw);
        return this._active;
      }
    } catch(e) {}
    return null;
  },

  clear() {
    this._active = null;
    localStorage.removeItem(this._checkpointKey);
  },

  /* ── Helpers ── */
  _pct() {
    const wf = this._active;
    if (!wf) return 0;
    if (wf.status === 'done') return 100;
    return this.states[wf.status]?.pct || Math.min(wf.currentStep / this.steps.length * 100, 95);
  },

  _elapsed() {
    const wf = this._active;
    if (!wf?.startTime) return '';
    const s = Math.round(((wf.endTime || Date.now()) - wf.startTime) / 1000);
    return s < 60 ? `${s}s` : `${Math.floor(s/60)}m${s%60}s`;
  },

  _totalChars() {
    return (this._active?.sections || []).reduce((sum, s) => sum + (s.content?.length || 0), 0).toLocaleString();
  },
};

window.ReportWorkflow = ReportWorkflow;

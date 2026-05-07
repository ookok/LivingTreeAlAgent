class ContextPanel extends Component {
  constructor() {
    super('context-panel');
    this._activeTab = 'context';
    this._tasks = [
      { id: 't1', name: '初始化 Hub', progress: 100, status: 'done' },
      { id: 't2', name: '加载知识库', progress: 100, status: 'done' },
      { id: 't3', name: '注册工具市场', progress: 100, status: 'done' },
      { id: 't4', name: '网络节点发现', progress: 60, status: 'running' },
      { id: 't5', name: '模型预热', progress: 0, status: 'pending' },
    ];
    this._tools = [
      { icon: '🔍', name: '搜索知识库', status: 'ready' },
      { icon: '📝', name: '文档生成', status: 'ready' },
      { icon: '💻', name: '代码执行', status: 'ready' },
      { icon: '🌐', name: '网络搜索', status: 'ready' },
    ];
    this.on('panel:toggle', () => this._toggle());
    this.on('ctx:update', () => { this.render(); if (this._activeTab === 'graph') this._drawGraph(); });
  }

  _toggle() {
    this.el.classList.toggle('open');
    if (this.el.classList.contains('open') && this._activeTab === 'graph') {
      requestAnimationFrame(() => this._drawGraph());
    }
  }

  _switchTab(tab) {
    this._activeTab = tab;
    this.render();
    if (tab === 'graph') requestAnimationFrame(() => this._drawGraph());
  }

  _drawGraph() {
    const c = LT.ge('graph-canvas');
    if (!c) return;
    const ctx = c.getContext('2d'), W = c.width, H = c.height;
    ctx.clearRect(0, 0, W, H);
    const brand = getComputedStyle(document.documentElement).getPropertyValue('--brand-default').trim();
    const nodes = [
      { x: 140, y: 50, r: 18, label: 'AI', c: brand },
      { x: 60, y: 120, r: 14, label: '知识库', c: '#3f85ff' },
      { x: 220, y: 120, r: 14, label: '代码', c: '#9570ff' },
      { x: 100, y: 190, r: 12, label: '文档', c: '#67c23a' },
      { x: 180, y: 190, r: 12, label: '搜索', c: '#00b8f8' },
      { x: 140, y: 240, r: 12, label: '工具', c: '#e28a00' },
    ];
    const edges = [[0, 1], [0, 2], [1, 3], [2, 4], [0, 5]];
    ctx.strokeStyle = 'var(--border-l2)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    edges.forEach(([a, b]) => { ctx.beginPath(); ctx.moveTo(nodes[a].x, nodes[a].y); ctx.lineTo(nodes[b].x, nodes[b].y); ctx.stroke(); });
    ctx.setLineDash([]);
    nodes.forEach(n => {
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fillStyle = n.c; ctx.fill();
      ctx.fillStyle = '#fff'; ctx.font = '9px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(n.label, n.x, n.y);
    });
    const leg = LT.ge('graph-legend');
    if (leg) {
      leg.innerHTML = nodes.slice(1).map(n => `<div class="graph-legend-item"><span class="graph-legend-dot" style="background:${n.c}"></span>${n.label}</div>`).join('');
    }
  }

  template() {
    const st = S.stats();
    const active = S.active();
    const msgs = S.getMsgs(active ? active.id : '');
    const toks = msgs.reduce((s, m) => s + Math.ceil((m.content || '').length / 3), 0);
    const pct = Math.min(toks / 10000 * 100, 100);

    const tabs = ['context', 'tasks', 'tools', 'graph'];
    const tabLabels = { context: '上下文', tasks: '任务', tools: '工具', graph: '知识' };

    return `
<div class="context-panel-header">
  <span class="context-panel-title">上下文</span>
  <button class="context-panel-close" data-action="close">
    <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
  </button>
</div>
<div class="context-tabs">
  ${tabs.map(t => `<button class="context-tab${this._activeTab === t ? ' active' : ''}" data-action="tab" data-tab="${t}">${tabLabels[t]}</button>`).join('')}
</div>
<div class="context-tab-content${this._activeTab === 'context' ? ' active' : ''}" id="tab-context">
  <div class="context-section">
    <div class="context-section-title">会话信息</div>
    <div class="context-info-grid">
      <div class="context-info-item"><span class="context-info-label">模型</span><span class="context-info-value" id="ctx-model">LivingTree v2.1</span></div>
      <div class="context-info-item"><span class="context-info-label">Token</span><span class="context-info-value" id="ctx-tokens">${toks.toLocaleString()}</span></div>
      <div class="context-info-item"><span class="context-info-label">消息</span><span class="context-info-value" id="ctx-msgs">${msgs.length}</span></div>
      <div class="context-info-item"><span class="context-info-label">状态</span><span class="context-info-value" id="ctx-status" style="color:${S.generating ? 'var(--brand-default)' : 'var(--status-success)'}">${S.generating ? '生成中' : '就绪'}</span></div>
    </div>
  </div>
  <div class="context-section">
    <div class="context-section-title">用量</div>
    <div class="context-usage-bar"><div class="context-usage-fill" style="width:${pct}%"></div></div>
    <div class="context-usage-text">${toks.toLocaleString()} / 1M tokens</div>
  </div>
</div>
<div class="context-tab-content${this._activeTab === 'tasks' ? ' active' : ''}" id="tab-tasks">
  <div class="task-list" id="task-list">
    ${this._tasks.map(t => `
    <div class="task-item">
      <div class="task-item-header">
        <span class="task-item-icon">${t.status === 'done' ? '✅' : t.status === 'running' ? '🔄' : '⏳'}</span>
        <span class="task-item-name">${t.name}</span>
        <span class="task-item-status ${t.status}">${t.status === 'done' ? '完成' : t.status === 'running' ? '进行中' : '等待'}</span>
      </div>
      <div class="task-progress-bar"><div class="task-progress-fill" style="width:${t.progress}%"></div></div>
    </div>`).join('')}
  </div>
</div>
<div class="context-tab-content${this._activeTab === 'tools' ? ' active' : ''}" id="tab-tools">
  <div class="context-section">
    <div class="context-section-title">可用工具</div>
    ${this._tools.map(t => `<div class="tool-item"><span class="tool-icon">${t.icon}</span><span class="tool-name">${t.name}</span><span class="tool-status ready">就绪</span></div>`).join('')}
  </div>
</div>
<div class="context-tab-content${this._activeTab === 'graph' ? ' active' : ''}" id="tab-graph">
  <div class="context-section">
    <div class="context-section-title">知识图谱</div>
    <div class="graph-container"><canvas id="graph-canvas" width="280" height="280"></canvas></div>
    <div class="graph-legend" id="graph-legend"></div>
  </div>
</div>`;
  }

  render() {
    super.render();
    this._bindEvents();
  }

  _bindEvents() {
    LT.qsa('[data-action="close"]', this.el).forEach(b => {
      b.onclick = () => { this.el.classList.remove('open'); };
    });
    LT.qsa('[data-action="tab"]', this.el).forEach(b => {
      b.onclick = () => this._switchTab(b.dataset.tab);
    });
  }
}
LT.register('context-panel', new ContextPanel());

class ContextPanel extends Component {
  constructor() {
    super('context-panel');
    this._activeTab = 'context';
    this._tasks = [];
    this._tools = [];
    this._serverData = null;
    this.on('panel:toggle', () => this._toggle());
    this.on('ctx:update', () => this.render());
  }

  async init() {
    this.render();
    try {
      const [tools, status] = await Promise.all([LT.api.tools(), LT.api.status()]);
      this._tools = (tools || []).map(t => ({ icon: '🔧', name: t.name || t, status: 'ready' }));
      this._serverData = status || {};
      this._tasks = this._buildTaskList(status);
    } catch (e) { /* use defaults */ }
    if (!this._tools.length) {
      this._tools = [
        { icon: '🔍', name: '搜索知识库', status: 'ready' },
        { icon: '📝', name: '文档生成', status: 'ready' },
        { icon: '💻', name: '代码执行', status: 'ready' },
        { icon: '🌐', name: '网络搜索', status: 'ready' },
      ];
    }
    this.render();
  }

  _buildTaskList(status) {
    const tasks = [];
    const orch = status?.orchestrator || {};
    const life = status?.life_engine || {};
    const net = status?.network || {};
    if (life.generation !== undefined) tasks.push({ name: '生命引擎', progress: 100, status: 'done' });
    if (orch.total_agents !== undefined) tasks.push({ name: `${orch.total_agents} 智能体就绪`, progress: 100, status: 'done' });
    if (net.status) tasks.push({ name: `网络: ${net.status}`, progress: net.status === 'ok' ? 100 : 50, status: net.status === 'ok' ? 'done' : 'running' });
    if (life.mutations !== undefined) tasks.push({ name: `进化: Gen ${life.generation}`, progress: 100, status: 'done' });
    return tasks.length ? tasks : [
      { name: '系统就绪', progress: 100, status: 'done' },
    ];
  }

  _toggle() {
    this.el.classList.toggle('open');
    if (this.el.classList.contains('open') && this._activeTab === 'knowledge') {
      requestAnimationFrame(() => this._drawGraph());
    }
  }

  _switchTab(tab) {
    this._activeTab = tab;
    this.render();
    this._bindEvents();
    if (tab === 'knowledge') requestAnimationFrame(() => this._drawGraph());
  }

  _drawGraph() {
    const c = LT.ge('graph-canvas'); if (!c) return;
    const ctx = c.getContext('2d'), W = c.width, H = c.height;
    ctx.clearRect(0, 0, W, H);
    const brand = getComputedStyle(document.documentElement).getPropertyValue('--brand-default').trim();
    const skills = this._serverData?.skills || [];
    const tools = this._tools.slice(0, 5);
    const nodes = [
      { x: 140, y: 40, r: 16, label: 'AI', c: brand },
    ];
    tools.forEach((t, i) => {
      const angle = (i / tools.length) * Math.PI * 2 - Math.PI / 2;
      nodes.push({ x: 140 + 80 * Math.cos(angle), y: 140 + 70 * Math.sin(angle), r: 12, label: t.name.slice(0,4), c: ['#3f85ff','#9570ff','#67c23a','#00b8f8','#e28a00'][i] || '#888' });
    });
    const edges = tools.map((_, i) => [0, i + 1]);
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border-l2').trim();
    ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    edges.forEach(([a, b]) => { ctx.beginPath(); ctx.moveTo(nodes[a].x, nodes[a].y); ctx.lineTo(nodes[b].x, nodes[b].y); ctx.stroke(); });
    ctx.setLineDash([]);
    nodes.forEach(n => { ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fillStyle = n.c; ctx.fill(); ctx.fillStyle = '#fff'; ctx.font = '8px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(n.label, n.x, n.y); });
    const leg = LT.ge('graph-legend');
    if (leg) leg.innerHTML = nodes.slice(1).map(n => `<div class="graph-legend-item"><span class="graph-legend-dot" style="background:${n.c}"></span>${n.label}</div>`).join('');
  }

  template() {
    const store = LT.store;
    const active = store.active();
    const msgs = active ? store.getMsgs(active.id) : [];
    const toks = msgs.reduce((s, m) => s + Math.ceil((m.content || '').length / 3), 0);
    const pct = Math.min(toks / 10000 * 100, 100);
    const tabs = ['context', 'tasks', 'tools', 'knowledge', 'experts'];
    const tabLabels = { context: '上下文', tasks: '任务', tools: '工具', knowledge: '知识库', experts: '专家' };
    const sd = this._serverData || {};
    const modelName = sd.model || 'LivingTree v2.1';

    return `
<div class="context-panel-header">
  <span class="context-panel-title">控制台</span>
  <button class="context-panel-close" data-action="close">
    <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
  </button>
</div>
<div class="context-tabs">
  ${tabs.map(t => `<button class="context-tab${this._activeTab===t?' active':''}" data-action="tab" data-tab="${t}">${tabLabels[t]}</button>`).join('')}
</div>

<!-- Context Tab -->
<div class="context-tab-content${this._activeTab==='context'?' active':''}">
  <div class="context-section"><div class="context-section-title">会话信息</div>
    <div class="context-info-grid">
      <div class="context-info-item"><span class="context-info-label">模型</span><span class="context-info-value">${modelName}</span></div>
      <div class="context-info-item"><span class="context-info-label">Token</span><span class="context-info-value">${toks.toLocaleString()}</span></div>
      <div class="context-info-item"><span class="context-info-label">消息</span><span class="context-info-value">${msgs.length}</span></div>
      <div class="context-info-item"><span class="context-info-label">状态</span><span class="context-info-value" style="color:${store.generating?'var(--brand-default)':'var(--status-success)'}">${store.generating?'生成中':'就绪'}</span></div>
    </div>
  </div>
  <div class="context-section"><div class="context-section-title">用量</div>
    <div class="context-usage-bar"><div class="context-usage-fill" style="width:${pct}%"></div></div>
    <div class="context-usage-text">${toks.toLocaleString()} / 1M tokens</div>
  </div>
</div>

<!-- Tasks Tab -->
<div class="context-tab-content${this._activeTab==='tasks'?' active':''}">
  <div class="task-list">${this._tasks.map(t => `
    <div class="task-item"><div class="task-item-header">
      <span class="task-item-icon">${t.status==='done'?'✅':t.status==='running'?'🔄':'⏳'}</span>
      <span class="task-item-name">${t.name}</span>
      <span class="task-item-status ${t.status}">${t.status==='done'?'完成':t.status==='running'?'进行中':'等待'}</span>
    </div>
    <div class="task-progress-bar"><div class="task-progress-fill" style="width:${t.progress}%"></div></div></div>`).join('')}
  </div>
</div>

<!-- Tools Tab -->
<div class="context-tab-content${this._activeTab==='tools'?' active':''}">
  <div class="context-section"><div class="context-section-title">可用工具 (${this._tools.length})</div>
    ${this._tools.map(t => `<div class="tool-item"><span class="tool-icon">${t.icon}</span><span class="tool-name">${LT.esc(t.name)}</span><span class="tool-status ready">就绪</span></div>`).join('')}
  </div>
</div>

<!-- Knowledge Tab (includes graph + KB quick access) -->
<div class="context-tab-content${this._activeTab==='knowledge'?' active':''}">
  <div class="context-section"><div class="context-section-title">知识图谱</div>
    <div class="graph-container"><canvas id="graph-canvas" width="280" height="200"></canvas></div>
    <div class="graph-legend" id="graph-legend"></div>
  </div>
  <div class="context-section">
    <div class="context-section-title">快速操作</div>
    <button class="card-btn card-btn-primary" onclick="window.open('/search.html','_blank')" style="width:100%">
      🔍 智能搜索
    </button>
    <button class="card-btn" onclick="LT.emit('doc:create',{content:'',title:'新文档'})" style="width:100%;margin-top:4px">
      📄 新建文档
    </button>
    <button class="card-btn" onclick="toggleGraphStudio()" style="width:100%;margin-top:4px">
      📊 可视化分析
    </button>
  </div>
</div>

<!-- Experts Tab -->
<div class="context-tab-content${this._activeTab==='experts'?' active':''}">
  <div class="context-section"><div class="context-section-title">专家角色</div>
    <div class="expert-list">
      <div class="expert-item">
        <span class="expert-avatar">📋</span>
        <div class="expert-info">
          <div class="expert-name">环评工程师</div>
          <div class="expert-desc">环境影响评价、标准合规</div>
        </div>
      </div>
      <div class="expert-item">
        <span class="expert-avatar">🔬</span>
        <div class="expert-info">
          <div class="expert-name">数据分析师</div>
          <div class="expert-desc">监测数据、统计分析</div>
        </div>
      </div>
      <div class="expert-item">
        <span class="expert-avatar">⚖️</span>
        <div class="expert-info">
          <div class="expert-name">法务顾问</div>
          <div class="expert-desc">法规解读、风险合规</div>
        </div>
      </div>
      <div class="expert-item">
        <span class="expert-avatar">📝</span>
        <div class="expert-info">
          <div class="expert-name">文档专家</div>
          <div class="expert-desc">报告撰写、格式排版</div>
        </div>
      </div>
      <div class="expert-item">
        <span class="expert-avatar">🌐</span>
        <div class="expert-info">
          <div class="expert-name">网络协调员</div>
          <div class="expert-desc">P2P协作、数据同步</div>
        </div>
      </div>
    </div>
  </div>
</div>`;
  }

  render() { super.render(); this._bindEvents(); }
  _bindEvents() {
    LT.qsa('[data-action="close"]', this.el).forEach(b => b.onclick = () => this.el.classList.remove('open'));
    LT.qsa('[data-action="tab"]', this.el).forEach(b => b.onclick = () => this._switchTab(b.dataset.tab));
  }
}
LT.register('context-panel', ContextPanel);

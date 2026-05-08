/* LivingTree Web — Graph Studio Component
   Unified AntV X6 visualization canvas with mode selector */

class GraphStudio extends Component {
  constructor(el, props = {}) {
    super(el, props);
    this._mode = 'pipeline';
    this._modes = [
      { id: 'pipeline', name: 'Agent 流水线', icon: '🔀' },
      { id: 'knowledge', name: '知识图谱', icon: '🕸️' },
      { id: 'lifecycle', name: '生命观测', icon: '🔄' },
      { id: 'economic', name: '经济决策', icon: '💰' },
      { id: 'ruletree', name: '规则进化', icon: '🧬' },
      { id: 'taskgraph', name: '任务依赖', icon: '📋' },
    ];
    this._data = {};
  }

  init() {
    this.render();
    this._bindEvents();
    // Delay X6 init to let DOM render
    setTimeout(async () => {
      X6Graph.init('x6-canvas');
      const data = await X6Graph.fetchData(this._mode) || {};
      X6Graph.switchMode(this._mode, data);
    }, 200);
  }

  template() {
    const tabs = this._modes.map(m => `
      <button class="gs-tab${m.id === this._mode ? ' active' : ''}" data-mode="${m.id}">
        <span class="gs-tab-icon">${m.icon}</span>
        <span>${m.name}</span>
      </button>`).join('');

    return `
<div class="gs-header">
  <div class="gs-header-left">
    <span class="gs-title">可视化控制台</span>
    <div class="gs-tabs">${tabs}</div>
  </div>
  <div class="gs-header-right">
    <button class="gs-btn" data-action="fit" title="适应画布">
      <svg width="14" height="14" viewBox="0 0 14 14"><rect x="2" y="2" width="10" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M9 2V1h3v3M5 12v1H2v-3M9 12v1h3v-3M5 2V1H2v3" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
    </button>
    <button class="gs-btn" data-action="zoom-in" title="放大">
      <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M9.5 9.5L13 13M4 6h4M6 4v4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
    </button>
    <button class="gs-btn" data-action="zoom-out" title="缩小">
      <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M9.5 9.5L13 13M4 6h4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
    </button>
    <button class="gs-btn" data-action="export-png" title="导出PNG">PNG</button>
    <button class="gs-btn gs-btn-close" data-action="close" title="关闭">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
  </div>
</div>
<div class="gs-body">
  <div class="gs-canvas-wrap" id="x6-canvas-wrap">
    <div class="gs-canvas" id="x6-canvas"></div>
  </div>
  <div class="gs-sidebar">
    <div class="gs-sidebar-section">
      <div class="gs-sidebar-title">图例</div>
      <div id="graph-legend"></div>
    </div>
    <div class="gs-sidebar-section">
      <div class="gs-sidebar-title">信息</div>
      <div class="gs-info" id="graph-info">
        <div class="gs-info-item">
          <span class="gs-info-label">模式</span>
          <span class="gs-info-value" id="gs-info-mode">Agent 流水线</span>
        </div>
        <div class="gs-info-item">
          <span class="gs-info-label">节点</span>
          <span class="gs-info-value" id="gs-info-nodes">-</span>
        </div>
        <div class="gs-info-item">
          <span class="gs-info-label">边</span>
          <span class="gs-info-value" id="gs-info-edges">-</span>
        </div>
      </div>
    </div>
  </div>
</div>`;
  }

  _bindEvents() {
    const E = this.el;
    // Mode tabs
    E.querySelectorAll('[data-mode]').forEach(btn => {
      btn.onclick = async () => {
        this._mode = btn.dataset.mode;
        // Fetch real data from backend
        let data = await X6Graph.fetchData(this._mode);
        if (!data) {
          // Fetch again with explicit call
          try {
            const resp = await fetch(`/api/graph/${this._mode}`);
            if (resp.ok) data = await resp.json();
          } catch(e) {}
        }
        X6Graph.switchMode(this._mode, data || {});
        this._updateInfo();
        E.querySelectorAll('.gs-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('gs-info-mode').textContent = btn.querySelector('span:last-child').textContent;
      };
    });

    // Toolbar buttons
    E.querySelectorAll('[data-action]').forEach(btn => {
      btn.onclick = () => {
        const action = btn.dataset.action;
        const g = X6Graph._graph;
        switch (action) {
          case 'fit': g && g.centerContent(); break;
          case 'zoom-in': g && g.zoom(0.1); break;
          case 'zoom-out': g && g.zoom(-0.1); break;
          case 'export-png': this._exportPNG(); break;
          case 'close': this._close(); break;
        }
      };
    });

    // Update info when graph changes
    if (X6Graph._graph) {
      X6Graph._graph.on('cell:added cell:removed', () => this._updateInfo());
    }
  }

  _updateInfo() {
    if (!X6Graph._graph) return;
    const nodes = X6Graph._graph.getNodes();
    const edges = X6Graph._graph.getEdges();
    const nodesEl = document.getElementById('gs-info-nodes');
    const edgesEl = document.getElementById('gs-info-edges');
    if (nodesEl) nodesEl.textContent = nodes.length;
    if (edgesEl) edgesEl.textContent = edges.length;
  }

  _exportPNG() {
    if (!X6Graph._graph) return;
    X6Graph._graph.toPNG((dataUri) => {
      const a = document.createElement('a');
      a.href = dataUri;
      a.download = `livingtree-${this._mode}-${Date.now()}.png`;
      a.click();
    }, { padding: 20, backgroundColor: '#1a1b1d' });
  }

  _close() {
    const panel = document.getElementById('graph-studio-panel');
    if (panel) panel.style.display = 'none';
  }

  destroy() {
    X6Graph.destroy();
    super.destroy();
  }
}

LT.register('graph-studio', GraphStudio);

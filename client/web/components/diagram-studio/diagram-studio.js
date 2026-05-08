/* LivingTree Web — Diagram Studio
   Report-grade diagram editor: map, PFD, site plan, noise, network, causal, risk */

class DiagramStudio extends Component {
  constructor(el, props = {}) {
    super(el, props);
    this._type = 'contour';
    this._types = [
      { id: 'contour', name: '扩散等值线', icon: '🗺️' },
      { id: 'process-flow', name: '工艺流程', icon: '⚙️' },
      { id: 'site-plan', name: '平面布置', icon: '🏗️' },
      { id: 'noise', name: '噪声剖面', icon: '📉' },
      { id: 'monitoring', name: '监测网络', icon: '📡' },
      { id: 'causal', name: '因果链', icon: '🔗' },
      { id: 'risk', name: '风险矩阵', icon: '⚠️' },
    ];
  }

  init() {
    this.render();
    this._bindEvents();
    setTimeout(() => {
      X6Diagram.init('diagram-canvas');
      X6Diagram.render(this._type, null);
    }, 100);
  }

  template() {
    const tabs = this._types.map(t =>
      `<button class="dgm-tab${t.id === this._type ? ' active' : ''}" data-type="${t.id}">
        <span>${t.icon}</span><span>${t.name}</span></button>`).join('');

    return `
<div class="dgm-header">
  <div class="dgm-header-left">
    <span class="dgm-title">报告图表编辑器</span>
    <div class="dgm-tabs">${tabs}</div>
  </div>
  <div class="dgm-header-right">
    <button class="dgm-btn" data-action="ai-generate" title="AI 自动生成">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M7 1l2.5 5 5.5.8-4 3.9 1 5.3-5-2.6-5 2.6 1-5.3-4-3.9 5.5-.8z" fill="currentColor"/></svg>
      <span>AI 生成</span>
    </button>
    <button class="dgm-btn" data-action="export-svg" title="导出SVG">SVG</button>
    <button class="dgm-btn" data-action="export-png" title="导出PNG">PNG</button>
    <button class="dgm-btn" data-action="insert-doc" title="插入文档">
      <svg width="14" height="14" viewBox="0 0 14 14"><rect x="2" y="3" width="10" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M5 6.5h4M5 8.5h3" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
      <span>插入文档</span>
    </button>
    <button class="dgm-btn dgm-btn-close" data-action="close" title="关闭">✕</button>
  </div>
</div>
<div class="dgm-body">
  <div class="dgm-canvas-wrap">
    <div class="dgm-canvas" id="diagram-canvas"></div>
  </div>
  <div class="dgm-sidebar" id="dgm-sidebar">
    <div class="dgm-sidebar-title">参数配置</div>
    <div class="dgm-params" id="dgm-params">
      <p class="dgm-hint">选择图表类型后，AI 将根据上下文自动填充参数</p>
    </div>
  </div>
</div>`;
  }

  _bindEvents() {
    // Type tabs
    this.el.querySelectorAll('[data-type]').forEach(btn => {
      btn.onclick = () => {
        this._type = btn.dataset.type;
        X6Diagram.render(this._type, null);
        this.el.querySelectorAll('.dgm-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        this._updateParams();
      };
    });

    // Actions
    this.el.querySelectorAll('[data-action]').forEach(btn => {
      btn.onclick = async () => {
        const action = btn.dataset.action;
        switch (action) {
          case 'ai-generate': await this._aiGenerate(); break;
          case 'export-svg': X6Diagram.exportSVG(svg => this._download(svg, 'image/svg+xml', 'svg')); break;
          case 'export-png': X6Diagram.exportPNG(uri => this._downloadURI(uri, 'png')); break;
          case 'insert-doc': this._insertIntoDocument(); break;
          case 'close': this._close(); break;
        }
      };
    });

    this._updateParams();
  },

  _updateParams() {
    const params = document.getElementById('dgm-params');
    if (!params) return;
    const configs = {
      'contour': '扩散源坐标 | 风向角度 | 风速 m/s | 浓度等值线级别',
      'process-flow': '拖拽设备节点 | 双击编辑标签 | 右键添加连接',
      'site-plan': '建筑坐标 | 排放源 | 监测点 | 敏感目标',
      'noise': '声源 dB | 距离衰减序列',
      'monitoring': '监测站坐标 | 监测参数 | 数据传输',
      'causal': '活动→影响→受体→措施 四层因果',
      'risk': '概率等级 | 后果等级 | 风险项定位',
    };
    params.innerHTML = `
      <div class="dgm-param-info">${configs[this._type] || 'AI 将自动填充参数'}</div>
      <div class="dgm-param-actions">
        <button class="form-btn form-btn-primary" data-action="ai-generate" onclick="document.querySelector('[data-action=ai-generate]').click()">
          🤖 AI 自动生成
        </button>
      </div>`;
  },

  async _aiGenerate() {
    // Generate diagram data from AI based on document context
    LT.emit('notify', { msg: 'AI 正在生成图表...', type: 'info' });
    try {
      const resp = await fetch('/api/diagram/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: this._type, context: 'report' }),
      });
      if (resp.ok) {
        const data = await resp.json();
        X6Diagram.render(this._type, data.config || data);
        LT.emit('notify', { msg: '图表已生成', type: 'success' });
      }
    } catch (e) {
      LT.emit('notify', { msg: 'AI 生成失败，使用默认数据', type: 'warning' });
    }
  },

  _insertIntoDocument() {
    X6Diagram.exportPNG(dataUri => {
      // Insert into OnlyOffice via the AI panel
      const imgHtml = `<img src="${dataUri}" alt="LivingTree Diagram" style="max-width:100%">`;
      // Emit event for doc-studio to handle
      LT.emit('diagram:insert', { html: imgHtml, dataUri, type: this._type });
      LT.emit('notify', { msg: '图表已插入文档', type: 'success' });
    });
  },

  _download(content, mime, ext) {
    const blob = new Blob([content], { type: mime });
    this._downloadURI(URL.createObjectURL(blob), ext);
  },

  _downloadURI(uri, ext) {
    const a = document.createElement('a');
    a.href = uri; a.download = `diagram-${this._type}-${Date.now()}.${ext}`;
    a.click();
    if (uri.startsWith('blob:')) URL.revokeObjectURL(uri);
  },

  _close() {
    const panel = document.getElementById('diagram-studio-panel');
    if (panel) panel.style.display = 'none';
  },

  destroy() {
    X6Diagram.destroy();
    super.destroy();
  },
}

LT.register('diagram-studio', DiagramStudio);

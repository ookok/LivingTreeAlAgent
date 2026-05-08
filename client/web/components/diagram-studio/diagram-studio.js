/* LivingTree Web — Diagram Studio
   Report-grade diagram editor: map, PFD, site plan, noise, network, causal, risk */

class DiagramStudio extends Component {
  constructor(el, props = {}) {
    super(el, props);
    this._type = 'contour';
    this._types = [
      { id: 'base-map', name: '底图标注', icon: '📍' },
      { id: 'contour', name: '扩散等值线', icon: '🗺️' },
      { id: 'process-flow', name: '工艺流程', icon: '⚙️' },
      { id: 'site-plan', name: '平面布置', icon: '🏗️' },
      { id: 'noise', name: '噪声剖面', icon: '📉' },
      { id: 'monitoring', name: '监测网络', icon: '📡' },
      { id: 'causal', name: '因果链', icon: '🔗' },
      { id: 'risk', name: '风险矩阵', icon: '⚠️' },
    ];
    this._drawTool = null;
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

    const drawToolbar = this._type === 'base-map' ? `
<div class="dgm-drawbar" id="dgm-drawbar">
  <span class="dgm-drawbar-label">标注工具:</span>
  <button class="dgm-draw-btn${this._drawTool === 'pin' ? ' active' : ''}" data-draw="pin" title="标记点">
    <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="5" r="3" fill="currentColor"/><path d="M7 8v5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
  </button>
  <button class="dgm-draw-btn${this._drawTool === 'circle' ? ' active' : ''}" data-draw="circle" title="距离圈">
    <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="3 2"/></svg>
  </button>
  <button class="dgm-draw-btn${this._drawTool === 'rect' ? ' active' : ''}" data-draw="rect" title="矩形区域">
    <svg width="14" height="14" viewBox="0 0 14 14"><rect x="2" y="3" width="10" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
  </button>
  <button class="dgm-draw-btn${this._drawTool === 'text' ? ' active' : ''}" data-draw="text" title="文字标注">
    <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 4h8M5 2l2 10M9 2l2 10" stroke="currentColor" stroke-width="1.3" fill="none" stroke-linecap="round"/></svg>
  </button>
  <span class="dgm-drawbar-sep"></span>
  <button class="dgm-draw-btn" data-draw="clear" title="清除绘制模式">✕</button>
  <span style="font-size:11px;color:var(--text-tertiary);margin-left:4px">${this._drawTool ? '点击画布放置' : '选择工具后点击画布'}</span>
</div>` : '';

    const imgUpload = this._type === 'base-map' ? `
<div class="dgm-img-upload" id="dgm-img-upload" onclick="document.getElementById('dgm-img-input').click()">
  <svg width="20" height="20" viewBox="0 0 20 20"><rect x="3" y="3" width="14" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="7" cy="7" r="2" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M3 14l4-4 3 3 2-2 5 5" stroke="currentColor" stroke-width="1.2" fill="none"/></svg>
  <span>上传底图 (或拖拽图片到此处)</span>
  <input type="file" id="dgm-img-input" accept="image/*" style="display:none">
</div>` : '';

    const scenarios = this._type === 'base-map' ? `
<div class="dgm-scenarios">
  <span class="dgm-drawbar-label">快速场景:</span>
  <button class="dgm-scenario-btn" data-scenario="distance">防护距离图</button>
  <button class="dgm-scenario-btn" data-scenario="windrose">风向玫瑰+距离圈</button>
  <button class="dgm-scenario-btn" data-scenario="monitor">监测点位图</button>
</div>` : '';

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
${drawToolbar}
<div class="dgm-body">
  <div class="dgm-canvas-wrap" id="dgm-canvas-wrap">
    ${imgUpload}
    <div class="dgm-canvas" id="diagram-canvas"></div>
  </div>
  <div class="dgm-sidebar" id="dgm-sidebar">
    <div class="dgm-sidebar-title">参数配置</div>
    <div class="dgm-params" id="dgm-params">
      <p class="dgm-hint">选择图表类型后，AI 将根据上下文自动填充参数</p>
    </div>
    ${scenarios}
  </div>
</div>`;
  }

  _bindEvents() {
    // Type tabs
    this.el.querySelectorAll('[data-type]').forEach(btn => {
      btn.onclick = async () => {
        this._type = btn.dataset.type;
        this._drawTool = null;
        X6Diagram.setDrawTool(null);

        // Fetch real data from backend
        let data = null;
        try {
          const resp = await fetch('/api/diagram/generate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: this._type, context: 'report' }),
          });
          if (resp.ok) {
            const result = await resp.json();
            data = result.config;
          }
        } catch (e) {}

        X6Diagram.render(this._type, data);
        this.render();
        this._bindEvents();
      };
    });

    // Drawing tools (base-map)
    this.el.querySelectorAll('[data-draw]').forEach(btn => {
      btn.onclick = () => {
        const tool = btn.dataset.draw;
        if (tool === 'clear') {
          this._drawTool = null;
          X6Diagram.setDrawTool(null);
        } else {
          this._drawTool = tool;
          X6Diagram.setDrawTool(tool);
        }
        this.render();
        this._bindEvents();
      };
    });

    // Scenario buttons
    this.el.querySelectorAll('[data-scenario]').forEach(btn => {
      btn.onclick = () => {
        X6Diagram.renderBaseMap({ scenario: btn.dataset.scenario });
        LT.emit('notify', { msg: '场景已加载', type: 'info' });
      };
    });

    // Image upload
    const imgInput = this.el.querySelector('#dgm-img-input');
    if (imgInput) {
      imgInput.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            X6Diagram.setBaseImage(ev.target.result);
            this.render();
            this._bindEvents();
          };
          reader.readAsDataURL(file);
        }
      };
    }

    // Drag-drop image onto canvas
    const canvasWrap = this.el.querySelector('#dgm-canvas-wrap');
    if (canvasWrap) {
      canvasWrap.addEventListener('dragover', e => e.preventDefault());
      canvasWrap.addEventListener('drop', e => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            X6Diagram.setBaseImage(ev.target.result);
            this.render();
            this._bindEvents();
          };
          reader.readAsDataURL(file);
        }
      });
    }

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
      'base-map': '上传底图 → 选择标注工具(标记点/距离圈/矩形/文字) → 点击画布放置 → 拖拽调整位置',
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

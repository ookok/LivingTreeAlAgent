class ModelsPanel extends Component {
  constructor() {
    super('models-modal');
    this._data = [];
    this._loading = true;
    this.on('models:open', () => this._open());
  }

  _open() {
    this.el.style.display = 'flex';
    this._loading = true;
    this.render();
    fetch('/tree/admin/models')
      .then(r => r.text())
      .then(html => {
        this._data = html;
        this._loading = false;
        this.render();
      })
      .catch(() => {
        this._loading = false;
        this._data = '<p style="color:var(--dim)">加载失败</p>';
        this.render();
      });
  }

  _close() { this.el.style.display = 'none'; }

  template() {
    return `
<div class="modal-panel" style="width:900px;max-width:95vw;height:85vh" onclick="event.stopPropagation()">
  <div class="modal-header">
    <span class="modal-title">📊 模型选举仪表盘</span>
    <button class="modal-close" data-action="close">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
  </div>
  <div class="modal-body" style="overflow-y:auto;padding:0">
    ${this._loading ? '<div style="text-align:center;padding:40px;color:var(--dim)">加载模型选举数据...</div>' : this._data}
  </div>
</div>`;
  }

  render() {
    super.render();
    var self = this;
    this.el.querySelectorAll('[data-action="close"]').forEach(function(b) {
      b.onclick = function() { self._close(); };
    });
    this.el.onclick = function(e) { if (e.target === self.el) self._close(); };
  }
}
LT.register('models', ModelsPanel);

class Settings extends Component {
  constructor() {
    super('settings-modal');
    this._load();
    this.on('settings:open', () => this._open());
    this.on('settings:close', () => this._close());
  }

  _load() {
    this._state = {
      api: localStorage.lt_api_base || '/api',
      model: localStorage.lt_model || 'auto',
      lang: document.documentElement.lang || 'zh-CN',
      thinking: localStorage.getItem('lt_thinking') === '1',
    };
  }

  _open() { this.el.style.display = 'flex'; this._load(); this.render(); }
  _close() { this.el.style.display = 'none'; }

  _save() {
    localStorage.lt_thinking = document.getElementById('setting-thinking').checked ? '1' : '0';
    this._close();
    LT.emit('notify', { msg: '设置已保存', type: 'success' });
  }

  template() {
    var s = this._state;
    return `
<div class="modal-panel" onclick="event.stopPropagation()">
  <div class="modal-header">
    <span class="modal-title">设置</span>
    <button class="modal-close" data-action="close">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
  </div>
  <div class="modal-body">
    <div class="form-group">
      <label class="form-label">默认模型</label>
      <select class="form-select" id="setting-model">
        <option value="auto"${s.model==='auto'?' selected':''}>自动选举</option>
        <option value="deepseek"${s.model==='deepseek'?' selected':''}>DeepSeek V4</option>
        <option value="openrouter"${s.model==='openrouter'?' selected':''}>OpenRouter</option>
        <option value="zhipu"${s.model==='zhipu'?' selected':''}>智谱 GLM</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-check">
        <input type="checkbox" id="setting-thinking"${s.thinking?' checked':''}>
        <span class="form-check-label" style="margin-left:8px">🧠 显示思考过程</span>
      </label>
      <div style="font-size:10px;color:var(--text-secondary);margin-top:4px;margin-left:24px">支持thinking的模型将展示推理链</div>
    </div>
  </div>
  <div class="modal-footer">
    <button class="form-btn form-btn-secondary" data-action="close">取消</button>
    <button class="form-btn form-btn-primary" data-action="save">保存</button>
  </div>
</div>`;
  </div>
</div>`;
  }

  render() {
    super.render();
    LT.qsa('[data-action="close"]', this.el).forEach(b => {
      b.onclick = () => this._close();
    });
    LT.qs('[data-action="save"]', this.el).onclick = () => this._save();
    this.el.onclick = (e) => { if (e.target === this.el) this._close(); };
  }
}
LT.register('settings', Settings);

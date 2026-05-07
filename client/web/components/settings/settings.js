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
      fontsize: parseInt(getComputedStyle(document.documentElement).getPropertyValue('--font-size-base')) || 13,
      stream: localStorage.lt_stream !== '0',
    };
  }

  _open() { this.el.style.display = 'flex'; this._load(); this.render(); }
  _close() { this.el.style.display = 'none'; }

  _save() {
    const api = LT.ge('setting-api').value;
    if (api) localStorage.lt_api_base = api;
    localStorage.lt_model = LT.ge('setting-model').value;
    const lang = LT.ge('setting-lang').value;
    document.documentElement.lang = lang;
    const fs = LT.ge('setting-fontsize').value;
    document.documentElement.style.setProperty('--font-size-base', fs + 'px');
    localStorage.lt_fontsize = fs;
    localStorage.lt_stream = LT.ge('setting-stream').checked ? '1' : '0';
    this._close();
    LT.emit('notify', { msg: '设置已保存', type: 'success' });
  }

  template() {
    const s = this._state;
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
      <label class="form-label">API 端点</label>
      <input type="text" class="form-input" id="setting-api" placeholder="/api" value="${LT.esc(s.api)}">
    </div>
    <div class="form-group">
      <label class="form-label">默认模型</label>
      <select class="form-select" id="setting-model">
        <option value="auto"${s.model === 'auto' ? ' selected' : ''}>自动选择</option>
        <option value="deepseek"${s.model === 'deepseek' ? ' selected' : ''}>DeepSeek V4</option>
        <option value="longcat"${s.model === 'longcat' ? ' selected' : ''}>LongCat</option>
        <option value="siliconflow"${s.model === 'siliconflow' ? ' selected' : ''}>SiliconFlow</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">界面语言</label>
      <select class="form-select" id="setting-lang">
        <option value="zh-CN"${s.lang === 'zh-CN' ? ' selected' : ''}>简体中文</option>
        <option value="en"${s.lang === 'en' ? ' selected' : ''}>English</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">字体大小</label>
      <div class="form-range-row">
        <span style="font-size:11px">A</span>
        <input type="range" class="form-range" id="setting-fontsize" min="11" max="16" value="${s.fontsize}" oninput="document.documentElement.style.setProperty('--font-size-base', this.value+'px')">
        <span style="font-size:16px">A</span>
      </div>
    </div>
    <div class="form-group">
      <label class="form-check">
        <input type="checkbox" id="setting-stream"${s.stream ? ' checked' : ''}>
        <span class="form-check-label">启用流式输出</span>
      </label>
    </div>
  </div>
  <div class="modal-footer">
    <button class="form-btn form-btn-secondary" data-action="close">取消</button>
    <button class="form-btn form-btn-primary" data-action="save">保存</button>
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

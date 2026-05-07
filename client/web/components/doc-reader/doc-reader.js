class DocReader extends Component {
  constructor() {
    super('doc-reader-modal');
    this._data = null;
    this._editMode = false;
    this.on('doc-reader:open', (data) => this._open(data));
    this.on('doc-reader:close', () => this._close());
  }

  _open(data) {
    this._data = data || {};
    this._editMode = false;
    this.el.style.display = 'flex';
    this.render();
  }

  _close() { this.el.style.display = 'none'; }

  _toggleEdit() {
    this._editMode = !this._editMode;
    this.render();
  }

  _saveEdit() {
    const code = LT.ge('doc-editor').value;
    if (this._data) this._data.code = code;
    this._editMode = false;
    this.render();
    LT.emit('notify', { msg: '文档已保存', type: 'success' });
  }

  _download(fmt) {
    const code = this._editMode ? LT.ge('doc-editor').value : (this._data.code || '');
    const title = (this._data.title || 'document').replace(/[^a-zA-Z\u4e00-\u9fff0-9]/g, '_');
    const blob = new Blob([code], { type: fmt === 'md' ? 'text/markdown' : 'text/plain' });
    const u = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = u; a.download = title + '.' + (fmt === 'md' ? 'md' : 'txt');
    a.click(); URL.revokeObjectURL(u);
  }

  _print() {
    const code = this._editMode ? LT.ge('doc-editor').value : (this._data.code || '');
    const w = window.open('', '_blank');
    w.document.write(`<pre style="font-family:monospace;font-size:13px;line-height:1.6;padding:20px;white-space:pre-wrap">${LT.esc(code)}</pre>`);
    w.document.close();
    setTimeout(() => w.print(), 500);
  }

  _toc(code) {
    const headings = [...code.matchAll(/^(#{1,3})\s+(.+)$/gm)];
    if (!headings.length) return '';
    return `
<div class="doc-toc" id="doc-toc">
  <div class="doc-toc-title">目录</div>
  ${headings.map(([, h, title]) => {
    const level = h.length;
    const cls = level === 2 ? 'h2' : level === 3 ? 'h3' : '';
    return `<a class="doc-toc-item ${cls}" href="javascript:void(0)">${LT.esc(title)}</a>`;
  }).join('')}
</div>`;
  }

  template() {
    const code = this._data.code || '';
    const title = this._data.title || '文档';
    const rendered = R.md(code);
    return `
<div class="modal-panel" style="width:800px;max-width:95vw;height:85vh" onclick="event.stopPropagation()">
  <div class="modal-header">
    <span class="modal-title" id="doc-reader-title">${LT.esc(title)}</span>
    <div class="modal-header-actions">
      <button class="form-btn form-btn-secondary" style="height:28px;font-size:12px" data-action="edit">${this._editMode ? '阅读' : '编辑'}</button>
      <button class="form-btn form-btn-secondary" style="height:28px;font-size:12px" data-action="dl-md">.md</button>
      <button class="form-btn form-btn-secondary" style="height:28px;font-size:12px" data-action="dl-txt">.txt</button>
      <button class="form-btn form-btn-secondary" style="height:28px;font-size:12px" data-action="print">打印</button>
      <button class="modal-close" data-action="close">
        <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </button>
    </div>
  </div>
  <div class="modal-body" style="overflow:auto">
    ${this._editMode ? '' : this._toc(code)}
    <div class="doc-content" id="doc-reader-content" style="display:${this._editMode ? 'none' : 'block'}">${rendered}</div>
    <textarea class="doc-editor" id="doc-editor" style="display:${this._editMode ? 'block' : 'none'}">${LT.esc(code)}</textarea>
  </div>
  <div class="modal-footer" style="display:${this._editMode ? 'flex' : 'none'}">
    <button class="form-btn form-btn-secondary" data-action="edit">取消</button>
    <button class="form-btn form-btn-primary" data-action="save">保存</button>
  </div>
</div>`;
  }

  render() {
    super.render();
    const E = this.el;
    LT.qsa('[data-action="close"]', E).forEach(b => { b.onclick = () => this._close(); });
    const editBtn = LT.qs('[data-action="edit"]', E);
    if (editBtn) editBtn.onclick = () => this._toggleEdit();
    const saveBtn = LT.qs('[data-action="save"]', E);
    if (saveBtn) saveBtn.onclick = () => this._saveEdit();
    const dlMd = LT.qs('[data-action="dl-md"]', E);
    if (dlMd) dlMd.onclick = () => this._download('md');
    const dlTxt = LT.qs('[data-action="dl-txt"]', E);
    if (dlTxt) dlTxt.onclick = () => this._download('txt');
    const printBtn = LT.qs('[data-action="print"]', E);
    if (printBtn) printBtn.onclick = () => this._print();
    E.onclick = (e) => { if (e.target === E) this._close(); };
  }
}
LT.register('doc-reader', DocReader);

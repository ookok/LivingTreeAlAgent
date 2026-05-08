/* ═══════════════════════════════════
   LivingTree Web — Monaco Code Editor Component
   Loads Monaco from CDN, provides full IDE editing
   ═══════════════════════════════════ */

class CodeEditor extends Component {
  constructor(el, props = {}) {
    super(el, props);
    this._editor = null;
    this._monaco = null;
    this._files = {};           // { path: { code, lang, editor, isProjectFile } }
    this._activeFile = null;
    this._loaded = false;
    this._codeMode = false;
    this._projectTreeCache = null;
  }

  async init() {
    this.render();
    await this._loadMonaco();
    this._setupFileTree();
    this._listenEvents();
  }

  template() {
    return `
      <div class="ce-container">
        <div class="ce-toolbar">
          <span class="ce-title">代码编辑器</span>
          <div class="ce-toolbar-actions">
            <select class="ce-lang-select" id="ce-lang" onchange="this._onLangChange()"><option value="plaintext">Plain Text</option><option value="javascript">JavaScript</option><option value="typescript">TypeScript</option><option value="python">Python</option><option value="html">HTML</option><option value="css">CSS</option><option value="json">JSON</option><option value="markdown">Markdown</option><option value="sql">SQL</option><option value="yaml">YAML</option><option value="bash">Shell</option><option value="java">Java</option><option value="go">Go</option><option value="rust">Rust</option><option value="cpp">C++</option></select>
            <button class="ce-btn" title="格式化" onclick="LT.emit('editor:format')"><svg width="14" height="14" viewBox="0 0 14 14"><path d="M2 2h10M2 5h8M2 8h6M2 11h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg></button>
            <button class="ce-btn" title="下载" onclick="LT.emit('editor:download')"><svg width="14" height="14" viewBox="0 0 14 14"><path d="M7 1v8M3 6l4 4 4-4M2 12h10" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg></button>
            <button class="ce-btn" title="复制" onclick="LT.emit('editor:copy')"><svg width="14" height="14" viewBox="0 0 14 14"><rect x="3.5" y="3.5" width="8" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M10.5 3.5V2a1 1 0 00-1-1H2a1 1 0 00-1 1v6a1 1 0 001 1h1.5" fill="none" stroke="currentColor" stroke-width="1.2"/></svg></button>
          </div>
        </div>
        <div class="ce-body">
          <div class="ce-file-tree" id="ce-file-tree">
            <div class="ce-file-tree-header">
              <span id="ce-tree-title">文件</span>
              <button class="ce-refresh-btn" title="刷新" onclick="LT.emit('code:refreshTree')" style="display:none" id="ce-refresh-btn">
                <svg width="12" height="12" viewBox="0 0 12 12"><path d="M2 5a4 4 0 015.7-3.5M10 7a4 4 0 01-5.7 3.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
              </button>
            </div>
            <div class="ce-file-list" id="ce-file-list">
              <div class="ce-empty">暂无文件</div>
            </div>
          </div>
          <div class="ce-editor-container" id="ce-editor-container">
            <div class="ce-loading" id="ce-loading">加载编辑器...</div>
          </div>
        </div>
      </div>
    `;
  }

  async _loadMonaco() {
    if (window.monaco) { this._monaco = window.monaco; this._createEditor(); return; }
    const loading = LT.ge('ce-loading');
    if (loading) loading.textContent = '加载 Monaco Editor...';

    return new Promise((resolve) => {
      require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });
      require(['vs/editor/editor.main'], (monaco) => {
        this._monaco = monaco;
        this._loaded = true;
        if (loading) loading.style.display = 'none';
        this._createEditor();
        resolve();
      });
    });
  }

  _createEditor() {
    const container = LT.ge('ce-editor-container');
    if (!container || !this._monaco) return;

    this._editor = this._monaco.editor.create(container, {
      value: '// 点击左侧文件或发送代码块到此处编辑\n',
      language: 'javascript',
      theme: 'vs-dark',
      fontSize: 13,
      fontFamily: '"JetBrains Mono", "Fira Code", Consolas, monospace',
      lineNumbers: 'on',
      minimap: { enabled: true, scale: 1, showSlider: 'mouseover' },
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      tabSize: 4,
      automaticLayout: true,
      bracketPairColorization: { enabled: true },
      renderWhitespace: 'selection',
      smoothScrolling: true,
      cursorBlinking: 'smooth',
      cursorSmoothCaretAnimation: 'on',
      padding: { top: 8 },
    });

    this._editor.addAction({
      id: 'save-content',
      label: 'Save',
      keybindings: [this._monaco.KeyMod.CtrlCmd | this._monaco.KeyCode.KeyS],
      run: () => this._saveCurrent(),
    });
  }

  _setupFileTree() {
    // Open a default file
    this.openFile('untitled.js', 'javascript', '// 在此处编写代码\n');
  }

  _listenEvents() {
    this.on('editor:open', ({ path, code, lang }) => this.openFile(path || 'code.js', lang, code));
    this.on('editor:open-code', ({ code, lang }) => this.openFile(`code.${lang || 'txt'}`, lang, code));
    this.on('editor:format', () => this._format());
    this.on('editor:download', () => this._download());
    this.on('editor:copy', () => this._copyAll());
    this.on('editor:save', () => this._saveCurrent());
    this.on('codemode:changed', (active) => {
      this._codeMode = active;
      if (active) {
        this._loadProjectTree();
      } else {
        this._projectTreeCache = null;
        this._renderFileList();
      }
    });
    // Refresh project tree when file is saved externally
    this.on('code:refreshTree', () => this._loadProjectTree());
  }

  openFile(path, lang, code) {
    if (!this._files[path]) {
      this._files[path] = { code, lang };
    } else if (code !== undefined) {
      this._files[path].code = code;
    }
    this._activeFile = path;
    this._setEditorContent(this._files[path].code, this._files[path].lang);
    this._updateLangSelect(this._files[path].lang);
    this._renderFileList();
  }

  _setEditorContent(code, lang) {
    if (!this._editor || !this._monaco) return;
    const model = this._editor.getModel();
    if (model) {
      model.setValue(code || '');
      this._monaco.editor.setModelLanguage(model, lang || 'plaintext');
    }
  }

  _updateLangSelect(lang) {
    const sel = LT.ge('ce-lang');
    if (sel) sel.value = lang || 'plaintext';
  }

  _renderFileList() {
    const list = LT.ge('ce-file-list');
    if (!list) return;
    const files = Object.keys(this._files);
    if (!files.length) { list.innerHTML = '<div class="ce-empty">暂无文件</div>'; return; }
    list.innerHTML = files.map(f => {
      const active = f === this._activeFile ? ' active' : '';
      const icon = this._fileIcon(f);
      return `<div class="ce-file-item${active}" onclick="LT.emit('editor:open',{path:'${LT.esc(f)}',lang:'${this._files[f].lang}',code:undefined})">
        <span class="ce-file-icon">${icon}</span>
        <span class="ce-file-name">${LT.esc(f)}</span>
        ${files.length > 1 ? `<button class="ce-file-close" onclick="event.stopPropagation();LT.emit('editor:closeFile','${LT.esc(f)}')">✕</button>` : ''}
      </div>`;
    }).join('');
  }

  _fileIcon(name) {
    const ext = name.split('.').pop();
    const m = { js: '📜', ts: '🔷', py: '🐍', html: '🌐', css: '🎨', json: '📋', md: '📝', sql: '🗄️', yaml: '⚙️', yml: '⚙️', sh: '💻', java: '☕', go: '🔵', rs: '🦀', cpp: '⚡', c: '⚡', txt: '📄' };
    return m[ext] || '📄';
  }

  _format() {
    if (!this._editor || !this._monaco) return;
    this._editor.getAction('editor.action.formatDocument')?.run();
  }

  _download() {
    if (!this._activeFile || !this._editor) return;
    const code = this._editor.getValue();
    const blob = new Blob([code], { type: 'text/plain' });
    const u = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = u; a.download = this._activeFile; a.click();
    URL.revokeObjectURL(u);
  }

  _copyAll() {
    if (!this._editor) return;
    navigator.clipboard.writeText(this._editor.getValue()).then(() =>
      LT.emit('notify', { msg: '已复制到剪贴板', type: 'success' }));
  }

  _saveCurrent() {
    if (!this._activeFile || !this._editor) return;
    this._files[this._activeFile].code = this._editor.getValue();
    this._files[this._activeFile].lang = LT.ge('ce-lang')?.value || 'plaintext';
    LT.emit('notify', { msg: `已保存: ${this._activeFile}`, type: 'success' });
    LT.emit('editor:saved', { path: this._activeFile, code: this._editor.getValue(), lang: this._files[this._activeFile].lang });
  }

  _onLangChange() {
    const lang = LT.ge('ce-lang')?.value;
    if (!lang || !this._editor || !this._monaco || !this._activeFile) return;
    this._files[this._activeFile].lang = lang;
    this._monaco.editor.setModelLanguage(this._editor.getModel(), lang);
  }

  /* ── Code Mode: Project File Tree ── */

  async _loadProjectTree(dirPath = '') {
    if (!LT.api || !LT.api.codeListFiles) return;
    const project = LT.store.selectedProject || '';
    if (!project) {
      this._projectTreeCache = null;
      this._renderFileList();
      return;
    }
    const refreshBtn = LT.ge('ce-refresh-btn');
    const treeTitle = LT.ge('ce-tree-title');
    if (refreshBtn) refreshBtn.style.display = '';
    if (treeTitle) treeTitle.textContent = dirPath ? dirPath : project;

    const data = await LT.api.codeListFiles(dirPath, project);
    if (!data) {
      this._projectTreeCache = { path: dirPath, items: [] };
      this._renderFileList();
      return;
    }
    this._projectTreeCache = data;
    this._renderFileList();
  }

  _renderFileList() {
    const list = LT.ge('ce-file-list');
    if (!list) return;

    // Code mode: show project tree
    if (this._codeMode && this._projectTreeCache) {
      this._renderProjectTree(list);
      return;
    }

    // Normal mode: show in-memory files
    const files = Object.keys(this._files);
    if (!files.length) { list.innerHTML = '<div class="ce-empty">暂无文件</div>'; return; }
    list.innerHTML = files.map(f => {
      const active = f === this._activeFile ? ' active' : '';
      const icon = this._fileIcon(f);
      return `<div class="ce-file-item${active}" onclick="LT.emit('editor:open',{path:'${LT.esc(f)}',lang:'${this._files[f].lang}',code:undefined})">
        <span class="ce-file-icon">${icon}</span>
        <span class="ce-file-name">${LT.esc(f)}</span>
        ${files.length > 1 ? `<button class="ce-file-close" onclick="event.stopPropagation();LT.emit('editor:closeFile','${LT.esc(f)}')">✕</button>` : ''}
      </div>`;
    }).join('');
  }

  _renderProjectTree(list) {
    const { path: currentPath, items } = this._projectTreeCache;
    let html = '';

    // Breadcrumb / back navigation
    if (currentPath && currentPath !== '.') {
      const parent = currentPath.includes('/') ? currentPath.split('/').slice(0, -1).join('/') : '';
      html += `<div class="ce-file-item ce-breadcrumb" onclick="LT.get('code-editor')._loadProjectTree('${LT.esc(parent)}')">
        <span class="ce-file-icon">📂</span>
        <span class="ce-file-name">.. (上级目录)</span>
      </div>`;
    }

    const dirs = items.filter(i => i.type === 'dir');
    const files = items.filter(i => i.type === 'file');

    for (const d of dirs) {
      html += `<div class="ce-file-item ce-dir-item" onclick="LT.get('code-editor')._loadProjectTree('${LT.esc(d.path)}')">
        <span class="ce-file-icon">📁</span>
        <span class="ce-file-name">${LT.esc(d.name)}</span>
        <span class="ce-file-arrow">▶</span>
      </div>`;
    }

    for (const f of files) {
      const isActive = this._activeFile === f.path;
      const icon = this._fileIcon(f.name);
      html += `<div class="ce-file-item ce-file-row${isActive ? ' active' : ''}" onclick="LT.get('code-editor')._openProjectFile('${LT.esc(f.path)}')">
        <span class="ce-file-icon">${icon}</span>
        <span class="ce-file-name">${LT.esc(f.name)}</span>
        <span class="ce-file-size">${this._formatSize(f.size)}</span>
      </div>`;
    }

    list.innerHTML = html || '<div class="ce-empty">空目录</div>';
  }

  async _openProjectFile(path) {
    if (!LT.api || !LT.api.codeReadFile) return;
    const project = LT.store.selectedProject || '';
    const data = await LT.api.codeReadFile(path, project);
    if (!data) {
      LT.emit('notify', { msg: `无法读取: ${path}`, type: 'error' });
      return;
    }
    this._files[path] = { code: data.content, lang: data.lang || 'plaintext', isProjectFile: true };
    this._activeFile = path;
    this._setEditorContent(data.content, data.lang);
    this._updateLangSelect(data.lang);
    this._renderFileList();
    LT.store.setActiveFile(path);
  }

  _formatSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  /* ── Save (enhanced for code mode) ── */

  async _saveCurrent() {
    if (!this._activeFile || !this._editor) return;
    const code = this._editor.getValue();
    const lang = LT.ge('ce-lang')?.value || 'plaintext';
    this._files[this._activeFile].code = code;
    this._files[this._activeFile].lang = lang;

    // In code mode, save to disk via API
    if (this._codeMode && this._files[this._activeFile].isProjectFile && LT.api) {
      const project = LT.store.selectedProject || '';
      const result = await LT.api.codeWriteFile(this._activeFile, code, project);
      if (result && result.ok) {
        LT.emit('notify', { msg: `已保存到磁盘: ${this._activeFile}`, type: 'success' });
      } else {
        LT.emit('notify', { msg: `保存失败: ${this._activeFile}`, type: 'error' });
        return;
      }
    } else {
      LT.emit('notify', { msg: `已保存: ${this._activeFile}`, type: 'success' });
    }
    LT.emit('editor:saved', { path: this._activeFile, code, lang });
  }

  destroy() {
    if (this._editor) { this._editor.dispose(); this._editor = null; }
    super.destroy();
  }
}

LT.register('code-editor', CodeEditor);

// Patch lang select change
document.addEventListener('change', e => {
  if (e.target.id === 'ce-lang') {
    const inst = LT.get('code-editor');
    if (inst) inst._onLangChange();
  }
});

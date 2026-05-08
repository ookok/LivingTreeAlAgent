/* LivingTree Web — Input Component */
class Input extends Component {
  constructor(el) {
    if (typeof el === 'string') el = LT.qs(el) || LT.ge(el);
    super(el);
    this._files = [];
    this._recorder = null;
    this._recording = false;
    this._slashCommands = [
      { cmd: '/ask', desc: '搜索查资料', icon: '🔍' },
      { cmd: '/do', desc: '执行操作', icon: '⚡' },
      { cmd: '/files', desc: '文件管理', icon: '📁' },
      { cmd: '/learn', desc: '学习进化', icon: '🧠' },
      { cmd: '/check', desc: '检查诊断', icon: '🔧' },
      { cmd: '/docs', desc: '文档生成', icon: '📝' },
      { cmd: '/team', desc: '协作网络', icon: '🌐' },
      { cmd: '/help', desc: '帮助', icon: '❓' }
    ];
    this._slashIdx = -1;
    this._slashFiltered = [];
  }

  init() {
    this.render();
    this._cacheElements();
    this._setupSlashCommands();
    this._setupFileUpload();
    this._setupVoice();
    this._setupDragDrop();
    this._setupTextarea();
    this._setupSendStop();
  }

  template() {
    return `
      <div class="file-preview"></div>
      <div class="slash-dropdown" style="display:none"></div>
      <div class="input-wrapper">
        <div class="input-toolbar">
          <button class="input-tool-btn slash-btn" title="命令 /">
            <svg width="14" height="14" viewBox="0 0 14 14"><path d="M4 2l6 10M2 5l3 3-3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
          </button>
          <button class="input-tool-btn upload-btn" title="上传文件">
            <svg width="14" height="14" viewBox="0 0 14 14"><path d="M7 2v8M4 6l3-4 3 4M2 12h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>
          </button>
          <button class="input-tool-btn voice-btn" title="语音">
            <svg width="14" height="14" viewBox="0 0 14 14"><rect x="5" y="1" width="4" height="8" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M3 6v1a4 4 0 008 0V6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><line x1="7" y1="11" x2="7" y2="13" stroke="currentColor" stroke-width="1.3"/><line x1="4" y1="13" x2="10" y2="13" stroke="currentColor" stroke-width="1.3"/></svg>
          </button>
          <div class="input-toolbar-divider"></div>
        </div>
        <textarea class="input-textarea" placeholder="输入消息... (/ 命令, Enter 发送)" rows="1"></textarea>
        <input type="file" class="hidden-file-input" multiple style="display:none">
        <div class="input-actions">
          <button class="btn-stop" style="display:none" title="停止">
            <svg width="12" height="12"><rect x="1" y="1" width="10" height="10" rx="1" fill="currentColor"/></svg>
          </button>
          <button class="btn-send" title="发送">
            <svg class="icon-send" width="14" height="14"><path d="M2 2l10 5-10 5 2-5-2-5z" fill="currentColor"/></svg>
            <span class="spinner"></span>
          </button>
        </div>
      </div>
    `;
  }

  _cacheElements() {
    this._wrapper = this.el.querySelector('.input-wrapper');
    this._textarea = this.el.querySelector('.input-textarea');
    this._btnSend = this.el.querySelector('.btn-send');
    this._btnStop = this.el.querySelector('.btn-stop');
    this._filePreview = this.el.querySelector('.file-preview');
    this._slashDD = this.el.querySelector('.slash-dropdown');
    this._slashBtn = this.el.querySelector('.slash-btn');
    this._uploadBtn = this.el.querySelector('.upload-btn');
    this._voiceBtn = this.el.querySelector('.voice-btn');
    this._fileInput = this.el.querySelector('.hidden-file-input');

    this._slashDDItems = [];
    this._slashCommands.forEach((c) => {
      const d = document.createElement('div');
      d.className = 'slash-item';
      d.innerHTML = `<span class="slash-item-icon">${c.icon}</span><div class="slash-item-info"><div class="slash-item-name">${c.cmd}</div><div class="slash-item-desc">${c.desc}</div></div>`;
      d.addEventListener('click', () => this._selectSlash(c));
      this._slashDD.appendChild(d);
      this._slashDDItems.push({ el: d, cmd: c });
    });
  }

  _setupSlashCommands() {
    this._slashBtn.addEventListener('click', () => {
      this._slashFiltered = [...this._slashCommands];
      this._slashIdx = 0;
      this._renderSlashDD();
      this._textarea.value = '/';
      this._textarea.focus();
    });

    this._textarea.addEventListener('input', () => {
      const v = this._textarea.value;
      const idx = v.lastIndexOf('/');
      if (idx >= 0 && (idx === 0 || v[idx - 1] === ' ')) {
        const q = v.slice(idx + 1).toLowerCase();
        this._slashFiltered = this._slashCommands.filter(c =>
          c.cmd.includes(q) || c.desc.includes(q)
        );
        this._slashIdx = 0;
        this._renderSlashDD();
      } else {
        this._closeSlash();
      }
    });

    this._textarea.addEventListener('keydown', (e) => {
      if (this._slashDD.style.display === 'block') {
        if (e.key === 'ArrowDown') { e.preventDefault(); this._slashIdx = Math.min(this._slashIdx + 1, this._slashFiltered.length - 1); this._renderSlashDD(); return; }
        if (e.key === 'ArrowUp') { e.preventDefault(); this._slashIdx = Math.max(this._slashIdx - 1, 0); this._renderSlashDD(); return; }
        if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); if (this._slashFiltered[this._slashIdx]) this._selectSlash(this._slashFiltered[this._slashIdx]); return; }
        if (e.key === 'Escape') { e.preventDefault(); this._closeSlash(); return; }
      }
    });
  }

  _renderSlashDD() {
    this._slashDDItems.forEach(({ el, cmd }) => {
      const show = this._slashFiltered.includes(cmd);
      el.style.display = show ? 'flex' : 'none';
      el.classList.toggle('selected', cmd === this._slashFiltered[this._slashIdx]);
    });
    this._slashDD.style.display = this._slashFiltered.length ? 'block' : 'none';
  }

  _closeSlash() {
    this._slashDD.style.display = 'none';
    this._slashIdx = -1;
  }

  _selectSlash(c) {
    this._textarea.value = c.cmd + ' ';
    this._closeSlash();
    this._textarea.focus();
    this._autoResize();
  }

  _setupFileUpload() {
    this._uploadBtn.addEventListener('click', () => this._fileInput.click());
    this._fileInput.addEventListener('change', (e) => {
      this._addFiles(e.target.files);
      e.target.value = '';
    });
  }

  _addFiles(fl) {
    for (const f of fl) {
      if (!this._files.find(x => x.name === f.name && x.size === f.size)) {
        this._files.push(f);
      }
    }
    this._renderFilePreview();
  }

  _removeFile(idx) {
    this._files.splice(idx, 1);
    this._renderFilePreview();
  }

  _fileIcon(name) {
    const ext = name.split('.').pop().toLowerCase();
    const m = { py: '🐍', js: '📜', ts: '🔷', jsx: '⚛️', html: '🌐', css: '🎨', json: '📋', md: '📝', txt: '📄', pdf: '📕', png: '🖼️', jpg: '🖼️', svg: '✏️', zip: '📦', sh: '💻', yml: '⚙️', sql: '🗄️', rs: '🦀', go: '🔵', cpp: '⚡', c: '⚡' };
    return m[ext] || '📄';
  }

  _renderFilePreview() {
    this._filePreview.innerHTML = '';
    this._files.forEach((f, i) => {
      const d = document.createElement('div');
      d.className = 'file-preview-item';
      d.innerHTML = `<span class="fp-icon">${this._fileIcon(f.name)}</span><span class="fp-name">${f.name}</span><span class="fp-remove">✕</span>`;
      d.querySelector('.fp-remove').addEventListener('click', () => this._removeFile(i));
      this._filePreview.appendChild(d);
    });
    this._filePreview.classList.toggle('has-files', this._files.length > 0);
  }

  _setupVoice() {
    this._voiceBtn.addEventListener('click', () => {
      this._recording ? this._stopVoice() : this._startVoice();
    });
  }

  _startVoice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { LT.emit('notify', { msg: '浏览器不支持语音识别', type: 'error' }); return; }
    this._recorder = new SR();
    this._recorder.lang = 'zh-CN';
    this._recorder.interimResults = true;
    this._recorder.continuous = true;
    this._recorder.onresult = (e) => {
      let t = '';
      for (let i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
      this._textarea.value = t;
      this._autoResize();
    };
    this._recorder.onerror = () => this._stopVoice();
    this._recorder.onend = () => this._stopVoice();
    this._recorder.start();
    this._recording = true;
    this._voiceBtn.classList.add('recording');
    this._showVoiceIndicator();
  }

  _stopVoice() {
    if (this._recorder) { this._recorder.stop(); this._recorder = null; }
    this._recording = false;
    this._voiceBtn.classList.remove('recording');
    this._hideVoiceIndicator();
  }

  _showVoiceIndicator() {
    let el = document.getElementById('voice-indicator');
    if (!el) {
      el = document.createElement('div');
      el.id = 'voice-indicator';
      el.className = 'voice-indicator';
      el.innerHTML = '<div class="voice-wave"><span></span><span></span><span></span><span></span><span></span></div><span class="voice-text">聆听中...</span>';
      document.body.appendChild(el);
    }
    el.classList.add('active');
  }

  _hideVoiceIndicator() {
    const el = document.getElementById('voice-indicator');
    if (el) el.classList.remove('active');
  }

  _setupDragDrop() {
    this._dragCounter = 0;
    let overlay = document.getElementById('drag-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'drag-overlay';
      overlay.className = 'drag-overlay';
      overlay.innerHTML = '📂 拖放文件';
      document.body.appendChild(overlay);
    }
    const onEnter = (e) => { e.preventDefault(); this._dragCounter++; overlay.classList.add('active'); };
    const onLeave = (e) => { e.preventDefault(); this._dragCounter--; if (this._dragCounter <= 0) { this._dragCounter = 0; overlay.classList.remove('active'); } };
    const onOver = (e) => e.preventDefault();
    const onDrop = (e) => { e.preventDefault(); this._dragCounter = 0; overlay.classList.remove('active'); if (e.dataTransfer.files.length) this._addFiles(e.dataTransfer.files); };

    document.addEventListener('dragenter', onEnter);
    document.addEventListener('dragleave', onLeave);
    document.addEventListener('dragover', onOver);
    document.addEventListener('drop', onDrop);

    this._unsubs.push(() => {
      document.removeEventListener('dragenter', onEnter);
      document.removeEventListener('dragleave', onLeave);
      document.removeEventListener('dragover', onOver);
      document.removeEventListener('drop', onDrop);
    });
  }

  _setupTextarea() {
    this._textarea.addEventListener('input', () => this._autoResize());
    this._textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        if (this._slashDD.style.display === 'block') return;
        e.preventDefault();
        this._send();
      }
    });
  }

  _autoResize() {
    this._textarea.style.height = 'auto';
    this._textarea.style.height = Math.min(this._textarea.scrollHeight, 200) + 'px';
  }

  _setupSendStop() {
    this._btnSend.addEventListener('click', () => this._send());
    this._btnStop.addEventListener('click', () => this._stop());
  }

  async _send() {
    const store = LT.store;
    const api = LT.api;
    if (store.generating) return;
    let text = this._textarea.value.trim();
    if (!text && !this._files.length) return;

    if (this._files.length) {
      const names = this._files.map(f => f.name).join(', ');
      text = text || `分析文件: ${names}`;
      text = `[文件: ${names}]\n${text}`;
      this._files = [];
      this._renderFilePreview();
    }

    if (!store.activeId) {
      store.create(text.slice(0, 30));
      LT.emit('session:switch');
    }

    LT.emit('message:send', text);

    LT.emit('msg:user', { content: text });

    this._textarea.value = '';
    this._textarea.style.height = 'auto';
    this._btnSend.classList.add('loading');
    this._btnStop.style.display = 'flex';

    LT.emit('msg:typing');

    // Detect report requests and initiate workflow stepper
    if (text.includes('报告') || text.includes('生成') || text.includes('文档') || text.includes('撰写')) {
      ReportWorkflow.init(text.slice(0, 40));
      LT.emit('workflow:update', { step: 'collecting' });
    }

    LT.emit('msg:agent-stream');
    store.addMsg(sid, { role: 'assistant', content: '' });
    let full = '';
    const onC = (c) => { full += c; store.updateLast(sid, full); LT.emit('msg:chunk', { content: full }); };
    const onD = () => { store.updateLast(sid, full); LT.emit('msg:done', { content: full }); this._btnSend.classList.remove('loading'); this._btnStop.style.display = 'none'; LT.emit('session:switch'); };
    const onE = (e) => { store.updateLast(sid, full + `\n\n*[错误: ${e.message || e}]*`); LT.emit('msg:done', { content: full + `\n\n*[错误: ${e.message || e}]*` }); this._btnSend.classList.remove('loading'); this._btnStop.style.display = 'none'; LT.emit('session:switch'); };

    LT.api.send(text, onC, onD, onE);
  }

  _stop() {
    LT.api.stop();
  }

  destroy() {
    this._stopVoice();
    this._unsubs.forEach(fn => fn());
    this._unsubs = [];
    if (this.el) this.el.innerHTML = '';
  }
}

LT.register('input', Input);

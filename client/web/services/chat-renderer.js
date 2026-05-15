/* LivingTree Chat Renderer — Rich segment-based message display
 * 
 * Handles: streaming thinking, tool calls, A2UI components, interactive asks, loading states
 * 
 * Message segment types:
 *   thinking   — collapsible reasoning stream (collapsed by default)
 *   text       — main content output
 *   tool_call  — expandable tool invocation with args + result
 *   a2ui       — auto-rendered Tailwind/Mermaid/Chart/Table
 *   ask        — interactive prompt requiring user response
 *   error      — error display
 *   loading    — typewriter animation
 */

(function() {
  'use strict';
  window.LT = window.LT || {};

  const ChatRenderer = {
    /** Add a new agent message container */
    addAgentMessage(containerId) {
      const area = document.getElementById(containerId || 'chat-area');
      const el = document.createElement('div');
      el.className = 'msg-enter flex gap-3 max-w-3xl mx-auto mb-4';
      el.innerHTML = `<div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm flex-shrink-0">🌳</div>
        <div class="flex-1 min-w-0 space-y-2" id="msg-${Date.now()}"></div>`;
      area.appendChild(el);
      area.scrollTop = area.scrollHeight;
      return el.querySelector('.space-y-2');
    },

    /** Add a user message */
    addUserMessage(text, containerId) {
      const area = document.getElementById(containerId || 'chat-area');
      const el = document.createElement('div');
      el.className = 'msg-enter flex gap-3 max-w-3xl mx-auto justify-end mb-4';
      el.innerHTML = `<div class="bg-blue-600 text-white rounded-2xl rounded-tr-none shadow-sm px-4 py-2.5 max-w-xl text-sm">${LT.esc(text)}</div>`;
      area.appendChild(el);
      area.scrollTop = area.scrollHeight;
    },

    /* ═══ Segment Renderers ═══ */

    /** Thinking block — collapsible, shows reasoning stream */
    thinking(container, text, isStreaming) {
      const cls = isStreaming ? 'thinking-streaming' : '';
      const existing = container.querySelector('.thinking-block:last-child.thinking-streaming');
      if (existing && isStreaming) {
        existing.querySelector('.thinking-content').textContent = text;
        return;
      }
      const div = document.createElement('div');
      div.className = `thinking-block bg-gray-50 border border-gray-200 rounded-xl overflow-hidden ${cls}`;
      div.innerHTML = `<div class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-100"
          onclick="this.nextElementSibling.classList.toggle('hidden');this.querySelector('.expand-icon').classList.toggle('rotate-90')">
          <span class="text-xs text-gray-500 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-purple-400 ${isStreaming?'animate-pulse':''}"></span>
            💭 思考中...
          </span>
          <svg class="expand-icon w-3 h-3 text-gray-400 transition-transform ${isStreaming?'':'rotate-90'}" viewBox="0 0 12 12"><path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div class="thinking-content px-3 py-2 text-xs text-gray-500 leading-relaxed max-h-32 overflow-y-auto ${isStreaming?'':'hidden'}">${LT.esc(text)}</div>`;
      container.appendChild(div);
    },

    /** Main text block */
    text(container, text, isStreaming) {
      const existing = container.querySelector('.text-block:last-child.text-streaming');
      if (existing && isStreaming) {
        existing.innerHTML = this._md(text);
        return;
      }
      const div = document.createElement('div');
      div.className = `text-block bg-white rounded-2xl rounded-tl-none shadow-sm px-4 py-3 text-sm text-gray-700 leading-relaxed ${isStreaming?'text-streaming':''}`;
      div.innerHTML = this._md(text);
      container.appendChild(div);
    },

    /** Tool call block — category-specific visual design */
    toolCall(container, name, args, status, result, meta) {
      const category = this._toolCategory(name);
      const div = document.createElement('div');

      if (category === 'file') {
        this._renderFileCall(div, name, args, result);
      } else if (category === 'bash') {
        this._renderBashCall(div, name, args, result, status, meta);
      } else if (category === 'code') {
        this._renderCodeCall(div, name, args, result, meta);
      } else if (category === 'search') {
        this._renderSearchCall(div, name, args, result);
      } else {
        this._renderGenericCall(div, name, args, result, status, meta);
      }
      container.appendChild(div);
      return div;
    },

    _toolCategory(name) {
      const fileOps = ['read_file','write_file','file_read','file_write','vfs:read','vfs:write','cat','ls','cp','find'];
      const bashOps = ['bash','shell','run_command','execute','sh','cmd','powershell'];
      const codeOps = ['python','node','eval','exec','run','import','pip_install'];
      const searchOps = ['web_search','kb_search','search','grep','find'];
      if (fileOps.includes(name)) return 'file';
      if (bashOps.includes(name)) return 'bash';
      if (codeOps.includes(name)) return 'code';
      if (searchOps.includes(name)) return 'search';
      return 'generic';
    },

    /* ── File/Code Operations: code view with line numbers + diff detection ── */
    _renderFileCall(div, name, args, result) {
      const isWrite = name.includes('write');
      const isRead = name.includes('read');
      const pathMatch = args?.match(/([\/\w.\\-]+\.?\w*)/);
      const filePath = pathMatch ? pathMatch[1] : '';
      const fileName = filePath.split(/[\/\\]/).pop() || 'unknown';
      const lang = this._detectLang(fileName);
      const content = result || '';
      const sizeBytes = content.length;

      // Detect if content has diff markers (+/- lines)
      const isDiff = /^[+-]/.test(content.trim()) && content.includes('\n');
      const isCreate = isWrite && !isDiff && content.length > 0;
      const isModify = isWrite && isDiff;

      let modeIcon = '📖', modeLabel = '读取', accentColor = 'green';
      if (isCreate) { modeIcon = '🆕'; modeLabel = '新建'; accentColor = 'emerald'; }
      else if (isModify) { modeIcon = '✏️'; modeLabel = '修改'; accentColor = 'amber'; }

      // Build line-numbered code view
      const codeHtml = content ? this._buildCodeView(content, lang, isDiff) : '<span class="text-gray-400 text-xs italic">(empty)</span>';

      div.className = `tool-block rounded-xl overflow-hidden bg-white border border-gray-200 shadow-sm`;
      div.innerHTML = `<div class="flex items-center gap-2 px-3 py-2 bg-${accentColor}-50 border-b border-${accentColor}-100 cursor-pointer"
          onclick="this.parentElement.querySelector('.file-detail').classList.toggle('hidden')">
          <span class="text-base">${modeIcon}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-xs font-medium text-gray-700">${LT.esc(modeLabel)}</span>
              <span class="text-xs text-gray-400 font-mono truncate">${LT.esc(fileName)}</span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-gray-400">${lang}</span>
            ${isRead?`<span class="text-xs text-gray-300">${sizeBytes}B</span>`:''}
          </div>
          <svg class="w-3 h-3 text-gray-300 expand-icon" viewBox="0 0 12 12"><path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div class="file-detail ${isCreate||isModify?'':'hidden'}">
          <div class="text-xs text-gray-400 px-3 py-1.5 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
            <span class="font-mono">📁 ${LT.esc(filePath)}</span>
            <span class="text-gray-300">${content.split('\n').length} lines · ${sizeBytes}B · ${lang}</span>
          </div>
          ${codeHtml}
        </div>`;
    },

    /* ── Code Execution: code view with line numbers ── */
    _renderCodeCall(div, name, args, result, meta) {
      const langMap = {python:'Python', node:'JavaScript', eval:'Python', exec:'Shell', run:'Shell'};
      const lang = langMap[name] || 'Code';
      const content = result || args || '';
      const turn = meta?.turn || 0;
      const isDiff = /^[+-]/.test(content.trim()) && content.includes('\n');
      const codeHtml = content ? this._buildCodeView(content, lang.toLowerCase(), isDiff) : '';

      div.className = 'tool-block rounded-xl overflow-hidden bg-white border border-purple-200 shadow-sm';
      div.innerHTML = `<div class="flex items-center justify-between px-3 py-2 bg-purple-50 border-b border-purple-100 cursor-pointer"
          onclick="this.parentElement.querySelector('.code-detail').classList.toggle('hidden')">
          <div class="flex items-center gap-2">
            <span class="text-sm">${lang==='Python'?'🐍':lang==='JavaScript'?'🟢':'💻'}</span>
            <span class="text-xs font-medium text-purple-700">${lang}</span>
            ${turn?`<span class="text-xs text-purple-400">· 第${turn}次</span>`:''}
          </div>
          <div class="flex items-center gap-2">
            ${content?`<span class="text-xs text-gray-400">${content.split('\\n').length} lines</span>`:''}
            <svg class="w-3 h-3 text-purple-300" viewBox="0 0 12 12"><path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
          </div>
        </div>
        <div class="code-detail ${content?'':'hidden'}">
          ${content?`<div class="text-xs text-gray-400 px-3 py-1.5 bg-gray-50 border-b border-gray-100">${isDiff?'📊 Diff 视图':'📄 代码视图'} · ${lang} · ${content.split('\\n').length} lines</div>`:''}
          ${codeHtml}
        </div>`;
    },

    /* ── Code View Builder: line numbers + syntax-aware + diff highlighting ── */
    _buildCodeView(content, lang, isDiff) {
      const lines = content.split('\n');
      const maxLine = lines.length;
      const gutterW = String(maxLine).length;

      let html = '<div class="overflow-x-auto"><table class="w-full text-xs font-mono leading-relaxed border-collapse">';

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const lineNum = i + 1;
        const numStr = String(lineNum).padStart(gutterW, ' ');

        let lineClass = 'text-gray-700';
        let bgClass = '';
        let prefix = '';

        if (isDiff) {
          if (line.startsWith('+') && !line.startsWith('+++')) {
            lineClass = 'text-green-800';
            bgClass = 'bg-green-50';
            prefix = '+';
          } else if (line.startsWith('-') && !line.startsWith('---')) {
            lineClass = 'text-red-800';
            bgClass = 'bg-red-50';
            prefix = '-';
          } else if (line.startsWith('@@')) {
            lineClass = 'text-blue-600';
            bgClass = 'bg-blue-50';
          } else {
            lineClass = 'text-gray-500';
          }
        }

        const displayLine = prefix ? line.slice(1) : line;
        html += `<tr class="${bgClass}">`;
        html += `<td class="text-right text-gray-300 select-none pr-3 pl-2 py-0.5 ${bgClass} w-12 border-r border-gray-100">${numStr}</td>`;
        html += `<td class="${lineClass} pl-3 py-0.5 whitespace-pre-wrap break-all">${LT.esc(displayLine)||' '}</td>`;
        html += `</tr>`;
      }

      html += '</table></div>';
      return html;
    },

    _detectLang(fileName) {
      const ext = (fileName||'').split('.').pop().toLowerCase();
      const map = {py:'Python',js:'JavaScript',ts:'TypeScript',jsx:'React',tsx:'React TS',
                   go:'Go',rs:'Rust',java:'Java',cpp:'C++',c:'C',cs:'C#',sh:'Shell',
                   bash:'Shell',ps1:'PowerShell',sql:'SQL',html:'HTML',css:'CSS',
                   json:'JSON',xml:'XML',yaml:'YAML',yml:'YAML',md:'Markdown',
                   toml:'TOML',cfg:'Config',ini:'INI',dockerfile:'Dockerfile'};
      return map[ext] || ext.toUpperCase() || 'text';
    },

    /* ── Bash: terminal window simulation ── */
    _renderBashCall(div, name, args, result, status, meta) {
      const exitOk = result && !/(error|Error|fail|exception)/i.test(String(result));
      const elapsed = meta?.elapsedMs || 0;

      div.className = 'tool-block rounded-xl overflow-hidden border border-gray-700 bg-gray-900';
      div.innerHTML = `<div class="flex items-center gap-2 px-3 py-1.5 bg-gray-800 cursor-pointer"
          onclick="this.parentElement.querySelector('.bash-detail').classList.toggle('hidden')">
          <span class="flex gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-red-500"></span>
            <span class="w-2.5 h-2.5 rounded-full bg-yellow-500"></span>
            <span class="w-2.5 h-2.5 rounded-full bg-green-500"></span>
          </span>
          <span class="text-xs text-gray-400 ml-2 flex-1 font-mono truncate">$ ${LT.esc(args).slice(0,70)}</span>
          ${status==='running'?'<span class="text-xs text-blue-400 animate-pulse">running</span>':''}
          ${elapsed?`<span class="text-xs text-gray-500 ml-2">${elapsed}ms</span>`:''}
          <span class="text-xs ml-1 ${exitOk?'text-green-400':'text-red-400'}">${status==='done'?(exitOk?'exit 0':'exit 1'):''}</span>
        </div>
        <div class="bash-detail ${status==='running'?'':'hidden'}">
          <div class="px-3 py-2 text-xs font-mono text-green-400 max-h-48 overflow-y-auto whitespace-pre-wrap bg-gray-950">${LT.esc(result||(status==='running'?'...':'')).slice(0,2000)}</div>
        </div>`;
    },

    /* ── Code Execution: purple code card ── */
    _renderCodeCall(div, name, args, result, meta) {
      const langMap = {python:'🐍 Python', node:'🟢 Node.js', eval:'⚡ Eval', exec:'⚙️ Exec'};
      const lang = langMap[name] || '💻 Code';
      const turn = meta?.turn || 0;

      div.className = 'tool-block rounded-xl overflow-hidden border border-purple-200 bg-purple-50';
      div.innerHTML = `<div class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-purple-100"
          onclick="this.parentElement.querySelector('.code-detail').classList.toggle('hidden')">
          <div class="flex items-center gap-2">
            <span class="text-lg">${lang.split(' ')[0]}</span>
            <span class="text-xs font-medium text-purple-700">${lang}</span>
            ${turn?`<span class="text-xs text-purple-400">· 第${turn}次</span>`:''}
          </div>
          <svg class="w-3 h-3 text-purple-400" viewBox="0 0 12 12"><path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div class="code-detail hidden px-3 pb-2">
          <div class="bg-gray-900 rounded-lg p-2 text-xs font-mono text-purple-300 max-h-48 overflow-y-auto whitespace-pre-wrap">${LT.esc(result||'').slice(0,2000)}</div>
        </div>`;
    },

    /* ── Search: blue search card with hit count ── */
    _renderSearchCall(div, name, args, result) {
      const query = args?.slice(0,80) || '';
      const lines = result ? String(result).split('\n').filter(l=>l.trim()).length : 0;

      div.className = 'tool-block rounded-xl overflow-hidden border border-blue-200 bg-blue-50';
      div.innerHTML = `<div class="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-blue-100"
          onclick="this.parentElement.querySelector('.search-detail').classList.toggle('hidden')">
          <span class="text-lg">🔍</span>
          <div class="flex-1 min-w-0">
            <span class="text-xs font-medium text-blue-700">${LT.esc(name)}</span>
            <span class="text-xs text-blue-400 ml-2 truncate">${LT.esc(query)}</span>
          </div>
          <span class="text-xs text-blue-500">${lines} 条</span>
        </div>
        <div class="search-detail hidden px-3 pb-2">
          <div class="bg-white rounded-lg p-2 text-xs text-gray-600 max-h-48 overflow-y-auto whitespace-pre-wrap border border-blue-100">${LT.esc(result||'').slice(0,1000)}</div>
        </div>`;
    },

    /* ── Generic fallback ── */
    _renderGenericCall(div, name, args, result, status, meta) {
      const icons = {pending:'⏳',running:'🔄',done:'✅',error:'❌'};
      const colors = {pending:'text-yellow-500',running:'text-blue-500',done:'text-green-500',error:'text-red-500'};
      const turnInfo = meta?.turn ? `· 第${meta.turn}轮` : '';
      const timeInfo = meta?.elapsedMs ? `· ${meta.elapsedMs}ms` : '';

      div.className = `tool-block bg-gray-50 border border-gray-200 rounded-xl overflow-hidden ${status==='running'?'tool-running':''}`;
      div.innerHTML = `<div class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-100"
          onclick="this.querySelector('.generic-detail').classList.toggle('hidden')">
          <span class="text-xs">${icons[status]||'🔧'} <span class="${colors[status]||'text-gray-700'}">${LT.esc(name)}</span> <span class="text-gray-400">${turnInfo} ${timeInfo}</span></span>
          <svg class="w-3 h-3 text-gray-400" viewBox="0 0 12 12"><path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div class="generic-detail hidden px-3 py-2 text-xs border-t border-gray-200">
          ${args?`<div class="text-gray-400 mb-1"><span class="font-medium">参数:</span> ${LT.esc(args).slice(0,300)}</div>`:''}
          ${result?`<div class="text-gray-600 bg-white rounded-lg p-2 mt-1 max-h-32 overflow-y-auto font-mono">${LT.esc(String(result)).slice(0,800)}</div>`:''}
        </div>`;
    },

    /** Interactive ask — tabs, select, confirm, input */
    ask(container, question, options, type) {
      const div = document.createElement('div');
      div.className = 'bg-blue-50 border border-blue-200 rounded-xl p-3 text-sm';

      if (type === 'tabs') {
        // Tab-style selection
        let tabHtml = `<p class="text-blue-800 mb-2 text-xs font-medium">${LT.esc(question)}</p><div class="flex gap-1 bg-blue-100 rounded-lg p-0.5">`;
        (options||[]).forEach((opt, i) => {
          const active = i === 0 ? 'bg-white shadow-sm text-blue-700' : 'text-blue-500 hover:text-blue-700';
          tabHtml += `<button class="flex-1 px-3 py-1.5 text-xs rounded-md transition-colors ${active}"
            onclick="LT.chat.sendMsg('${LT.esc(opt.value||opt)}')">${LT.esc(opt.label||opt)}</button>`;
        });
        tabHtml += '</div>';
        div.innerHTML = tabHtml;
      } else if (type === 'select') {
        // Dropdown-style selection
        let selHtml = `<p class="text-blue-800 mb-2 text-xs font-medium">${LT.esc(question)}</p>
          <select class="w-full px-3 py-2 border border-blue-200 rounded-lg text-xs bg-white mb-2"
            onchange="LT.chat.sendMsg(this.value)">
            <option value="">-- 请选择 --</option>`;
        (options||[]).forEach(opt => {
          selHtml += `<option value="${LT.esc(opt.value||opt)}">${LT.esc(opt.label||opt)}</option>`;
        });
        selHtml += '</select>';
        div.innerHTML = selHtml;
      } else {
        // Default: button grid
        let btnHtml = `<p class="text-blue-800 mb-2 text-xs font-medium">${LT.esc(question)}</p><div class="flex flex-wrap gap-2">`;
        (options||[{value:'ok',label:'OK'}]).forEach(opt => {
          const v = typeof opt === 'string' ? opt : opt.value;
          const l = typeof opt === 'string' ? opt : (opt.label||v);
          btnHtml += `<button onclick="LT.chat.sendMsg('${LT.esc(v)}')" class="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">${LT.esc(l)}</button>`;
        });
        btnHtml += '</div>';
        div.innerHTML = btnHtml;
      }
      container.appendChild(div);
    },

    /** A2UI component block */
    a2ui(container, type, data) {
      const div = document.createElement('div');
      if (type === 'tailwind') {
        div.className = 'living-a2ui';
        div.dataset.a2uiType = 'tailwind';
        div.dataset.a2uiComponent = data.component || 'Card';
        div.dataset.a2uiProps = JSON.stringify(data.props || {});
      } else if (type === 'chart') {
        div.className = 'living-a2ui';
        div.dataset.a2uiType = 'chart';
        div.dataset.a2uiChart = JSON.stringify(data);
        div.style.cssText = 'width:100%;min-height:300px;';
      } else if (type === 'diagram') {
        div.className = 'living-a2ui';
        div.dataset.a2uiType = 'diagram';
        div.textContent = data.code || '';
      }
      container.appendChild(div);
      if (window.LivingA2UI) setTimeout(() => LivingA2UI.scan(), 100);
      return div;
    },

    /** Interactive ask — requires user response */
    ask(container, question, options) {
      const div = document.createElement('div');
      div.className = 'bg-blue-50 border border-blue-200 rounded-xl p-3 text-sm';
      div.innerHTML = `<p class="text-blue-800 mb-2">🤔 ${LT.esc(question)}</p>
        <div class="flex flex-wrap gap-2">${(options||['是','否','跳过']).map(o =>
          `<button onclick="LT.chat.sendMsg('${LT.esc(o)}')" class="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">${LT.esc(o)}</button>`
        ).join('')}</div>`;
      container.appendChild(div);
    },

    /** Loading animation */
    loading(container) {
      const div = document.createElement('div');
      div.className = 'loading-block';
      div.innerHTML = `<div class="flex items-center gap-2 text-gray-400 text-xs px-1">
        <span class="typing-dot inline-block w-1.5 h-1.5 bg-gray-400 rounded-full" style="animation:blink 1.4s infinite both"></span>
        <span class="typing-dot inline-block w-1.5 h-1.5 bg-gray-400 rounded-full" style="animation:blink 1.4s infinite both;animation-delay:.2s"></span>
        <span class="typing-dot inline-block w-1.5 h-1.5 bg-gray-400 rounded-full" style="animation:blink 1.4s infinite both;animation-delay:.4s"></span>
        <span class="ml-1">思考中...</span>
      </div>`;
      container.appendChild(div);
      return div;
    },

    /** Error block */
    error(container, msg) {
      const div = document.createElement('div');
      div.className = 'bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-700';
      div.textContent = '❌ ' + msg;
      container.appendChild(div);
    },

    /* ═══ Task List — multi-step plan with status refresh ═══ */

    /** Check if a task list already exists in this message */
    _existingTaskList(container) {
      return container.querySelector('.task-list-block');
    },

    /** Render or update a multi-step task plan — renders to fixed bar above input */
    taskList(container, tasks, isStreaming) {
      const bar = document.getElementById('task-bar');
      if (!bar) return;

      bar.classList.remove('hidden');

      const total = tasks.length;
      const done = tasks.filter(t => t.status === 'done').length;
      const progress = total > 0 ? Math.round(done/total*100) : 0;
      const allDone = done === total && total > 0;
      const running = tasks.find(t => t.status === 'running');

      // Compact progress bar
      let html = `<div class="max-w-3xl mx-auto">`;

      // Header row: title + progress + collapse toggle
      html += `<div class="flex items-center justify-between mb-1.5">`;
      html += `<div class="flex items-center gap-2">`;
      html += `<span class="text-xs font-medium text-gray-700">📋 ${done}/${total}</span>`;
      if (running) {
        html += `<span class="text-xs text-blue-500 animate-pulse">${LT.esc(running.label||running.name||'')}</span>`;
      }
      html += `</div>`;
      html += `<div class="flex items-center gap-2">`;
      html += `<div class="w-32 h-1 bg-gray-100 rounded-full overflow-hidden"><div class="h-full bg-blue-500 rounded-full transition-all duration-700" style="width:${progress}%"></div></div>`;
      html += `<button onclick="var b=document.getElementById('task-bar-detail');b.classList.toggle('hidden');this.classList.toggle('rotate-180')" class="text-gray-400 hover:text-gray-600 transition-transform text-xs">▼</button>`;
      html += `</div></div>`;

      // Expandable detail: full task list
      html += `<div id="task-bar-detail" class="hidden border border-gray-100 rounded-lg bg-gray-50 overflow-hidden">`;
      for (let i = 0; i < tasks.length; i++) {
        const t = tasks[i];
        const statusIcons = {pending:'⏳', running:'🔄', done:'✅', failed:'❌', skipped:'⏭️'};
        const statusColors = {pending:'text-yellow-500', running:'text-blue-500 animate-pulse', done:'text-green-500', failed:'text-red-500', skipped:'text-gray-400'};
        const icon = statusIcons[t.status] || '⏳';
        const color = statusColors[t.status] || 'text-gray-400';
        const strikethrough = t.status === 'done' ? 'line-through text-gray-400' : 'text-gray-700';
        const bg = t.status === 'running' ? 'bg-blue-50' : '';

        html += `<div class="flex items-center gap-2 px-2 py-1 text-xs border-b border-gray-100 ${bg}">`;
        html += `<span class="w-4 text-center ${color}">${icon}</span>`;
        html += `<span class="flex-1 ${strikethrough}">${i+1}. ${LT.esc(t.label||t.name||'')}</span>`;
        if (t.result) {
          html += `<span class="text-gray-400 ml-2 truncate max-w-[100px]">${LT.esc(String(t.result).slice(0,30))}</span>`;
        }
        html += `</div>`;
      }
      html += `</div></div>`;

      bar.innerHTML = html;

      // Auto-collapse when done
      if (allDone) {
        bar.innerHTML = `<div class="max-w-3xl mx-auto flex items-center gap-2">
          <span class="text-xs text-green-600 font-medium">✅ ${done}/${total} 完成</span>
          <div class="w-32 h-1 bg-green-100 rounded-full overflow-hidden"><div class="h-full bg-green-500 rounded-full" style="width:100%"></div></div>
        </div>`;
        setTimeout(() => { bar.classList.add('hidden'); bar.innerHTML = ''; }, 3000);
      }
    },

    /** Proactive interjection — LLM interrupts before routing */
    interject(container, text, trigger) {
      const triggerLabels = {
        ambiguity: '🤔 需要澄清', error_detected: '⚠️ 发现错误', direction: '💡 换个角度',
        scope_creep: '🎯 聚焦问题', repetition: '🔄 换个说法', missing_context: '❓ 缺少信息',
        contradiction: '⚡ 前后矛盾', clarification: '📖 术语解释',
      };
      const label = triggerLabels[trigger] || '🤚 插话';

      const div = document.createElement('div');
      div.className = 'bg-yellow-50 border border-yellow-200 rounded-xl p-3 text-sm animate-pulse';
      div.innerHTML = `<div class="flex items-center gap-2 mb-1">
          <span class="text-xs font-medium text-yellow-700">${label}</span>
          <span class="text-xs text-yellow-400">· 主动插话</span>
        </div>
        <p class="text-yellow-800 text-sm leading-relaxed">${LT.esc(text)}</p>`;
      container.appendChild(div);
      // Stop pulse after 2s
      setTimeout(() => div.classList.remove('animate-pulse'), 2000);
    },
    clear(container) {
      while (container.firstChild) container.removeChild(container.firstChild);
    },

    /* ═══ Markdown ═══ */
    _md(text) {
      if (!text) return '';
      let out = LT.esc(text);
      // Bold
      out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      // Italic
      out = out.replace(/\*(.+?)\*/g, '<em>$1</em>');
      // Inline code
      out = out.replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-red-600 px-1 py-0.5 rounded text-xs">$1</code>');
      // Code blocks
      out = out.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) => {
        return `<pre class="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs overflow-x-auto my-2"><code>${LT.esc(code)}</code></pre>`;
      });
      // Line breaks
      out = out.replace(/\n/g, '<br>');
      return out;
    },

    /** Parse streaming content for segments */
    parseSegments(text) {
      const segments = [];
      const parts = text.split(/(<thinking>|<\/thinking>|<tool_call|<result>|<\/result>|<ask[^>]*>|<\/ask>|<plan>|<\/plan>|{"type":)/g);
      let currentType = 'text';
      let buffer = '';
      let askMeta = '';

      for (const part of parts) {
        if (part === '<thinking>') {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'thinking';
        } else if (part === '</thinking>') {
          if (buffer.trim()) { segments.push({type:'thinking', content:buffer.trim()}); buffer=''; }
          currentType = 'text';
        } else if (part === '<plan>') {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'plan';
          buffer = '';
        } else if (part === '</plan>') {
          if (buffer.trim()) { segments.push({type:'plan', content:buffer.trim()}); }
          buffer = '';
          currentType = 'text';
        } else if (part.startsWith('<tool_call')) {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'tool_call';
          buffer = part;
        } else if (part === '<result>') {
          currentType = 'tool_result';
          buffer = '';
        } else if (part === '</result>') {
          if (buffer.trim()) { segments.push({type:'tool_result', content:buffer.trim()}); buffer=''; }
          currentType = 'text';
        } else if (part.startsWith('<ask')) {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'ask';
          askMeta = part;  // e.g. <ask type="tabs" label="...">
          buffer = '';
        } else if (part === '</ask>') {
          if (buffer.trim()) {
            segments.push({type:'ask', content:buffer.trim(), meta:askMeta});
          }
          buffer = '';
          currentType = 'text';
        } else if (part === '{"type":') {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'a2ui';
          buffer = part;
        } else {
          buffer += (part || '');
        }
      }
      if (buffer.trim()) segments.push({type:currentType, content:buffer.trim()});
      return segments;
    },

    /** Render all segments into container */
    renderSegments(container, segments) {
      this.clear(container);
      for (const seg of segments) {
        if (!seg.content) continue;
        if (seg.type === 'thinking') {
          this.thinking(container, seg.content, false);
        } else if (seg.type === 'text') {
          this.text(container, seg.content, false);
        } else if (seg.type === 'tool_call') {
          const m = seg.content.match(/<tool_call\s+name="(\w+)"\s*>(.*?)<\/tool_call>/);
          if (m) this.toolCall(container, m[1], m[2], 'done', null, {});
        } else if (seg.type === 'tool_result') {
          this.toolCall(container, '', '', 'done', seg.content, {});
        } else if (seg.type === 'ask') {
          this._renderAskSegment(container, seg.content, seg.meta);
        } else if (seg.type === 'plan') {
          this._renderPlanSegment(container, seg.content);
        } else if (seg.type === 'a2ui') {
          try {
            const data = JSON.parse(seg.content);
            if (data.type) this.a2ui(container, data.type, data[data.type] || data);
          } catch(e) {}
        }
      }
    },

    _renderPlanSegment(container, content) {
      // Parse <step id="..." label="..."> or numbered lines
      const tasks = [];
      const stepRe = /<step\s+id="([^"]+)"\s+label="([^"]+)"\s*\/?>/g;
      let m;
      while ((m = stepRe.exec(content)) !== null) {
        tasks.push({id: m[1], label: m[2], name: m[2], status: 'pending'});
      }
      // Fallback: parse numbered lines like "1. do X" or "- [ ] do X"
      if (!tasks.length) {
        const lines = content.split('\n').filter(l => l.trim());
        for (const line of lines) {
          const match = line.match(/^[\d]+[.)]\s*(.+)/) || line.match(/^[-*]\s*\[.\]\s*(.+)/) || line.match(/^[-*]\s*(.+)/);
          if (match) {
            tasks.push({id: 't'+tasks.length, label: match[1], name: match[1], status: 'pending'});
          }
        }
      }
      if (tasks.length) {
        this.taskList(container, tasks, false);
      }
    },

    _renderAskSegment(container, content, meta) {
      // Parse ask attributes
      const typeMatch = meta?.match(/type="(\w+)"/);
      const labelMatch = meta?.match(/label="([^"]+)"/);
      const type = typeMatch?.[1] || 'confirm';
      const label = labelMatch?.[1] || '请选择';

      // Parse options/tabs
      const options = [];
      const optRe = /<(?:option|tab)\s+value="([^"]+)"\s+label="([^"]+)"(?:\s+selected)?\s*\/?>/g;
      let m;
      while ((m = optRe.exec(content)) !== null) {
        options.push({value: m[1], label: m[2]});
      }
      // Fallback: parse comma-separated
      if (!options.length && content.trim()) {
        content.trim().split(',').forEach(v => options.push({value: v.trim(), label: v.trim()}));
      }

      this.ask(container, label, options, type);
    },

    /** Render all segments into container */
    renderSegments(container, segments) {
      this.clear(container);
      for (const seg of segments) {
        if (!seg.content) continue;
        if (seg.type === 'thinking') {
          this.thinking(container, seg.content, false);
        } else if (seg.type === 'text') {
          this.text(container, seg.content, false);
        } else if (seg.type === 'tool_call') {
          const m = seg.content.match(/<tool_call\s+name="(\w+)"\s*>(.*?)<\/tool_call>/);
          if (m) this.toolCall(container, m[1], m[2], 'done');
        } else if (seg.type === 'tool_result') {
          this.toolCall(container, '', '', 'done', seg.content);
        } else if (seg.type === 'a2ui') {
          try {
            const data = JSON.parse(seg.content);
            if (data.type) this.a2ui(container, data.type, data[data.type] || data);
          } catch(e) {}
        }
      }
    }
  };

  LT.chat = LT.chat || {};
  LT.chat.renderer = ChatRenderer;

  /** Send a message with full rich rendering */
  LT.chat.sendMsg = async function(text) {
    if (!text) { const inp = document.getElementById('msg-input'); text = inp.value.trim(); if (!text) return; inp.value = ''; inp.style.height = 'auto'; }
    
    LT.chat.renderer.addUserMessage(text);
    const container = LT.chat.renderer.addAgentMessage();
    const loadingEl = LT.chat.renderer.loading(container);

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({message:text, stream:true})
      });

      if (!resp.ok) throw new Error('HTTP '+resp.status);

      // Fallback: non-streaming response
      if (!resp.body || !resp.body.getReader) {
        const data = await resp.json();
        const content = data.reply || data.text || data.content || '';
        loadingEl?.remove();
        const segments = LT.chat.renderer.parseSegments(content);
        LT.chat.renderer.renderSegments(container, segments);
        if (window.LivingA2UI) setTimeout(() => LivingA2UI.scan(), 100);
        return;
      }

      let fullText = '';
      let thinkingText = '';
      let inThinking = false;
      let inToolCall = false;
      let toolBuffer = '';
      let toolName = '';
      let lastRender = Date.now();

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      loadingEl?.remove();

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, {stream: true});

        // Split by SSE event boundaries
        const events = chunk.split('\n\n').filter(e => e.trim());
        
        for (const eventBlock of events) {
          const lines = eventBlock.split('\n');
          let eventType = 'message';
          let eventData = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6);
            }
          }

          if (!eventData || eventData === '[DONE]') continue;

          try {
            const parsed = JSON.parse(eventData);

            // ── Tool lifecycle events (real-time progress) ──
            if (eventType === 'tool_start') {
              LT.chat.renderer.toolCall(container, parsed.name, parsed.args, 'running', null,
                {turn: (container.querySelectorAll('.tool-block').length + 1)});
              continue;
            }
            if (eventType === 'tool_done') {
              // Update the last running tool to done
              const running = container.querySelector('.tool-running');
              if (running) {
                running.classList.remove('tool-running', 'animate-pulse');
                running.classList.add('tool-done');
                const statusEl = running.querySelector('.tool-status span, [class*="text-blue"]');
                if (statusEl) statusEl.textContent = parsed.name;
                running.querySelector('.tool-status').innerHTML =
                  '✅ <span class="text-green-500">' + LT.esc(parsed.name) + '</span>';
                if (parsed.elapsed_ms) {
                  running.querySelector('.text-gray-400').textContent = parsed.elapsed_ms + 'ms';
                }
              }
              continue;
            }

            // ── Standard stream content ──
            const token = parsed.choices?.[0]?.delta?.content || parsed.content || parsed.text || '';
            const reasoning = parsed.choices?.[0]?.delta?.reasoning_content || parsed.reasoning || '';
            const toolCalls = parsed.choices?.[0]?.delta?.tool_calls || parsed.tool_calls;

            // Handle reasoning/thinking stream
            if (reasoning) {
              if (!inThinking) {
                inThinking = true;
                LT.chat.renderer.thinking(container, reasoning, true);
              } else {
                LT.chat.renderer.thinking(container, (thinkingText + reasoning), true);
              }
              thinkingText += reasoning;
              continue;
            }
            if (inThinking && token) {
              inThinking = false;
              // Finalize thinking block
              LT.chat.renderer.thinking(container, thinkingText, false);
            }

            // ── Dead code: remove old tool_calls handling (now handled by SSE events) ──

            // ── Background model events ──
            if (eventType === 'background_start') {
              loadingEl?.remove();
              LT.chat.renderer.text(container, '🧠 后台思考中...', true);
              continue;
            }
            if (eventType === 'interject') {
              loadingEl?.remove();
              LT.chat.renderer.interject(container, parsed.content || parsed.text, parsed.trigger);
              return;
            }
            if (eventType === 'done') {
              // Final render of accumulated text
              const segments = LT.chat.renderer.parseSegments(fullText || parsed.full_text || '');
              LT.chat.renderer.renderSegments(container, segments);
              if (window.LivingA2UI) setTimeout(() => LivingA2UI.scan(), 100);
              continue;
            }

            // ── Interject detection ──
            if (parsed.mode === 'interject') {
              loadingEl?.remove();
              LT.chat.renderer.interject(container, parsed.content, parsed.trigger || 'clarification');
              return;
            }

            // Handle text output
            if (token) {
              fullText += token;
              // Throttle DOM updates to 60fps
              if (Date.now() - lastRender > 50) {
                const segments = LT.chat.renderer.parseSegments(fullText);
                LT.chat.renderer.renderSegments(container, segments);
                lastRender = Date.now();
              }
            }
          } catch(e) {}
        }
      }

      // Final render
      const segments = LT.chat.renderer.parseSegments(fullText);
      LT.chat.renderer.renderSegments(container, segments);
      
      // Trigger A2UI scan for any rendered components
      if (window.LivingA2UI) setTimeout(() => LivingA2UI.scan(), 100);

    } catch(e) {
      loadingEl?.remove();
      LT.chat.renderer.error(container, e.message || '请求失败');
    }

    document.getElementById('chat-area').scrollTop = document.getElementById('chat-area').scrollHeight;
  };

})();

const ENTITY_MAP = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
};

const LANG_CLASS_MAP = {
  js: 'javascript',
  ts: 'typescript',
  jsx: 'jsx',
  tsx: 'tsx',
  py: 'python',
  rb: 'ruby',
  go: 'go',
  rs: 'rust',
  java: 'java',
  cpp: 'cpp',
  c: 'c',
  cs: 'csharp',
  sh: 'bash',
  bash: 'bash',
  zsh: 'bash',
  ps1: 'powershell',
  powershell: 'powershell',
  sql: 'sql',
  html: 'html',
  css: 'css',
  json: 'json',
  xml: 'xml',
  yaml: 'yaml',
  yml: 'yaml',
  md: 'markdown',
  dockerfile: 'dockerfile',
  diff: 'diff',
  plaintext: 'plaintext',
  text: 'plaintext'
};

function _cls(lang) {
  if (!lang) return 'lang-plaintext';
  const norm = lang.toLowerCase().trim();
  return 'lang-' + (LANG_CLASS_MAP[norm] || norm);
}

const renderer = {

  esc(str) {
    if (typeof str !== 'string') return '';
    return str.replace(/[&<>"']/g, c => ENTITY_MAP[c] || c);
  },

  codeBlock(code, lang) {
    const escaped = this.esc(code);
    const cls = _cls(lang);
    const label = lang ? `<span class="code-lang">${this.esc(lang)}</span>` : '';

    const escCode = this.esc(code);
    return [
      '<div class="code-block">',
      '  <div class="code-header">',
      `    ${label}`,
      '    <div class="code-header-actions">',
      `      <button class="code-open-editor" onclick="LT.emit('editor:open-code',{code:\`${escCode}\`,lang:'${lang||'plaintext'}'});LT.emit('code-editor:toggle')" title="在编辑器中打开">`,
      '        <svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 4l3 3-3 3M8 11h3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" fill="none"/></svg>',
      '        编辑',
      '      </button>',
      '      <button class="copy-btn" onclick="LT.renderer.copyBtn(this)" title="Copy code">',
      '        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">',
      '          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>',
      '          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
      '        </svg>',
      '        <span>Copy</span>',
      '      </button>',
      '    </div>',
      '  </div>',
      `  <pre><code class="${cls}">${escaped}</code></pre>`,
      '</div>'
    ].join('\n');
  },

  md(text) {
    if (!text) return '';

    // Detect card blocks first
    let cardResult = '';
    if (window.Cards) {
      const cards = Cards.parseFromContent(text);
      if (cards.length) {
        // Store cards on the renderer for later attachment
        this._pendingCards = cards;
      }
    }

    const lines = text.split('\n');
    const output = [];
    let inCodeBlock = false;
    let codeBuf = [];
    let codeLang = '';
    let inList = false;
    let listType = '';

    function _flushList() {
      if (inList) {
        output.push(listType === 'ol' ? '</ol>' : '</ul>');
        inList = false;
        listType = '';
      }
    }

    function _inline(s) {
      let t = s;
      t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      t = t.replace(/__(.+?)__/g, '<strong>$1</strong>');
      t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
      t = t.replace(/_(.+?)_/g, '<em>$1</em>');
      t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
      t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" title="$1">');
      t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
      return t;
    }

    for (let i = 0; i < lines.length; i++) {
      const raw = lines[i];
      const trimmed = raw.trim();

      if (trimmed.startsWith('```')) {
        if (inCodeBlock) {
          output.push(this.codeBlock(codeBuf.join('\n'), codeLang));
          codeBuf = [];
          codeLang = '';
          inCodeBlock = false;
        } else {
          _flushList();
          inCodeBlock = true;
          codeLang = trimmed.slice(3).trim();
        }
        continue;
      }

      if (inCodeBlock) {
        codeBuf.push(raw);
        continue;
      }

      if (!trimmed) {
        _flushList();
        output.push('<br>');
        continue;
      }

      if (/^#{1,6}\s/.test(trimmed)) {
        _flushList();
        const m = trimmed.match(/^(#{1,6})\s+(.*)/);
        const level = m ? m[1].length : 1;
        const heading = m ? _inline(this.esc(m[2])) : '';
        output.push(`<h${level}>${heading}</h${level}>`);
        continue;
      }

      if (/^>\s/.test(trimmed)) {
        _flushList();
        const q = trimmed.replace(/^>\s?/, '');
        output.push(`<blockquote><p>${_inline(this.esc(q))}</p></blockquote>`);
        continue;
      }

      if (/^---\s*$/.test(trimmed)) {
        _flushList();
        output.push('<hr>');
        continue;
      }

      const ulMatch = trimmed.match(/^[-*+]\s+(.*)/);
      if (ulMatch) {
        if (!inList || listType !== 'ul') {
          _flushList();
          output.push('<ul>');
          inList = true;
          listType = 'ul';
        }
        output.push(`<li>${_inline(this.esc(ulMatch[1]))}</li>`);
        continue;
      }

      const olMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
      if (olMatch) {
        if (!inList || listType !== 'ol') {
          _flushList();
          output.push('<ol>');
          inList = true;
          listType = 'ol';
        }
        output.push(`<li>${_inline(this.esc(olMatch[2]))}</li>`);
        continue;
      }

      _flushList();

      let processed = trimmed;
      const tableSep = /^\|[-:| ]+\|$/;
      const tableRow = /^\|.+\|$/;

      if (i + 2 < lines.length && tableRow.test(trimmed) && tableSep.test(lines[i + 1].trim())) {
        const headerCells = trimmed.split('|').filter(c => c.trim());
        output.push('<table><thead><tr>');
        for (const cell of headerCells) {
          output.push(`<th>${_inline(this.esc(cell.trim()))}</th>`);
        }
        output.push('</tr></thead><tbody>');
        i += 1;
        for (i = i + 1; i < lines.length; i++) {
          const row = lines[i].trim();
          if (!tableRow.test(row)) {
            i--;
            break;
          }
          const cells = row.split('|').filter(c => c.trim());
          output.push('<tr>');
          for (const cell of cells) {
            output.push(`<td>${_inline(this.esc(cell.trim()))}</td>`);
          }
          output.push('</tr>');
        }
        output.push('</tbody></table>');
        continue;
      }

      output.push(`<p>${_inline(this.esc(processed))}</p>`);
    }

    _flushList();

    if (inCodeBlock && codeBuf.length) {
      output.push(this.codeBlock(codeBuf.join('\n'), codeLang));
    }

    return output.join('\n');
  },

  copyBtn(btn) {
    const block = btn.closest('.code-block');
    if (!block) return;

    const code = block.querySelector('code');
    if (!code) return;

    const text = code.textContent || '';

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        const span = btn.querySelector('span');
        if (span) {
          span.textContent = 'Copied!';
          setTimeout(() => { span.textContent = 'Copy'; }, 2000);
        }
      }).catch(() => {
        _fallbackCopy(text, btn);
      });
    } else {
      _fallbackCopy(text, btn);
    }
  },

  userMsg(content) {
    const escRaw = this.esc(content).replace(/`/g, '\\`');
    return `<div class="message message-user" data-raw="\`${escRaw}\`"><div class="message-bubble user-bubble">${this.md(content)}</div></div>`;
  },

  agentMsg(content, stream) {
    const streamAttr = stream ? ' data-stream="true"' : '';
    const escRaw = this.esc(content).replace(/`/g, '\\`');
    // Strip card blocks from rendered content (rendered separately)
    const cleanContent = content.replace(/\[card:\w+\][\s\S]*?\[\/card\]/g, '');
    return `<div class="message message-agent" data-raw="\`${escRaw}\`"><div class="message-bubble agent-bubble"${streamAttr}>${this.md(cleanContent)}</div></div>`;
  },

  /* ── Message action buttons ── */
  msgActions(role) {
    if (role !== 'agent' && role !== 'assistant') return '';
    return `
<div class="msg-actions">
  <button class="msg-action-btn" data-action="copy-text" title="复制文本">
    <svg width="13" height="13" viewBox="0 0 13 13"><rect x="4" y="4" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M9 4V2.5A1 1 0 008 1H2.5A1 1 0 001.5 2v5.5A1 1 0 002.5 8.5H4" fill="none" stroke="currentColor" stroke-width="1.1"/></svg>
  </button>
  <button class="msg-action-btn" data-action="copy-md" title="复制 Markdown">
    <svg width="13" height="13" viewBox="0 0 13 13"><path d="M2 4h9v6H2z" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M4 6.5h5M4 8.5h3" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
  </button>
  <button class="msg-action-btn" data-action="open-in-oo" title="在 OnlyOffice 中编辑">
    <svg width="13" height="13" viewBox="0 0 13 13"><rect x="1.5" y="2" width="10" height="9" rx="1" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M4 5.5h5M4 7.5h3" stroke="currentColor" stroke-width="1" stroke-linecap="round"/><path d="M8.5 2V1" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
  </button>
  <button class="msg-action-btn" data-action="share" title="分享">
    <svg width="13" height="13" viewBox="0 0 13 13"><circle cx="9.5" cy="3.5" r="1.8" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="9.5" cy="9.5" r="1.8" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="3.5" cy="6.5" r="1.8" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M7.8 4.3L5.2 5.7M7.8 8.7L5.2 7.3" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
  </button>
</div>`;
  },

  /* ── Copy methods ── */
  copyMsgText(msgEl) {
    const bubble = msgEl.querySelector('.agent-bubble,.user-bubble');
    const text = bubble ? bubble.textContent : '';
    this._clipCopy(text, '已复制文本');
  },

  copyMsgMarkdown(msgEl) {
    const raw = this._getRaw(msgEl);
    this._clipCopy(raw, '已复制 Markdown');
  },

  _getRaw(msgEl) {
    const attr = msgEl.getAttribute('data-raw');
    if (!attr) return '';
    // decode backtick-escaped content
    let raw = attr.replace(/^`|`$/g, '');
    // unescape HTML entities back
    const unesc = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'" };
    raw = raw.replace(/&amp;|&lt;|&gt;|&quot;|&#39;/g, m => unesc[m] || m);
    raw = raw.replace(/\\`/g, '`');
    return raw;
  },

  _clipCopy(text, msg) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        if (typeof LT !== 'undefined') LT.emit('notify', { msg, type: 'success' });
      }).catch(() => this._fallbackCopy(text));
    } else {
      this._fallbackCopy(text);
    }
  },

  _fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); if (typeof LT !== 'undefined') LT.emit('notify', { msg: '已复制', type: 'success' }); }
    catch (e) { if (typeof LT !== 'undefined') LT.emit('notify', { msg: '复制失败', type: 'error' }); }
    document.body.removeChild(ta);
  },

  typing() {
    return [
      '<div class="message message-agent">',
      '  <div class="message-bubble agent-bubble typing-indicator">',
      '    <span class="dot"></span>',
      '    <span class="dot"></span>',
      '    <span class="dot"></span>',
      '  </div>',
      '</div>'
    ].join('\n');
  },

  append(el, html) {
    if (typeof el === 'string') {
      el = document.querySelector(el);
    }
    if (!el) return;

    const tpl = document.createElement('template');
    tpl.innerHTML = html.trim();
    el.appendChild(tpl.content.firstChild);
  },

  updateStream(el, content) {
    if (typeof el === 'string') {
      el = document.querySelector(el);
    }
    if (!el) return;

    const bubble = el.querySelector('.agent-bubble[data-stream]');
    const target = bubble || el.querySelector('.agent-bubble') || el;

    if (target) {
      target.innerHTML = this.md(content);
      target.setAttribute('data-stream', 'true');
    }
  },

  finalize(el) {
    if (typeof el === 'string') {
      el = document.querySelector(el);
    }
    if (!el) return;

    const bubble = el.querySelector('.agent-bubble[data-stream]');
    if (bubble) {
      bubble.removeAttribute('data-stream');
    }
  }
};

function _fallbackCopy(text, btn) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    const span = btn.querySelector('span');
    if (span) {
      span.textContent = 'Copied!';
      setTimeout(() => { span.textContent = 'Copy'; }, 2000);
    }
  } catch (e) {
    console.warn('[renderer] Copy failed:', e);
  }
  document.body.removeChild(ta);
}

window.LT = window.LT || {};
window.LT.renderer = renderer;

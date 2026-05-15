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
    const escCodeSafe = escCode.replace(/`/g,'\\`').replace(/\$\{/g,'\\${');
    return [
      '<div class="code-block">',
      '  <div class="code-header">',
      `    ${label}`,
      '    <div class="code-header-actions">',
      `      <button class="code-open-editor" data-code="${encodeURIComponent(escCode)}" data-lang="${lang||'plaintext'}" onclick="LT.emit('editor:open-code',{code:decodeURIComponent(this.dataset.code),lang:this.dataset.lang});LT.emit('code-editor:toggle')" title="在编辑器中打开">`,
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
    try {
      let html = marked.parse(text, { breaks: true, gfm: true });
      html = html.replace(/<pre><code(?:\s+class="[^"]*")?>/g, (m) => {
        const langMatch = m.match(/class="(?:lang-)?(\w+)"/);
        const lang = langMatch ? langMatch[1] : '';
        return `__CODEBLOCK_START__${lang}__`;
      });
      html = html.replace(/<\/code><\/pre>/g, '__CODEBLOCK_END__');
      let begin = 0, result = [];
      while (begin < html.length) {
        const startIdx = html.indexOf('__CODEBLOCK_START__', begin);
        if (startIdx === -1) { result.push(html.slice(begin)); break; }
        result.push(html.slice(begin, startIdx));
        const langEnd = html.indexOf('__', startIdx + 19);
        const lang = html.slice(startIdx + 19, langEnd);
        const endIdx = html.indexOf('__CODEBLOCK_END__', langEnd);
        const code = html.slice(langEnd + 2, endIdx).replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
        result.push(this.codeBlock(code, lang || 'plaintext'));
        begin = endIdx + 18;
      }
      return result.join('');
    } catch (e) {
      console.warn('[renderer] marked failed, using plain text:', e);
      return text.replace(/</g, '&lt;').replace(/\n/g, '<br>');
    }
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
    return `<div class="message message-user"><div class="message-bubble user-bubble">${this.md(content)}</div></div>`;
  },

  agentMsg(content, stream) {
    const streamAttr = stream ? ' data-stream="true"' : '';
    return `<div class="message message-agent"><div class="message-bubble agent-bubble"${streamAttr}>${this.md(content)}</div></div>`;
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

// export default renderer;

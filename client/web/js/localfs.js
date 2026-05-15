/**
 * LocalFS — 小树的本地文件系统挂载
 * 
 * Uses File System Access API (Chromium 86+) to mount local folders
 * directly in the browser. No upload needed. Files stay on user's machine.
 * 
 * Capabilities:
 *   - showDirectoryPicker() — 用户选择文件夹
 *   - 递归目录树遍历
 *   - 文件读/写 (需用户手势)
 *   - 拖拽文件夹挂载
 *   - 与 HTMX chat 集成
 */
(function() {
  'use strict';

  // ═══ State ═══
  const state = {
    mounts: new Map(),       // name → { handle, files }
    activeFile: null,        // { name, handle, content }
  };

  // ═══ Directory Picker ═══
  window.xiaoshu = window.xiaoshu || {};

  xiaoshu.mountFolder = async function() {
    try {
      const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
      const name = handle.name;
      const tree = await buildFileTree(handle, name, 0);
      state.mounts.set(name, { handle, tree, time: Date.now() });
      renderMounts();
      xiaoshu.emit('mount', { name, fileCount: countFiles(tree) });
    } catch (e) {
      if (e.name !== 'AbortError') console.error('Folder mount failed:', e);
    }
  };

  // ═══ Drag & Drop ═══
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', async (e) => {
    e.preventDefault();
    const items = [...e.dataTransfer.items];
    for (const item of items) {
      if (item.kind === 'file') {
        const handle = await item.getAsFileSystemHandle();
        if (handle && handle.kind === 'directory') {
          const tree = await buildFileTree(handle, handle.name, 0);
          state.mounts.set(handle.name, { handle, tree, time: Date.now() });
          renderMounts();
          xiaoshu.emit('mount', { name: handle.name, fileCount: countFiles(tree) });
        }
      }
    }
  });

  // ═══ File Tree Builder ═══
  async function buildFileTree(handle, name, depth) {
    const node = { name, kind: handle.kind, depth, children: [], path: name };
    if (handle.kind === 'directory' && depth < 5) {
      for await (const [childName, childHandle] of handle.entries()) {
        node.children.push(await buildFileTree(childHandle, childName, depth + 1));
      }
      node.children.sort((a, b) => {
        if (a.kind !== b.kind) return a.kind === 'directory' ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
    }
    return node;
  }

  function countFiles(tree) {
    let n = tree.kind === 'file' ? 1 : 0;
    for (const c of (tree.children || [])) n += countFiles(c);
    return n;
  }

  // ═══ File Operations ═══
  async function resolvePath(parts) {
    // parts: ['folderName', 'subdir', 'file.txt']
    let handle = state.mounts.get(parts[0]);
    if (!handle) return null;
    handle = handle.handle;
    for (let i = 1; i < parts.length; i++) {
      try {
        handle = await handle.getDirectoryHandle(parts[i]);
      } catch {
        try {
          handle = await handle.getFileHandle(parts[i]);
        } catch {
          return null;
        }
      }
    }
    return handle;
  }

  xiaoshu.readFile = async function(mountName, filePath) {
    const parts = [mountName, ...filePath.split('/').filter(Boolean)];
    const handle = await resolvePath(parts);
    if (!handle || handle.kind !== 'file') return null;
    const file = await handle.getFile();
    const text = await file.text();
    return { name: file.name, content: text, size: file.size, type: file.type };
  };

  xiaoshu.writeFile = async function(mountName, filePath, content) {
    const dirs = filePath.split('/').filter(Boolean);
    const fileName = dirs.pop();
    const parts = [mountName, ...dirs];
    const dirHandle = await resolvePath(parts);
    if (!dirHandle || dirHandle.kind !== 'directory') return false;
    const fileHandle = await dirHandle.getFileHandle(fileName, { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(content);
    await writable.close();
    return true;
  };

  // ═══ Unmount ═══
  xiaoshu.unmount = function(name) {
    state.mounts.delete(name);
    renderMounts();
  };

  // ═══ Render ═══
  function classifyFolder(tree) {
    const extensions = { py:0, js:0, ts:0, jsx:0, tsx:0, go:0, rs:0, java:0, cpp:0, c:0, cs:0, toml:0, yaml:0, yml:0, json:0, lock:0, cfg:0, ini:0,
                         md:0, txt:0, pdf:0, docx:0, xlsx:0, pptx:0, html:0, css:0, svg:0 };
    countExt(tree, extensions);
    const codeFiles = extensions.py + extensions.js + extensions.ts + extensions.jsx + extensions.tsx + extensions.go + extensions.rs + extensions.java + extensions.cpp + extensions.c + extensions.cs;
    const configFiles = extensions.toml + extensions.yaml + extensions.yml + extensions.json + extensions.lock + extensions.cfg + extensions.ini;
    const docFiles = extensions.md + extensions.txt + extensions.pdf + extensions.docx + extensions.html;
    const total = codeFiles + configFiles + docFiles || 1;
    if (codeFiles > total * 0.4) return 'code';
    if (docFiles > total * 0.6) return 'docs';
    if (codeFiles > 0 && docFiles > 0) return 'mixed';
    return 'unknown';
  }

  function countExt(node, ext) {
    if (node.kind === 'file') {
      const e = node.name.split('.').pop().toLowerCase();
      if (e in ext) ext[e]++;
    }
    if (node.children) node.children.forEach(c => countExt(c, ext));
  }

  function renderMounts() {
    const el = document.getElementById('local-mounts');
    if (!el) return;
    if (state.mounts.size === 0) {
      el.innerHTML = '<div style="font-size:12px;color:var(--dim);padding:8px">📂 未挂载本地文件夹</div>';
      return;
    }
    let html = '';
    for (const [name, { tree, time }] of state.mounts) {
      html += `<div class="mount-root" style="margin-bottom:4px">`;
      html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0">`;
      const folderType = classifyFolder(tree);
      const typeBadge = folderType === 'code' ? '<span style="font-size:10px;background:#1e40af;color:#bfdbfe;padding:1px 6px;border-radius:8px;margin-left:6px">💻 代码库</span>' :
                        folderType === 'docs' ? '<span style="font-size:10px;background:#166534;color:#bbf7d0;padding:1px 6px;border-radius:8px;margin-left:6px">📄 文档库</span>' :
                        folderType === 'mixed' ? '<span style="font-size:10px;background:#854d0e;color:#fde68a;padding:1px 6px;border-radius:8px;margin-left:6px">📦 混合</span>' : '';
      html += `<span style="font-size:12px;color:var(--accent);cursor:pointer" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">📁 ${name}${typeBadge}</span>`;
      html += `<button style="font-size:10px;padding:2px 6px;background:var(--border)" onclick="xiaoshu.unmount('${name}')">×</button>`;
      html += `</div>`;
      html += `<div style="display:none;padding-left:12px;font-size:11px;max-height:200px;overflow-y:auto">`;
      html += renderTree(tree, name);
      html += `</div></div>`;
    }
    el.innerHTML = html;
  }

  function renderTree(node, mountName) {
    if (node.kind === 'file') {
      const icon = node.name.endsWith('.py') ? '🐍' : node.name.endsWith('.md') ? '📝' : node.name.endsWith('.json') ? '📋' : '📄';
      const path = node.path;
      return `<div style="padding:2px 0;cursor:pointer" onclick="(async()=>{const f=await xiaoshu.readFile('${mountName}','${path}');if(f)xiaoshu.emit('fileRead',f)})()" title="${path}">${icon} ${node.name}</div>`;
    }
    let html = `<div style="font-weight:600">📁 ${node.name}</div>`;
    for (const child of node.children) {
      child.path = node.path + '/' + child.name;
      html += renderTree(child, mountName);
    }
    return html;
  }

  // ═══ Event System ═══
  const listeners = {};
  xiaoshu.on = function(event, fn) { (listeners[event] = listeners[event] || []).push(fn); };
  xiaoshu.emit = function(event, data) { (listeners[event] || []).forEach(fn => fn(data)); };

  // ═══ Chat Integration ═══
  xiaoshu.on('fileRead', (file) => {
    // Insert file content into chat input
    const input = document.querySelector('textarea[name="message"]');
    if (input) {
      input.value = `请分析这个文件 (${file.name}):\n\n\`\`\`\n${file.content.slice(0, 3000)}\n\`\`\``;
      input.dispatchEvent(new Event('input'));
    }
  });

  xiaoshu.on('mount', ({ name, fileCount }) => {
    // Notify chat that a folder was mounted
    const log = document.getElementById('chat-log');
    if (log) {
      log.insertAdjacentHTML('beforeend', 
        `<div class="msg assistant"><div class="who">小树 🌳</div><div class="text">📂 已挂载 <b>${name}</b> (${fileCount} 个文件)。你可以让我搜索这个文件夹里的内容。</div></div>`);
    }
  });

  // ═══ Expose mounted folders to HTMX requests ═══
  document.body.addEventListener('htmx:configRequest', (evt) => {
    const mounts = [];
    for (const [name] of state.mounts) mounts.push(name);
    if (mounts.length > 0) {
      evt.detail.headers['X-Local-Mounts'] = mounts.join(',');
    }
  });

  console.log('🌳 LocalFS ready — 小树可以挂载本地文件夹了');
})();

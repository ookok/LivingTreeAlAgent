/* LivingTree Web — Project Selector Component */

class ProjectSelector extends Component {
  init() {
    this._unsubs.push(LT.on('codemode:changed', (active) => { if (active) this.render(); }));
    this._unsubs.push(LT.on('projects:loaded', () => this.render()));
    this._unsubs.push(LT.on('project:selected', () => this.render()));
    this._unsubs.push(LT.on('project:created', () => this.render()));
    this._unsubs.push(LT.on('project:deleted', () => this.render()));
    this._unsubs.push(LT.on('github:authChanged', () => this.render()));
    this.render();
    if (LT.store) LT.store.loadProjects();
  }

  template() {
    const store = LT.store;
    const projects = store.projects || [];
    const selected = store.selectedProject || '';
    const githubAuthed = store.githubAuthed;

    const hasProjects = projects.length > 0;

    const projectItems = hasProjects ? projects.map(p => {
      const active = p.name === selected ? ' active' : '';
      const typeBadge = p.type === 'code' ? '<span style="font-size:10px;background:#1e40af;color:#bfdbfe;padding:1px 6px;border-radius:8px;margin-left:4px">代码</span>' :
                        p.type === 'docs' ? '<span style="font-size:10px;background:#166534;color:#bbf7d0;padding:1px 6px;border-radius:8px;margin-left:4px">文档</span>' : '';
      return `<div class="proj-item${active}" onclick="LT.get('project-selector')._selectProject('${LT.esc(p.name)}')">
        <span class="proj-icon">${p.type==='code'?'💻':p.type==='docs'?'📄':'📁'}</span>
        <div class="proj-info">
          <span class="proj-name">${LT.esc(p.name)}${typeBadge}</span>
          <span class="proj-meta">${p.file_count || 0} 文件${p.github_url ? ' · 🔗 GitHub' : ''}</span>
        </div>
        <div class="proj-actions">
          <button class="proj-action-btn" onclick="event.stopPropagation();LT.get('project-selector')._scanProject('${LT.esc(p.name)}')" title="安全扫描">🛡️</button>
          ${p.github_url ? `<button class="proj-action-btn" onclick="event.stopPropagation();LT.get('project-selector')._syncProject('${LT.esc(p.name)}')" title="同步">🔄</button>` : ''}
          <button class="proj-action-btn proj-action-del" onclick="event.stopPropagation();LT.get('project-selector')._deleteProject('${LT.esc(p.name)}')" title="删除">🗑️</button>
        </div>
      </div>`;
    }).join('') : `<div class="proj-empty">尚未创建项目</div>`;

    return `<div class="project-selector">
<div class="proj-header">
  <span class="proj-title">📦 项目选择</span>
  <button class="proj-close-btn" onclick="LT.emit('project-selector:close')">✕</button>
</div>
<div class="proj-body">
  <div class="proj-list">${projectItems}</div>
  <div class="proj-actions-row">
    <button class="proj-btn proj-btn-create" onclick="LT.get('project-selector')._showCreateDialog()">
      <svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 2v8M2 6h8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      新建项目
    </button>
    <button class="proj-btn proj-btn-github" onclick="LT.get('project-selector')._handleGitHub()">
      <svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 1C3.2 1 1 3.2 1 6c0 2.2 1.4 4.1 3.4 4.8.3 0 .4-.1.4-.3v-1c-1.4.3-1.7-.6-1.7-.6-.2-.6-.6-.7-.6-.7-.5-.3 0-.3 0-.3.5 0 .8.5.8.5.5.8 1.3.6 1.6.4 0-.3.2-.6.4-.7-1.3-.1-2.6-.6-2.6-2.8 0-.6.2-1.1.6-1.5 0-.2-.3-.7.1-1.5 0 0 .5-.1 1.5.6.4-.1.9-.2 1.4-.2s1 .1 1.4.2c1-.7 1.5-.6 1.5-.6.4.8.1 1.3.1 1.5.4.4.6.9.6 1.5 0 2.2-1.4 2.7-2.6 2.8.2.2.4.5.4 1v1.5c0 .1.1.3.4.3C9.6 10.1 11 8.2 11 6c0-2.8-2.2-5-5-5z" fill="currentColor"/></svg>
      ${githubAuthed ? `从 GitHub 克隆 (已登录: ${LT.esc(store.githubUser)})` : '登录 GitHub'}
    </button>
  </div>
</div>
<div class="proj-create-overlay" id="proj-create-overlay" style="display:none">
  <div class="proj-create-dialog">
    <div class="proj-create-header"><span>新建项目</span><button onclick="LT.get('project-selector')._hideCreateDialog()">✕</button></div>
    <div class="proj-create-body">
      <input class="proj-input" id="proj-create-name" placeholder="项目名称 (字母/数字/中文/连字符)">
      <input class="proj-input" id="proj-create-gh-url" placeholder="GitHub URL (可选)">
      <button class="proj-btn proj-btn-primary" onclick="LT.get('project-selector')._createProject()">创建项目</button>
    </div>
  </div>
</div>
<div class="proj-github-overlay" id="proj-github-overlay" style="display:none">
  <div class="proj-github-dialog">
    <div class="proj-create-header"><span>从 GitHub 克隆</span><button onclick="LT.get('project-selector')._hideGitHubDialog()">✕</button></div>
    <div class="proj-github-body" id="proj-github-repos">
      <div class="proj-loading">加载仓库列表...</div>
    </div>
  </div>
</div>
</div>`;
  }

  _selectProject(name) {
    LT.store.selectProject(name);
    this.render();
  }

  _showCreateDialog() {
    const overlay = document.getElementById('proj-create-overlay');
    if (overlay) overlay.style.display = 'flex';
  }

  _hideCreateDialog() {
    const overlay = document.getElementById('proj-create-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  async _createProject() {
    const nameInput = document.getElementById('proj-create-name');
    const ghInput = document.getElementById('proj-create-gh-url');
    const name = (nameInput?.value || '').trim();
    if (!name) { LT.emit('notify', { msg: '请输入项目名', type: 'error' }); return; }
    const gh = (ghInput?.value || '').trim();
    const result = await LT.store.createProject(name, gh);
    if (result) {
      this._hideCreateDialog();
      LT.emit('notify', { msg: `项目 "${name}" 已创建`, type: 'success' });
      // Auto-scan after creation
      setTimeout(() => this._scanProject(name), 500);
    } else {
      LT.emit('notify', { msg: '创建失败', type: 'error' });
    }
  }

  async _deleteProject(name) {
    if (!confirm(`确定删除项目 "${name}"？所有文件将被永久删除。`)) return;
    const result = await LT.store.deleteProject(name);
    if (result) {
      LT.emit('notify', { msg: `项目 "${name}" 已删除`, type: 'success' });
    }
  }

  async _syncProject(name) {
    LT.emit('notify', { msg: `正在同步 "${name}"...`, type: 'info' });
    const result = await LT.store.syncProject(name);
    if (result && result.ok) {
      LT.emit('notify', { msg: `同步完成: ${name}`, type: 'success' });
      LT.emit('code:refreshTree');
    } else {
      LT.emit('notify', { msg: '同步失败', type: 'error' });
    }
  }

  async _scanProject(name) {
    LT.emit('notify', { msg: `正在扫描 "${name}" 安全...`, type: 'info' });
    const result = await LT.store.scanProject(name);
    if (result) {
      if (result.passed) {
        LT.emit('notify', { msg: `扫描通过: ${name}`, type: 'success' });
      } else {
        const criticals = result.findings.filter(f => f.severity === 'critical').length;
        const highs = result.findings.filter(f => f.severity === 'high').length;
        let warnMsg = `发现 ${result.total} 个安全风险`;
        if (criticals) warnMsg += ` (致命: ${criticals})`;
        if (highs) warnMsg += ` (高危: ${highs})`;
        LT.emit('notify', { msg: warnMsg, type: 'error' });
        LT.emit('security:findings', result.findings);
      }
    }
  }

  async _handleGitHub() {
    if (!LT.store.githubAuthed) {
      await LT.store.loginGitHub();
      return;
    }
    // Show repo list
    const overlay = document.getElementById('proj-github-overlay');
    if (overlay) overlay.style.display = 'flex';
    await this._loadRepos();
  }

  _hideGitHubDialog() {
    const overlay = document.getElementById('proj-github-overlay');
    if (overlay) overlay.style.display = 'none';
  }

  async _loadRepos() {
    const container = document.getElementById('proj-github-repos');
    if (!container) return;
    container.innerHTML = '<div class="proj-loading">加载仓库列表...</div>';
    const repos = await LT.api.githubRepos();
    if (!repos || !Array.isArray(repos)) {
      container.innerHTML = '<div class="proj-empty">加载失败，请重试</div>';
      return;
    }
    if (!repos.length) {
      container.innerHTML = '<div class="proj-empty">没有找到仓库</div>';
      return;
    }
    container.innerHTML = repos.map(r => {
      const name = r.name.split('/').pop();
      return `<div class="proj-repo-item" onclick="LT.get('project-selector')._cloneRepo('${LT.esc(r.url)}','${LT.esc(name)}')">
        <div class="proj-repo-name">⭐ ${r.stars || 0} · ${LT.esc(r.name)}</div>
        <div class="proj-repo-desc">${LT.esc(r.description || '')}</div>
        <div class="proj-repo-meta">${r.language || ''} · ${r.updated_at ? r.updated_at.slice(0, 10) : ''}</div>
      </div>`;
    }).join('');
  }

  async _cloneRepo(url, name) {
    LT.emit('notify', { msg: `正在克隆 ${name}...`, type: 'info' });
    this._hideGitHubDialog();
    const result = await LT.api.githubClone(url, name);
    if (result && result.ok) {
      await LT.store.loadProjects();
      LT.store.selectedProject = name;
      LT.store.save();
      LT.emit('project:created', result);
      LT.emit('notify', { msg: `克隆成功: ${name}`, type: 'success' });
      this.render();
      // Auto-scan after clone
      setTimeout(() => this._scanProject(name), 1000);
    } else {
      LT.emit('notify', { msg: '克隆失败', type: 'error' });
    }
  }
}

LT.register('project-selector', ProjectSelector);

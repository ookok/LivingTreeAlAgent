class BootOverlay extends Component {
  constructor() {
    super('boot-overlay');
    this._timer = null;
    this._pct = 0;
    this._text = '正在初始化...';
  }

  init() {
    this.render();
    this._poll();
  }

  async _poll() {
    for (let i = 0; i < 120; i++) {
      try {
        const r = await fetch('/api/boot/progress');
        const d = await r.json();
        this._pct = d.pct || 0;
        this._text = d.detail || '...';
        this.render();
        if (d.stage === 'ready') {
          await new Promise(r => setTimeout(r, 500));
          this.el.classList.add('hidden');
          setTimeout(() => this.el.remove(), 500);
          return;
        }
      } catch (e) { /* retry on failure */ }
      await new Promise(r => setTimeout(r, 500));
    }
    this.el.remove();
  }

  template() {
    return `
<div class="boot-overlay-box">
  <div class="boot-overlay-logo">🌳</div>
  <div class="boot-overlay-title">LivingTree AI Agent</div>
  <div class="boot-overlay-progress">
    <div class="boot-overlay-bar"><div class="boot-overlay-fill" style="width:${this._pct}%"></div></div>
    <div class="boot-overlay-text">${LT.esc(this._text)}</div>
  </div>
</div>`;
  }

  destroy() {
    super.destroy();
  }
}
LT.register('boot-overlay', BootOverlay);

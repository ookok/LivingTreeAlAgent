/* LivingTree Component Framework */
const LT = {
  _components: {},
  _events: {},

  /* ── Event Bus ── */
  on(event, fn) { (this._events[event] = this._events[event] || []).push(fn); return () => this.off(event, fn) },
  off(event, fn) { const a = this._events[event]; if (a) { const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1) } },
  emit(event, data) { (this._events[event] || []).forEach(fn => fn(data)) },

  /* ── Component Registry ── */
  register(name, comp) { this._components[name] = comp },
  get(name) { return this._components[name] },

  /* ── HTML helpers ── */
  html(strings, ...values) {
    const raw = strings.reduce((r, s, i) => r + s + (values[i] || ''), '');
    const t = document.createElement('template'); t.innerHTML = raw.trim();
    return t.content.firstElementChild || t.content;
  },
  qs(sel, root) { return (root || document).querySelector(sel) },
  qsa(sel, root) { return [...(root || document).querySelectorAll(sel)] },
  ge(id) { return document.getElementById(id) },
  esc(s) { const m = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }; return String(s).replace(/[&<>"']/g, c => m[c]) },

  /* ── Storage ── */
  load(key) { try { return JSON.parse(localStorage[key] || 'null') } catch (e) { return null } },
  save(key, val) { localStorage[key] = JSON.stringify(val) },
};

/* ── Component Base Class ── */
class Component {
  constructor(el, props = {}) { this.el = typeof el === 'string' ? LT.ge(el) : el; this.props = props; this._state = {}; this._unsubs = []; }
  setState(patch) { Object.assign(this._state, patch); this.render() }
  state() { return this._state }
  on(event, fn) { this._unsubs.push(LT.on(event, fn)) }
  emit(event, data) { LT.emit(event, data) }
  template() { return '' }
  render() { if (this.el) this.el.innerHTML = this.template() }
  init() { this.render() }
  destroy() { this._unsubs.forEach(fn => fn()); this._unsubs = []; if (this.el) this.el.innerHTML = '' }
}

window.LT = LT;
window.Component = Component;

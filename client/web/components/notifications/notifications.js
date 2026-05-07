class Notifications extends Component {
  constructor() {
    super('notifications');
    this.on('notify', ({ msg, type }) => this._show(msg, type));
  }

  _show(msg, type = 'info') {
    const card = LT.html`<div class="notif-card ${type}">${LT.esc(msg)}</div>`;
    this.el.appendChild(card);
    setTimeout(() => {
      card.classList.add('exiting');
      setTimeout(() => card.remove(), 300);
    }, 3000);
  }

  template() { return ''; }
}
LT.register('notifications', Notifications);

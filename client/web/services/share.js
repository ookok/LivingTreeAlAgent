/* ═══════════════════════════════════
   LivingTree Web — Share Service
   Supports: WeChat, WeCom, copy link
   PC: QR code | Mobile: native share + URL scheme
   ═══════════════════════════════════ */

const Share = {

  /* ── Detect platform ── */
  isMobile() {
    return /Android|iPhone|iPad|iPod|webOS/i.test(navigator.userAgent);
  },

  isWeChat() {
    return /MicroMessenger/i.test(navigator.userAgent);
  },

  isWeCom() {
    return /wxwork/i.test(navigator.userAgent);
  },

  /* ── Open share modal ── */
  open(content, title) {
    const modal = document.getElementById('share-modal');
    if (!modal) return;

    // Render template on first use
    if (!modal.querySelector('.share-modal-panel')) {
      modal.innerHTML = this.template();
    }

    this._content = content;
    this._title = title || content.slice(0, 40);

    // Preview
    const preview = modal.querySelector('.share-preview');
    if (preview) preview.textContent = this._title;

    // QR code (PC)
    const qrWrap = modal.querySelector('.share-qr-wrap');
    if (qrWrap) {
      qrWrap.style.display = this.isMobile() ? 'none' : 'block';
      if (!this.isMobile()) {
        const qrImg = qrWrap.querySelector('.share-qr-img');
        if (qrImg) {
          const shareText = this._title + '\n\n' + content.slice(0, 500);
          qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(shareText);
          qrImg.alt = shareText;
        }
      }
    }

    // Mobile buttons
    const mobileBtns = modal.querySelector('.share-mobile-btns');
    if (mobileBtns) {
      mobileBtns.style.display = this.isMobile() ? 'flex' : 'none';
    }

    // WeChat/WeCom direct
    const wxDirect = modal.querySelector('.share-wx-direct');
    if (wxDirect) wxDirect.style.display = this.isWeChat() ? 'flex' : 'none';

    modal.style.display = 'flex';
  },

  close() {
    const modal = document.getElementById('share-modal');
    if (modal) modal.style.display = 'none';
  },

  /* ── Copy share link ── */
  copyLink() {
    const text = this._content;
    navigator.clipboard.writeText(text).then(() => {
      LT.emit('notify', { msg: '已复制分享内容', type: 'success' });
      this.close();
    }).catch(() => {
      this._fallbackCopy(text);
    });
  },

  /* ── Copy markdown ── */
  copyMarkdown() {
    const text = this._content;
    this._doCopy(text, '已复制 Markdown');
  },

  _doCopy(text, msg) {
    navigator.clipboard.writeText(text).then(() => {
      LT.emit('notify', { msg, type: 'success' });
    }).catch(() => {
      this._fallbackCopy(text);
    });
  },

  _fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); LT.emit('notify', { msg: '已复制', type: 'success' }); }
    catch (e) { LT.emit('notify', { msg: '复制失败', type: 'error' }); }
    document.body.removeChild(ta);
  },

  /* ── Share to WeChat (mobile) ── */
  shareToWeChat() {
    if (navigator.share) {
      navigator.share({ title: this._title, text: this._content.slice(0, 200) }).catch(() => {});
    } else {
      this.copyLink();
    }
  },

  /* ── Share to WeCom (mobile) ── */
  shareToWeCom() {
    // Try wxwork:// scheme — may not work without signature
    const text = encodeURIComponent(this._title + '\n' + this._content.slice(0, 500));
    const url = 'wxwork://message?username=&body=' + text;
    const a = document.createElement('a');
    a.href = url;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Fallback: copy
    setTimeout(() => {
      if (!document.hidden && this.isMobile()) {
        this.copyLink();
      }
    }, 800);
  },

  /* ── Share modal template ── */
  template() {
    return `
<div class="modal-panel share-modal-panel" onclick="event.stopPropagation()">
  <div class="modal-header">
    <span class="modal-title">分享消息</span>
    <button class="modal-close" onclick="Share.close()">
      <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
  </div>
  <div class="modal-body">
    <div class="share-preview"></div>

    <!-- QR Code (PC only) -->
    <div class="share-qr-wrap">
      <div class="share-section-title">扫码分享到微信</div>
      <img class="share-qr-img" src="" alt="QR Code" width="200" height="200">
      <div class="share-qr-hint">用微信扫一扫即可分享</div>
    </div>

    <!-- Mobile share buttons -->
    <div class="share-mobile-btns">
      <button class="share-btn share-btn-wx" onclick="Share.shareToWeChat()">
        <svg width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="9" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6.5 8.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM13.5 8.5a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM6 11.5c-1.5 1-1.5 3.5 0 4.5M14 11.5c1.5 1 1.5 3.5 0 4.5" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>
        <span>分享到微信</span>
      </button>
      <button class="share-btn share-btn-wxwork" onclick="Share.shareToWeCom()">
        <svg width="20" height="20" viewBox="0 0 20 20"><rect x="2" y="3" width="16" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6 8h8M6 11h5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
        <span>分享到企业微信</span>
      </button>
    </div>

    <!-- In-WeChat direct share -->
    <div class="share-wx-direct">
      <div class="share-section-title">长按复制以下内容分享</div>
      <div class="share-wx-text"></div>
    </div>

    <!-- Copy link (always available) -->
    <div class="share-copy-row">
      <button class="share-btn share-btn-copy" onclick="Share.copyLink()">
        <svg width="16" height="16" viewBox="0 0 16 16"><rect x="5" y="5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M11 5V3a1.5 1.5 0 00-1.5-1.5h-6A1.5 1.5 0 002 3v6a1.5 1.5 0 001.5 1.5H5" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
        <span>复制分享内容</span>
      </button>
      <button class="share-btn share-btn-md" onclick="Share.copyMarkdown()">
        <svg width="16" height="16" viewBox="0 0 16 16"><path d="M2 4h12v8H2z" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5 7h6M5 10h4" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>
        <span>复制 Markdown</span>
      </button>
    </div>
  </div>
</div>`;
  }
};

/* Register & expose */
window.Share = Share;

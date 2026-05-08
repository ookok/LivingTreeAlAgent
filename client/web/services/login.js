/* WeChat Work Login Handler */
(function() {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');

  if (code) {
    handleLogin(code, 'oauth');
  }

  window.doOAuthLogin = async function() {
    try {
      const r = await fetch('/api/login/config');
      const c = await r.json();
      if (c.oauth_url) { window.location.href = c.oauth_url; return; }
      handleLogin('dev_test_code_001', 'oauth');
    } catch (e) { showError('获取登录配置失败'); devLogin(); }
  };

  window.toggleQR = function() {
    const w = document.getElementById('qr-wrap');
    w.classList.toggle('show');
    if (w.classList.contains('show')) loadQRCode();
  };

  async function loadQRCode() {
    try {
      const r = await fetch('/api/login/config');
      const c = await r.json();
      if (c.corp_id) {
        const url = `https://login.work.weixin.qq.com/wwlogin/sso/login?login_type=login_admin&appid=${c.corp_id}&agentid=${c.agent_id}&redirect_uri=${encodeURIComponent(location.origin+'/login.html')}&state=${Date.now()}`;
        document.getElementById('qr-placeholder').style.display = 'none';
        const img = document.getElementById('qr-img');
        img.style.display = 'block';
        img.src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(url)}&bgcolor=ffffff`;
        document.getElementById('qr-hint').textContent = '请使用企业微信扫描二维码';
      }
    } catch (e) {}
  }

  async function handleLogin(authCode, loginType) {
    const btn = document.getElementById('btn-wework');
    btn.innerHTML = '<div class="app-spinner"></div>';
    btn.disabled = true;
    try {
      const r = await fetch('/api/login/wework', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({code:authCode, login_type:loginType}),
      });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
      const data = await r.json();
      localStorage.setItem('lt_token', data.token);
      localStorage.setItem('lt_user', JSON.stringify({user_id:data.user_id, name:data.name}));
      location.href = urlParams.get('redirect') || '/';
    } catch (e) { showError(e.message); btn.disabled = false; btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 20 20"><rect x="2" y="3" width="16" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 8h8M6 11h5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg><span>企业微信登录</span>'; }
  }

  function devLogin() { handleLogin('dev_test_code_001', 'oauth'); }

  function showError(m) { const e = document.getElementById('login-error'); e.textContent = m; e.classList.add('show'); setTimeout(() => e.classList.remove('show'), 5000); }

  // Auto OAuth in WeCom browser
  if (/wxwork|wechatwork/i.test(navigator.userAgent)) doOAuthLogin();
})();

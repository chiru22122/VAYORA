/**
 * VAYORA CLIENT-SIDE API & UI ORCHESTRATION ENGINE
 * Handles network requests, token authentication, dynamic toasts,
 * real-time presence (WebSocket + heartbeat), and real payment checkout modal.
 */

const VAYORA = (function() {
  // Read runtime environment configuration (supports frontend/.env and window.__ENV__)
  window.__ENV__ = window.__ENV__ || {};

  const DEFAULT_PROD_BACKEND = (typeof window !== 'undefined' && window.location && window.location.origin)
    ? window.location.origin
    : "http://127.0.0.1:8000";

  function isLocalOrigin() {
    if (typeof window === 'undefined' || !window.location) return true;
    const h = window.location.hostname;
    const p = window.location.protocol;
    return (
      p === 'file:' ||
      h === 'localhost' ||
      h === '127.0.0.1' ||
      h === '0.0.0.0' ||
      h.startsWith('192.168.') ||
      h.startsWith('10.') ||
      h.endsWith('.local') ||
      h === ''
    );
  }

  function getBackendUrl() {
    const isBrowser = typeof window !== 'undefined' && window.location;
    if (!isBrowser) return 'http://127.0.0.1:8000';

    if (isLocalOrigin()) {
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem('VAYORA_BACKEND_URL');
        if (stored && (stored.includes('vercel.app') || stored.includes('onrender.com'))) {
          localStorage.removeItem('VAYORA_BACKEND_URL');
        }
      }
      if (window.location.port === '8000') {
        return `${window.location.protocol}//${window.location.host}`;
      }
      const localHost = (window.location.hostname && window.location.hostname !== '') ? window.location.hostname : '127.0.0.1';
      return `http://${localHost}:8000`;
    }

    // 1. Explicit runtime environment bridge (window.__ENV__)
    if (window.__ENV__ && window.__ENV__.BACKEND_URL) {
      return window.__ENV__.BACKEND_URL.replace(/\/+$/, '');
    }
    // 2. Safe HTML meta tag configuration: <meta name="backend-url" content="...">
    if (typeof document !== 'undefined') {
      const meta = document.querySelector('meta[name="backend-url"]');
      if (meta && meta.content) {
        return meta.content.trim().replace(/\/+$/, '');
      }
    }
    // 3. Browser localStorage override (allows runtime configuration in browser console)
    const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('VAYORA_BACKEND_URL') : null;
    if (stored) {
      return stored.trim().replace(/\/+$/, '');
    }

    // 4. Default production backend URL
    return DEFAULT_PROD_BACKEND;
  }

  function getAppName() {
    return (window.__ENV__ && window.__ENV__.APP_NAME)
      ? window.__ENV__.APP_NAME
      : "VAYORA - Your Digital Value, One Journey";
  }

  function getApiBase() {
    const isBrowser = typeof window !== 'undefined' && window.location;
    if (!isBrowser) return 'http://127.0.0.1:8000/api';

    // When directly served on port 8000 or hosted on Vercel unified deployment,
    // relative /api connects directly to the FastAPI server on the same domain
    if (window.location.port === '8000' || (window.location.hostname && window.location.hostname.includes('vercel.app'))) {
      return '/api';
    }

    // When opened from other ports (e.g. 5500 Live Server, 3000, 5173) or file://,
    // explicitly connect to backend URL on port 8000
    const backend = getBackendUrl();
    return backend ? `${backend}/api` : 'http://127.0.0.1:8000/api';
  }

  function setBackendUrl(url) {
    if (!url) return;
    const clean = url.replace(/\/+$/, '');
    window.__ENV__.BACKEND_URL = clean;
    localStorage.setItem('VAYORA_BACKEND_URL', clean);
  }

  // Asynchronously attempt to load frontend/.env if hosted statically
  (async function loadFrontendEnv() {
    try {
      const res = await fetch('/.env');
      if (res.ok) {
        const text = await res.text();
        text.split('\n').forEach(line => {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith('#')) return;
          const idx = trimmed.indexOf('=');
          if (idx > -1) {
            const key = trimmed.slice(0, idx).trim();
            const val = trimmed.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
            window.__ENV__[key] = val;
          }
        });
      }
    } catch (e) {}
  })();

  let _presenceWs = null;
  let _presenceHeartbeatTimer = null;
  let _onlineUsersCache = [];

  function getToken() {
    return localStorage.getItem('vayora_token');
  }

  function setToken(token) {
    localStorage.setItem('vayora_token', token);
  }

  function getCurrentUser() {
    try {
      const u = localStorage.getItem('vayora_user');
      return u ? JSON.parse(u) : null;
    } catch (e) {
      return null;
    }
  }

  function setCurrentUser(user) {
    localStorage.setItem('vayora_user', JSON.stringify(user));
  }

  function logout() {
    localStorage.removeItem('vayora_token');
    localStorage.removeItem('vayora_user');
    window.location.href = '/login.html';
  }

  async function request(endpoint, options = {}) {
    const apiBase = getApiBase();
    let url;
    if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
      url = endpoint;
    } else {
      const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
      url = `${apiBase}${cleanEndpoint}`;
    }
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    const token = getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const config = {
        method: options.method || 'GET',
        headers,
        ...options
      };

      if (options.body && typeof options.body === 'object') {
        config.body = JSON.stringify(options.body);
      }

      const response = await fetch(url, config);

      if (response.status === 401) {
        const path = window.location.pathname;
        if (!path.includes('login.html') && !path.includes('register.html') && !path.endsWith('/') && !path.includes('index.html')) {
          logout();
          return null;
        }
      }

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const errorMsg = data.detail || data.message || `Request failed (${response.status})`;
        throw new Error(errorMsg);
      }

      return data;
    } catch (error) {
      console.error(`[VAYORA API Error] ${endpoint}:`, error);
      if (typeof window !== 'undefined' && error instanceof TypeError && error.message.toLowerCase().includes('fetch')) {
        console.warn(`[VAYORA Backend Notice] Could not connect to API at: ${url}. Verify backend status at /api/health`);
        throw new Error(`Could not connect to API at ${url}. Make sure local server is running on port 8000.`);
      }
      throw error;
    }
  }

  // --- NATIVE WEB AUDIO SCI-FI SOUND SYNTHESIZER ---
  let _audioCtx = null;
  let _soundEnabled = localStorage.getItem('vayora_sound_fx') !== 'false';

  function getAudioContext() {
    if (!_audioCtx && typeof window !== 'undefined') {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (AudioCtxClass) _audioCtx = new AudioCtxClass();
    }
    if (_audioCtx && _audioCtx.state === 'suspended') {
      _audioCtx.resume();
    }
    return _audioCtx;
  }

  function playSound(type) {
    if (!_soundEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;

      if (type === 'click') {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, now);
        osc.frequency.exponentialRampToValueAtTime(400, now + 0.04);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.04);
      } else if (type === 'success') {
        // Two-tone cyber chime (523Hz -> 784Hz)
        [523.25, 659.25, 783.99].forEach((freq, i) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(freq, now + i * 0.09);
          gain.gain.setValueAtTime(0.12, now + i * 0.09);
          gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.09 + 0.28);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + i * 0.09);
          osc.stop(now + i * 0.09 + 0.28);
        });
      } else if (type === 'coin') {
        // Crystal coin clink (987Hz -> 1318Hz)
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(987.77, now);
        osc.frequency.setValueAtTime(1318.51, now + 0.06);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.22);
      } else if (type === 'nfc') {
        // High-tech Sonar Ping
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(1200, now);
        osc.frequency.exponentialRampToValueAtTime(2400, now + 0.15);
        gain.gain.setValueAtTime(0.18, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.35);
      } else if (type === 'error') {
        // Low Warning Buzzer
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(180, now);
        osc.frequency.linearRampToValueAtTime(120, now + 0.18);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.18);
      }
    } catch (e) {
      console.warn('Audio play error', e);
    }
  }

  function toggleSound() {
    _soundEnabled = !_soundEnabled;
    localStorage.setItem('vayora_sound_fx', _soundEnabled.toString());
    showToast('Sound Effects', _soundEnabled ? 'Futuristic Audio FX Enabled 🔊' : 'Audio Muted 🔇', 'info', 2000);
    if (_soundEnabled) playSound('success');
    updateSoundToggleUI();
  }

  function updateSoundToggleUI() {
    const soundBtns = document.querySelectorAll('.sound-toggle-btn');
    soundBtns.forEach(btn => {
      btn.innerHTML = _soundEnabled
        ? '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>'
        : '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>';
      btn.title = _soundEnabled ? 'Mute Sound FX' : 'Enable Sound FX';
    });
  }

  // Toast Notification System
  function showToast(title, message, type = 'success', duration = 4500) {
    if (type === 'success') playSound('success');
    else if (type === 'error') playSound('error');
    else playSound('click');

    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    // Suppress duplicate toasts if the same message is already currently displayed
    const activeToasts = container.querySelectorAll('.vayora-toast');
    for (const active of activeToasts) {
      const activeMsg = active.querySelector('.toast-message');
      if (activeMsg && activeMsg.textContent.trim() === String(message || '').trim()) {
        return;
      }
    }

    const toast = document.createElement('div');
    toast.className = `vayora-toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>';
    } else {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
    }

    toast.innerHTML = `
      <div class="toast-icon">${iconSvg}</div>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        <div class="toast-message">${message}</div>
      </div>
    `;

    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 400);
    }, duration);
  }

  // Count-up animation for balance numbers
  function animateValue(elem, start, end, duration = 1200, formatFn = null) {
    if (!elem) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      elem.textContent = formatFn ? formatFn(end) : end;
      return;
    }
    const startTime = performance.now();
    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = start + (end - start) * ease;
      elem.textContent = formatFn ? formatFn(current) : current.toFixed(2);
      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        elem.textContent = formatFn ? formatFn(end) : end;
      }
    }
    requestAnimationFrame(update);
  }

  function formatCurrencyINR(amount) {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2
    }).format(amount);
  }

  function formatCurrencyUSD(amount) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 2
    }).format(amount);
  }

  function parseDate(dateStr) {
    if (!dateStr) return null;
    if (dateStr instanceof Date) return dateStr;
    let s = String(dateStr).trim();
    // If ISO date string has no timezone indicator, treat as UTC
    if (!s.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(s)) {
      if (s.includes(' ') && !s.includes('T')) {
        s = s.replace(' ', 'T');
      }
      s += 'Z';
    }
    const d = new Date(s);
    return isNaN(d.getTime()) ? new Date(dateStr) : d;
  }

  function formatDate(dateStr, includeSeconds = false) {
    if (!dateStr) return '—';
    const d = parseDate(dateStr);
    if (!d || isNaN(d.getTime())) return String(dateStr);
    
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      ...(includeSeconds ? { second: '2-digit' } : {}),
      hour12: true
    });
  }

  function formatDateTime(dateStr) {
    return formatDate(dateStr, true);
  }

  function formatDateOnly(dateStr) {
    if (!dateStr) return '—';
    const d = parseDate(dateStr);
    if (!d || isNaN(d.getTime())) return String(dateStr);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  }

  function formatTimeOnly(dateStr, includeSeconds = true) {
    if (!dateStr) return '—';
    const d = parseDate(dateStr);
    if (!d || isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      ...(includeSeconds ? { second: '2-digit' } : {}),
      hour12: true
    });
  }

  // Demo Switcher Helper - Disabled in Production
  async function switchDemoUser() {}

  // --- REAL-TIME PRESENCE & WEBSOCKET ENGINE ---

  function initRealtimePresence() {
    const user = getCurrentUser();
    if (!user) return;

    // Connect WebSocket to BACKEND_URL
    const backend = getBackendUrl();
    let wsUrl;
    try {
      const u = new URL(backend);
      const proto = u.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${proto}//${u.host}/api/ws/presence`;
    } catch (e) {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${proto}//${window.location.host}/api/ws/presence`;
    }

    try {
      _presenceWs = new WebSocket(wsUrl);

      _presenceWs.onopen = () => {
        // Send initial identification
        _presenceWs.send(JSON.stringify({
          type: "IDENTIFY",
          user_id: user.user_id,
          page: window.location.pathname
        }));
      };

      _presenceWs.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "PRESENCE_UPDATE") {
            _onlineUsersCache = msg.online_users || [];
            updatePresenceUI(msg.online_count, msg.online_users);
          } else if (msg.type === "PAYMENT_EVENT") {
            handleRealtimePaymentAlert(msg.data);
          }
        } catch (e) {
          console.warn("WS Parse Error", e);
        }
      };

      _presenceWs.onclose = () => {
        // Reconnect after 6s
        setTimeout(initRealtimePresence, 6000);
      };
    } catch (e) {
      console.warn("WS Connection Error", e);
    }

    // Fallback periodic HTTP heartbeat every 15s
    clearInterval(_presenceHeartbeatTimer);
    _presenceHeartbeatTimer = setInterval(sendHeartbeat, 15000);
    sendHeartbeat();
  }

  async function sendHeartbeat() {
    const user = getCurrentUser();
    if (!user) return;
    const pageName = window.location.pathname.replace(/^\/|\.html$/g, '') || 'dashboard';

    try {
      const res = await request(`/user/heartbeat?page=${encodeURIComponent(pageName)}`, {
        method: 'POST'
      });
      if (res && res.online_count !== undefined) {
        _onlineUsersCache = res.online_users || [];
        updatePresenceUI(res.online_count, res.online_users);
      }
    } catch (e) {
      // Non-fatal heartbeat warning
    }
  }

  function handleRealtimePaymentAlert(data) {
    const user = getCurrentUser();
    if (!user || !data) return;

    const userEmail = (user.email || '').toLowerCase().trim();
    const recvEmail = (data.receiver_email || '').toLowerCase().trim();
    const depEmail = (data.user_email || '').toLowerCase().trim();

    if (data.event === "PAYMENT_RECEIVED" && recvEmail === userEmail) {
      showToast(
        '💰 Funds Received!',
        `+${data.amount} ${data.asset_symbol} received from ${data.sender_email}`,
        'success',
        6000
      );
      // Dispatch custom event for page refresh
      window.dispatchEvent(new CustomEvent('vayora:payment_received', { detail: data }));
    } else if (data.event === "DEPOSIT_COMPLETED" && depEmail === userEmail) {
      showToast(
        '🧾 Deposit Succeeded',
        `+${data.amount} ${data.symbol} added to your wallet balance.`,
        'success',
        5000
      );
      window.dispatchEvent(new CustomEvent('vayora:deposit_settled', { detail: data }));
    }
  }

  function updatePresenceUI(count, users) {
    const countBadge = document.getElementById('global-presence-count');
    if (countBadge) {
      countBadge.textContent = `${count} Online`;
    }

    // Dispatch global event for admin or other monitors
    window.dispatchEvent(new CustomEvent('vayora:presence_update', {
      detail: { count, users }
    }));
  }

  function renderPresencePill() {
    const topbarRight = document.querySelector('.topbar-right');
    if (!topbarRight || document.getElementById('global-presence-pill')) return;

    const pill = document.createElement('div');
    pill.id = 'global-presence-pill';
    pill.className = 'realtime-presence-pill';
    pill.title = 'Click to view active users online now';
    pill.innerHTML = `
      <span class="status-pulse-dot" style="width: 8px; height: 8px; background: var(--neon-emerald); border-radius: 50%; box-shadow: var(--glow-emerald);"></span>
      <span id="global-presence-count" style="font-size: 0.75rem; font-weight: 700; color: var(--text-primary);">1 Online</span>
    `;

    pill.addEventListener('click', openOnlineUsersModal);
    topbarRight.insertBefore(pill, topbarRight.firstChild);
  }

  // --- THEME MANAGEMENT ENGINE (CLEAN LIGHT / DARK) ---
  function getPreferredTheme() {
    return localStorage.getItem('vayora_theme') || 'light';
  }

  function initTheme() {
    const currentTheme = getPreferredTheme();
    document.documentElement.setAttribute('data-theme', currentTheme);
    renderThemeToggleBtn();
  }

  function updateThemeToggleButtons(theme) {
    const isDark = theme === 'dark';
    const buttons = document.querySelectorAll('.theme-toggle-btn');
    buttons.forEach(btn => {
      btn.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
      btn.innerHTML = isDark
        ? '<span style="font-size: 0.95rem;">☀️</span><span>Light</span>'
        : '<span style="font-size: 0.95rem;">🌙</span><span>Dark</span>';
    });
  }

  function renderThemeToggleBtn() {
    if (document.getElementById('theme-toggle-btn')) {
      updateThemeToggleButtons(document.documentElement.getAttribute('data-theme') || getPreferredTheme());
      return;
    }

    const currentTheme = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
    const isDark = currentTheme === 'dark';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'theme-toggle-btn';
    btn.className = 'theme-toggle-btn';
    btn.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
    btn.innerHTML = isDark
      ? '<span style="font-size: 0.95rem;">☀️</span><span>Light</span>'
      : '<span style="font-size: 0.95rem;">🌙</span><span>Dark</span>';

    btn.addEventListener('click', toggleTheme);

    const topbarRight = document.querySelector('.topbar-right');
    const landingNavRight = document.querySelector('.landing-nav > div:last-child');

    if (topbarRight) {
      const profileChip = topbarRight.querySelector('.user-profile-chip');
      if (profileChip) {
        topbarRight.insertBefore(btn, profileChip);
      } else {
        topbarRight.appendChild(btn);
      }
    } else if (landingNavRight) {
      landingNavRight.insertBefore(btn, landingNavRight.firstChild);
    }
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || getPreferredTheme();
    const nextTheme = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', nextTheme);
    localStorage.setItem('vayora_theme', nextTheme);

    updateThemeToggleButtons(nextTheme);
    showToast('Theme Updated', `Switched to ${nextTheme === 'dark' ? 'Dark' : 'Light'} theme`, 'info', 1800);

    window.dispatchEvent(new CustomEvent('vayora:theme_changed', { detail: { theme: nextTheme } }));
  }

  function openOnlineUsersModal() {
    let modal = document.getElementById('presence-users-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'presence-users-modal';
      modal.className = 'modal-backdrop';
      modal.innerHTML = `
        <div class="modal-window" style="max-width: 500px;">
          <div class="modal-header">
            <div class="modal-title" style="display: flex; align-items: center; gap: 8px;">
              <span class="status-pulse-dot" style="width: 8px; height: 8px; background: var(--neon-emerald); border-radius: 50%;"></span>
              <span>Real-Time Online Users</span>
            </div>
            <button class="modal-close-btn" onclick="document.getElementById('presence-users-modal').classList.remove('open')">✕</button>
          </div>
          <div class="modal-body">
            <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 14px;">
              Active sessions currently connected to VAYORA Network:
            </p>
            <div id="presence-users-list-body" style="max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px;">
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }

    const listBody = document.getElementById('presence-users-list-body');
    if (listBody) {
      if (!_onlineUsersCache || _onlineUsersCache.length === 0) {
        listBody.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 16px;">Detecting online users...</div>';
      } else {
        listBody.innerHTML = _onlineUsersCache.map(u => `
          <div style="background: var(--bg-secondary); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 12px 14px; display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div style="width: 34px; height: 34px; border-radius: 50%; background: ${u.avatar_color || '#00f59b'}; color: #000; font-weight: 800; display: flex; align-items: center; justify-content: center; font-size: 0.85rem;">
                ${u.name.charAt(0).toUpperCase()}
              </div>
              <div>
                <div style="font-weight: 700; color: var(--text-primary); font-size: 0.85rem;">${u.name}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${u.email}</div>
              </div>
            </div>
            <div style="text-align: right;">
              <span class="status-pill ${u.status === 'ONLINE' ? 'status-completed' : 'status-pending'}" style="font-size: 0.68rem; padding: 2px 8px;">
                ${u.status}
              </span>
              <div style="font-size: 0.7rem; color: var(--neon-cyan); margin-top: 3px;">${u.current_page}</div>
            </div>
          </div>
        `).join('');
      }
    }

    modal.classList.add('open');
  }

  // --- REAL PAYMENT / DEPOSIT CHECKOUT MODAL ENGINE ---

  function openDepositModal(defaultCurrency = 'USDT') {
    let modal = document.getElementById('deposit-checkout-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'deposit-checkout-modal';
      modal.className = 'modal-backdrop';
      modal.innerHTML = `
        <div class="modal-window" style="max-width: 540px;">
          <div class="modal-header">
            <div class="modal-title" style="display: flex; align-items: center; gap: 8px;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: var(--neon-emerald);"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
              <span>Add Real Funds / Card Checkout</span>
            </div>
            <button class="modal-close-btn" onclick="document.getElementById('deposit-checkout-modal').classList.remove('open')">✕</button>
          </div>
          <div class="modal-body">
            
            <!-- Quick Preset Amount Pills -->
            <div style="margin-bottom: 16px;">
              <div style="font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 6px;">Select Deposit Amount:</div>
              <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <button type="button" class="deposit-preset-btn active" data-amt="25">$25</button>
                <button type="button" class="deposit-preset-btn" data-amt="50">$50</button>
                <button type="button" class="deposit-preset-btn" data-amt="100">$100</button>
                <button type="button" class="deposit-preset-btn" data-amt="250">$250</button>
                <button type="button" class="deposit-preset-btn" data-amt="500">$500</button>
              </div>
            </div>

            <!-- Amount Input and Currency -->
            <div class="form-group">
              <div class="form-label">
                <span>Custom Deposit Amount</span>
                <span style="color: var(--neon-cyan);">Instant Ledger Credit</span>
              </div>
              <div style="display: flex; gap: 10px;">
                <input type="number" id="deposit-amount-input" class="form-control" value="25" min="1" step="any" style="font-family: var(--font-mono); font-size: 1.25rem; font-weight: 700;">
                <select id="deposit-currency-select" class="form-control" style="width: 120px; font-weight: 700; cursor: pointer;">
                  <option value="USDT">USDT</option>
                  <option value="USD">USD</option>
                  <option value="INR">INR</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
            </div>

            <!-- Payment Method Tabs -->
            <div style="display: flex; gap: 8px; margin: 16px 0;">
              <button type="button" class="deposit-method-tab active" data-method="card">💳 Card (Stripe Sandbox)</button>
              <button type="button" class="deposit-method-tab" data-method="applepay"> Apple / Google Pay</button>
              <button type="button" class="deposit-method-tab" data-method="bank">🏦 Bank Direct Debit</button>
            </div>

            <!-- Card Details Form -->
            <div id="deposit-card-section" style="background: var(--bg-secondary); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 18px; margin-bottom: 18px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <span style="font-size: 0.75rem; font-weight: 700; color: var(--text-primary); text-transform: uppercase;">Stripe Sandbox Checkout</span>
                  <span style="font-size: 0.65rem; background: rgba(14, 165, 233, 0.12); color: #0284c7; padding: 2px 6px; border-radius: 4px; font-weight: 700; letter-spacing: 0.5px;">TEST MODE</span>
                </div>
                <button type="button" id="fill-test-card-btn" class="demo-btn-pill" style="margin: 0; padding: 3px 8px; font-size: 0.7rem;">Use Test Card (4242)</button>
              </div>

              <div class="form-group" style="margin-bottom: 12px;">
                <label class="form-label" style="font-size: 0.75rem;">Card Number</label>
                <input type="text" id="checkout-card-num" class="form-control" placeholder="4242 •••• •••• 4242" maxlength="19" style="font-family: var(--font-mono);">
              </div>

              <div style="display: flex; gap: 10px;">
                <div class="form-group" style="flex: 1; margin-bottom: 0;">
                  <label class="form-label" style="font-size: 0.75rem;">Expiry Date</label>
                  <input type="text" id="checkout-card-exp" class="form-control" placeholder="12/28" maxlength="5" style="font-family: var(--font-mono);">
                </div>
                <div class="form-group" style="flex: 1; margin-bottom: 0;">
                  <label class="form-label" style="font-size: 0.75rem;">CVC / CVV</label>
                  <input type="password" id="checkout-card-cvc" class="form-control" placeholder="888" maxlength="4" style="font-family: var(--font-mono);">
                </div>
              </div>
            </div>

            <!-- Alternative Section (Initially hidden) -->
            <div id="deposit-upi-section" style="display: none; background: var(--bg-secondary); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 18px; margin-bottom: 18px; text-align: center;">
              <div style="font-size: 0.85rem; font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">Stripe Express / Direct Settlement</div>
              <p style="font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 14px;">One-click test authorization with Stripe Sandbox Express credentials:</p>
              <input type="text" id="checkout-upi-vpa" class="form-control" value="express_test_authorized@stripe.vayora" readonly style="font-family: var(--font-mono); text-align: center; margin-bottom: 10px; background: var(--bg-primary);">
            </div>

            <!-- Submit Button -->
            <button type="button" id="execute-deposit-btn" class="btn btn-primary btn-block btn-lg">
              Confirm & Pay <span id="deposit-btn-amount">$25.00 USD</span>
            </button>

            <div style="text-align: center; margin-top: 12px; font-size: 0.72rem; color: var(--text-muted); display: flex; align-items: center; justify-content: center; gap: 6px;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <span>256-Bit Encrypted &bull; Automated Real Email Receipt Dispatched</span>
            </div>

          </div>
        </div>
      `;
      document.body.appendChild(modal);
      bindDepositModalEvents();
    }

    const currSelect = document.getElementById('deposit-currency-select');
    if (currSelect) currSelect.value = defaultCurrency;
    updateDepositBtnLabel();

    modal.classList.add('open');
  }

  function bindDepositModalEvents() {
    const amtInput = document.getElementById('deposit-amount-input');
    const currSelect = document.getElementById('deposit-currency-select');
    const presetBtns = document.querySelectorAll('.deposit-preset-btn');
    const methodTabs = document.querySelectorAll('.deposit-method-tab');
    const testCardBtn = document.getElementById('fill-test-card-btn');
    const cardSection = document.getElementById('deposit-card-section');
    const upiSection = document.getElementById('deposit-upi-section');
    const executeBtn = document.getElementById('execute-deposit-btn');

    presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        presetBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        amtInput.value = btn.getAttribute('data-amt');
        updateDepositBtnLabel();
      });
    });

    if (amtInput) {
      amtInput.addEventListener('input', () => {
        presetBtns.forEach(b => b.classList.remove('active'));
        updateDepositBtnLabel();
      });
    }

    if (currSelect) {
      currSelect.addEventListener('change', updateDepositBtnLabel);
    }

    methodTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        methodTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const method = tab.getAttribute('data-method');
        if (method === 'upi') {
          if (cardSection) cardSection.style.display = 'none';
          if (upiSection) upiSection.style.display = 'block';
        } else {
          if (cardSection) cardSection.style.display = 'block';
          if (upiSection) upiSection.style.display = 'none';
        }
      });
    });

    if (testCardBtn) {
      testCardBtn.addEventListener('click', () => {
        document.getElementById('checkout-card-num').value = '4242 •••• •••• 4242';
        document.getElementById('checkout-card-exp').value = '12/28';
        document.getElementById('checkout-card-cvc').value = '888';
        showToast('Test Card Filled', 'Stripe standard test card credentials applied', 'info', 2000);
      });
    }

    if (executeBtn) {
      executeBtn.addEventListener('click', executeRealPaymentDeposit);
    }
  }

  function updateDepositBtnLabel() {
    const amtInput = document.getElementById('deposit-amount-input');
    const currSelect = document.getElementById('deposit-currency-select');
    const btnAmount = document.getElementById('deposit-btn-amount');
    if (amtInput && currSelect && btnAmount) {
      const amt = parseFloat(amtInput.value) || 0;
      const curr = currSelect.value;
      const symbol = curr === 'INR' ? '₹' : '$';
      btnAmount.textContent = `${symbol}${amt.toFixed(2)} ${curr}`;
    }
  }

  async function executeRealPaymentDeposit() {
    const amtInput = document.getElementById('deposit-amount-input');
    const currSelect = document.getElementById('deposit-currency-select');
    const executeBtn = document.getElementById('execute-deposit-btn');
    const modal = document.getElementById('deposit-checkout-modal');

    const amount = parseFloat(amtInput.value);
    const currency = currSelect.value;

    if (!amount || amount <= 0) {
      showToast('Validation Error', 'Please enter a valid deposit amount', 'error');
      return;
    }

    executeBtn.disabled = true;
    executeBtn.innerHTML = '<span class="spinner"></span> Contacting Payment Gateway...';

    try {
      // Step 1: Create Checkout Intent
      const intent = await request('/payments/checkout/create-intent', {
        method: 'POST',
        body: { amount, currency, payment_method: 'card' }
      });

      executeBtn.innerHTML = '<span class="spinner"></span> Authorizing & Settling Funds...';

      // Step 2: Confirm Payment on Ledger
      const confirmation = await request('/payments/checkout/confirm', {
        method: 'POST',
        body: {
          amount,
          currency,
          reference: intent.reference,
          payment_method: 'Visa •••• 4242 (Stripe Sandbox Verified)',
          gateway_txn_id: intent.intent_id
        }
      });

      if (modal) modal.classList.remove('open');

      showToast(
        'Payment Successful!',
        `Successfully added ${amount.toFixed(2)} ${confirmation.currency} to your account. Receipt emailed!`,
        'success',
        6000
      );

      // Trigger custom event so page balance updates automatically
      window.dispatchEvent(new CustomEvent('vayora:deposit_settled', { detail: confirmation }));

    } catch (err) {
      showToast('Payment Failed', err.message, 'error');
    } finally {
      executeBtn.disabled = false;
      updateDepositBtnLabel();
    }
  }

  // --- 3D TILT PHYSICS ENGINE (CLEAN NO-OP) ---
  function init3DTilt() {
    // Disabled in favor of clean simple light/dark theme
  }

  // --- DYNAMIC RIPPLE CLICK ENGINE ---
  function initRipples() {
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn, .quick-action-card, .demo-btn-pill, .timeframe-btn');
      if (!btn) return;

      const rect = btn.getBoundingClientRect();
      const circle = document.createElement('span');
      const diameter = Math.max(rect.width, rect.height);
      const radius = diameter / 2;

      circle.style.width = circle.style.height = `${diameter}px`;
      circle.style.left = `${e.clientX - rect.left - radius}px`;
      circle.style.top = `${e.clientY - rect.top - radius}px`;
      circle.classList.add('ripple-effect');

      const existingRipple = btn.querySelector('.ripple-effect');
      if (existingRipple) existingRipple.remove();

      btn.appendChild(circle);
      setTimeout(() => circle.remove(), 600);
    });
  }

  // --- AMBIENT AURORA BACKGROUND INJECTOR (CLEAN NO-OP) ---
  function injectAuroraBackground() {
    // Disabled in favor of clean simple light/dark theme
  }

  // --- LIVE CRYPTO TICKER MARQUEE SIMULATION ---
  function initTickerSimulation() {
    const tickerTrack = document.querySelector('.ticker-marquee-track');
    if (!tickerTrack) return;

    // Simulate subtle live price movements every 6 seconds
    setInterval(() => {
      const priceBadges = tickerTrack.querySelectorAll('[data-price-symbol]');
      if (!priceBadges.length) return;

      const randomBadge = priceBadges[Math.floor(Math.random() * priceBadges.length)];
      const currentPrice = parseFloat(randomBadge.getAttribute('data-price-val') || '0');
      if (!currentPrice) return;

      const isUp = Math.random() > 0.45;
      const deltaPercent = (Math.random() * 0.4 + 0.05) / 100;
      const newPrice = isUp ? currentPrice * (1 + deltaPercent) : currentPrice * (1 - deltaPercent);

      randomBadge.setAttribute('data-price-val', newPrice.toFixed(2));
      randomBadge.textContent = `$${newPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

      randomBadge.classList.remove('price-tick-up', 'price-tick-down');
      void randomBadge.offsetWidth; // Trigger reflow
      randomBadge.classList.add(isUp ? 'price-tick-up' : 'price-tick-down');
    }, 5000);
  }

  // --- INITIALIZE SHELL ---
  function initShell(activePage) {
    // Initialize Theme Switcher (Simple Light / Dark Mode)
    initTheme();
    initRipples();
    initTickerSimulation();

    const user = getCurrentUser();
    if (!user) {
      const path = window.location.pathname;
      if (!path.includes('login.html') && !path.includes('register.html') && !path.endsWith('/') && !path.includes('index.html')) {
        window.location.href = '/login.html';
        return;
      }
    }

    if (user) {
      const nameEls = document.querySelectorAll('.dynamic-user-name');
      nameEls.forEach(el => el.textContent = user.name);

      const emailEls = document.querySelectorAll('.dynamic-user-email');
      emailEls.forEach(el => el.textContent = user.email);

      const avatarEls = document.querySelectorAll('.avatar-sphere');
      avatarEls.forEach(el => {
        el.textContent = user.name.charAt(0).toUpperCase();
      });

      // Mount Real-Time Presence Indicator and Connect WebSocket
      renderPresencePill();
      initRealtimePresence();
    }

    // Highlight current navigation link
    if (activePage) {
      const links = document.querySelectorAll('.nav-link');
      links.forEach(l => {
        if (l.getAttribute('data-page') === activePage) {
          l.classList.add('active');
        } else {
          l.classList.remove('active');
        }
      });
    }

    // Mobile menu toggle
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.querySelector('.app-sidebar');
    if (mobileBtn && sidebar) {
      mobileBtn.addEventListener('click', () => {
        sidebar.classList.toggle('mobile-open');
      });
    }
    updateSoundToggleUI();
  }

  // Pre-initialize theme immediately upon script and DOM loading
  if (typeof document !== 'undefined') {
    const savedTheme = localStorage.getItem('vayora_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    document.addEventListener('DOMContentLoaded', () => {
      initTheme();
      initRipples();
      updateSoundToggleUI();
    });
  }

  let _cachedLiveRate = 94.76;
  let _lastLiveRateFetch = 0;

  async function getLiveRate() {
    const now = Date.now();
    if (now - _lastLiveRateFetch < 8000) {
      return _cachedLiveRate;
    }
    try {
      const data = await request('/convert/rate');
      if (data && data.rate) {
        _cachedLiveRate = parseFloat(data.rate);
        _lastLiveRateFetch = now;
      }
    } catch (e) {}
    return _cachedLiveRate;
  }

  return {
    get API_BASE() { return getApiBase(); },
    getAppName,
    getBackendUrl,
    getApiBase,
    setBackendUrl,
    getToken,
    setToken,
    getCurrentUser,
    setCurrentUser,
    logout,
    request,
    getLiveRate,
    showToast,
    animateValue,
    formatCurrencyINR,
    formatCurrencyUSD,
    formatDate,
    formatDateTime,
    formatDateOnly,
    formatTimeOnly,
    parseDate,
    switchDemoUser,
    initShell,
    initTheme,
    toggleTheme,
    init3DTilt,
    initRipples,
    injectAuroraBackground,
    openDepositModal,
    playSound,
    toggleSound
  };
})();

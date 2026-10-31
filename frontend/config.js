/**
 * VAYORA Frontend Runtime Configuration Bridge
 * Sets window.__ENV__ with APP_NAME and BACKEND_URL for the frontend.
 * Safely resolves the backend URL from localStorage, window.__ENV__, or hosting defaults.
 */
window.__ENV__ = window.__ENV__ || {};
window.__ENV__.APP_NAME = window.__ENV__.APP_NAME || "VAYORA - Your Digital Value, One Journey";

(function() {
  const isBrowser = typeof window !== 'undefined' && window.location;
  if (!isBrowser) {
    window.__ENV__.BACKEND_URL = "http://127.0.0.1:8000";
    return;
  }

  const hostname = window.location.hostname;
  const isFile = window.location.protocol === 'file:';
  const isLocal = isFile || hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0' || hostname.startsWith('192.168.') || hostname.startsWith('10.') || hostname === '';

  if (isLocal) {
    // In local development, clean any stale cloud URLs
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem('VAYORA_BACKEND_URL');
      if (stored && (stored.includes('vercel.app') || stored.includes('onrender.com'))) {
        localStorage.removeItem('VAYORA_BACKEND_URL');
      }
    }
    const localHost = (hostname && hostname !== '') ? hostname : '127.0.0.1';
    window.__ENV__.BACKEND_URL = `http://${localHost}:8000`;
    return;
  }

  // In production (Vercel / Cloud)
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem('VAYORA_BACKEND_URL');
    if (stored && (stored.includes('127.0.0.1') || stored.includes('localhost') || stored.includes('onrender.com'))) {
      localStorage.removeItem('VAYORA_BACKEND_URL');
    }
  }

  const savedUrl = typeof localStorage !== 'undefined' ? localStorage.getItem('VAYORA_BACKEND_URL') : null;
  if (savedUrl) {
    window.__ENV__.BACKEND_URL = savedUrl;
  } else {
    // In production unified deployments, backend is hosted on the same origin (window.location.origin)
    window.__ENV__.BACKEND_URL = (typeof window !== 'undefined' && window.location && window.location.origin)
      ? window.location.origin
      : "http://127.0.0.1:8000";
  }
})();

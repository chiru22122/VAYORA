/**
 * VAYORA Frontend Runtime Configuration Bridge
 * Sets window.__ENV__ with APP_NAME and BACKEND_URL for the frontend.
 * Safely resolves the backend URL from localStorage, window.__ENV__, or hosting defaults.
 */
window.__ENV__ = window.__ENV__ || {};
window.__ENV__.APP_NAME = window.__ENV__.APP_NAME || "VAYORA - Your Digital Value, One Journey";

(function() {
  const isVercel = typeof window !== 'undefined' && (
    window.location.hostname.endsWith('.vercel.app') ||
    (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' && window.location.port !== '8000')
  );
  
  const savedUrl = typeof localStorage !== 'undefined' ? localStorage.getItem('VAYORA_BACKEND_URL') : null;
  
  if (savedUrl) {
    window.__ENV__.BACKEND_URL = savedUrl;
  } else if (!window.__ENV__.BACKEND_URL) {
    if (isVercel) {
      // Default placeholder pointing to your Render web service.
      // Update this value with your actual Render URL (e.g. from Render dashboard),
      // or set it in the browser console via: localStorage.setItem('VAYORA_BACKEND_URL', 'https://your-service.onrender.com')
      window.__ENV__.BACKEND_URL = "https://vayora-backend.onrender.com";
    } else {
      window.__ENV__.BACKEND_URL = "http://127.0.0.1:8000";
    }
  }
})();

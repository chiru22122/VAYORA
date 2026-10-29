/**
 * VAYORA Frontend Runtime Configuration Bridge
 * Sets window.__ENV__ with APP_NAME and BACKEND_URL for the frontend.
 * This can also be customized directly or overridden via frontend/.env.
 */
window.__ENV__ = window.__ENV__ || {};
window.__ENV__.APP_NAME = window.__ENV__.APP_NAME || "VAYORA - Your Digital Value, One Journey";
window.__ENV__.BACKEND_URL = window.__ENV__.BACKEND_URL || "http://127.0.0.1:8000";

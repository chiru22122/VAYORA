/**
 * VAYORA SECURITY CENTER LOGIC
 * Manages device sessions, audit logs, backup recovery codes, and password changes.
 */

document.addEventListener('DOMContentLoaded', async () => {
  VAYORA.initShell('security');

  const securityScoreEl = document.getElementById('security-score-display');
  const emailVerifiedStatusEl = document.getElementById('sec-email-verified-status');
  const sessionsTbody = document.getElementById('sec-sessions-tbody');
  const loginHistoryTbody = document.getElementById('sec-login-history-tbody');
  const logoutAllBtn = document.getElementById('sec-logout-all-btn');
  const genRecoveryBtn = document.getElementById('sec-generate-recovery-btn');
  const recoveryCodesContainer = document.getElementById('recovery-codes-box');
  const passwordForm = document.getElementById('sec-password-form');

  try {
    await Promise.all([
      loadSecurityOverview(),
      loadActiveSessions(),
      loadLoginHistory()
    ]);

    if (logoutAllBtn) {
      logoutAllBtn.addEventListener('click', handleLogoutAllDevices);
    }

    if (genRecoveryBtn) {
      genRecoveryBtn.addEventListener('click', handleGenerateRecoveryCodes);
    }

    if (passwordForm) {
      passwordForm.addEventListener('submit', handleChangePassword);
    }

  } catch (err) {
    console.error('Security center error:', err);
  }

  async function loadSecurityOverview() {
    const sec = await VAYORA.request('/security');
    if (!sec) return;

    if (securityScoreEl) {
      securityScoreEl.textContent = `${sec.security_score}%`;
      securityScoreEl.style.color = sec.security_score >= 80 ? 'var(--neon-emerald)' : 'var(--neon-amber)';
    }

    if (emailVerifiedStatusEl) {
      if (sec.email_verified) {
        emailVerifiedStatusEl.innerHTML = '<span class="status-pill status-completed">Verified ✓</span>';
      } else {
        emailVerifiedStatusEl.innerHTML = '<span class="status-pill status-pending">Unverified</span>';
      }
    }
  }

  async function loadActiveSessions() {
    if (!sessionsTbody) return;
    const sessions = await VAYORA.request('/security/sessions');
    if (!sessions || sessions.length === 0) {
      sessionsTbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--text-muted);">No active sessions found.</td></tr>';
      return;
    }

    sessionsTbody.innerHTML = sessions.map(s => `
      <tr>
        <td style="font-weight: 600; color: var(--text-primary);">${s.device}</td>
        <td style="font-family: var(--font-mono); color: var(--text-secondary);">${s.ip_address}</td>
        <td><span class="status-pill status-active">ACTIVE</span></td>
        <td style="text-align: right;">
          <button class="btn btn-secondary btn-sm" onclick="revokeSession(${s.session_id})">Revoke</button>
        </td>
      </tr>
    `).join('');
  }

  async function loadLoginHistory() {
    if (!loginHistoryTbody) return;
    const history = await VAYORA.request('/security/login-history');
    if (!history || history.length === 0) {
      loginHistoryTbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--text-muted);">No login history records.</td></tr>';
      return;
    }

    loginHistoryTbody.innerHTML = history.slice(0, 10).map(h => `
      <tr>
        <td>${VAYORA.formatDate(h.created_at)}</td>
        <td>${h.device}</td>
        <td style="font-family: var(--font-mono);">${h.ip_address}</td>
        <td>
          <span class="status-pill ${h.success ? 'status-completed' : 'status-failed'}">
            ${h.success ? 'Success' : 'Failed'}
          </span>
        </td>
      </tr>
    `).join('');
  }

  window.revokeSession = async function(sessionId) {
    try {
      await VAYORA.request(`/security/sessions/${sessionId}/revoke`, { method: 'POST' });
      VAYORA.showToast('Session Revoked', 'Device disconnected successfully', 'success');
      await loadActiveSessions();
    } catch (e) {
      VAYORA.showToast('Error', e.message, 'error');
    }
  };

  async function handleLogoutAllDevices() {
    try {
      const res = await VAYORA.request('/security/logout-all', { method: 'POST' });
      VAYORA.showToast('Success', res.message, 'success');
      await loadActiveSessions();
    } catch (e) {
      VAYORA.showToast('Error', e.message, 'error');
    }
  }

  async function handleGenerateRecoveryCodes() {
    try {
      const res = await VAYORA.request('/security/recovery-codes', { method: 'POST' });
      if (recoveryCodesContainer && res.codes) {
        recoveryCodesContainer.style.display = 'block';
        const grid = document.getElementById('recovery-codes-grid');
        if (grid) {
          grid.innerHTML = res.codes.map(c => `
            <div style="background: rgba(255,255,255,0.05); padding: 8px 12px; border-radius: 6px; font-family: var(--font-mono); font-weight: 700; color: var(--neon-emerald); letter-spacing: 1px;">
              ${c}
            </div>
          `).join('');
        }
      }
      VAYORA.showToast('Recovery Codes Ready', 'New backup recovery codes generated', 'success');
      await loadSecurityOverview();
    } catch (e) {
      VAYORA.showToast('Error', e.message, 'error');
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    const oldP = document.getElementById('sec-old-pass').value;
    const newP = document.getElementById('sec-new-pass').value;

    if (!oldP || !newP) {
      VAYORA.showToast('Error', 'Please fill in both password fields', 'error');
      return;
    }

    try {
      const res = await VAYORA.request('/security/change-password', {
        method: 'POST',
        body: { old_password: oldP, new_password: newP }
      });
      VAYORA.showToast('Password Changed', res.message, 'success');
      passwordForm.reset();
    } catch (err) {
      VAYORA.showToast('Error', err.message, 'error');
    }
  }
});

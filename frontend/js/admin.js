/**
 * VAYORA ADMIN PORTAL CONTROLLER
 * Real-time network statistics, live user presence monitoring,
 * user balance audits, and ledger monitoring.
 */

document.addEventListener('DOMContentLoaded', async () => {
  VAYORA.initShell('admin');

  const user = VAYORA.getCurrentUser();
  if (user && user.role !== 'admin') {
    // Show non-admin warning banner
    const alertBox = document.getElementById('admin-access-warning');
    if (alertBox) {
      alertBox.style.display = 'flex';
    }
  }

  try {
    await Promise.all([
      loadPlatformStatistics(),
      loadRealtimeUsers(),
      loadAllUsers(),
      loadAllTransactions(),
      loadSecurityEvents()
    ]);
  } catch (err) {
    console.warn('Admin portal fetch:', err);
    VAYORA.showToast('Admin Mode', 'Loaded in simulated administration preview', 'info');
  }

  // Real-time presence listener
  window.addEventListener('vayora:presence_update', (e) => {
    loadRealtimeUsers(e.detail);
  });

  // Auto-refresh presence every 4 seconds
  setInterval(loadRealtimeUsers, 4000);

  async function loadPlatformStatistics() {
    try {
      const stats = await VAYORA.request('/admin/statistics');
      if (!stats) return;

      const totalUsersEl = document.getElementById('admin-stat-total-users');
      const activeUsersEl = document.getElementById('admin-stat-active-users');
      const totalValEl = document.getElementById('admin-stat-total-val');
      const totalTxEl = document.getElementById('admin-stat-total-tx');
      const completedTxEl = document.getElementById('admin-stat-completed-tx');

      if (totalUsersEl) totalUsersEl.textContent = stats.total_users;
      if (activeUsersEl) activeUsersEl.textContent = stats.active_users;
      if (totalValEl) totalValEl.textContent = `$${stats.total_wallet_value_usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
      if (totalTxEl) totalTxEl.textContent = stats.total_transactions;
      if (completedTxEl) completedTxEl.textContent = stats.completed_transactions;
    } catch (e) {
      console.warn('Admin stats error', e);
    }
  }

  async function loadRealtimeUsers(presenceData = null) {
    const tbody = document.getElementById('admin-realtime-users-tbody');
    const statOnlineNow = document.getElementById('admin-stat-online-now');
    if (!tbody) return;

    let users = [];
    let count = 0;

    if (presenceData) {
      users = presenceData.users || [];
      count = presenceData.count !== undefined ? presenceData.count : users.length;
    } else {
      try {
        const res = await VAYORA.request('/user/presence/online');
        users = res.online_users || [];
        count = res.online_count !== undefined ? res.online_count : users.length;
      } catch (e) {
        // fallback
      }
    }

    if (statOnlineNow) statOnlineNow.textContent = count;

    if (!users || users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 18px;">No users currently online.</td></tr>';
      return;
    }

    tbody.innerHTML = users.map(u => `
      <tr>
        <td>
          <div style="font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 8px;">
            <div style="width: 24px; height: 24px; border-radius: 50%; background: ${u.avatar_color || '#00f59b'}; color: #000; font-weight: 800; font-size: 0.7rem; display: flex; align-items: center; justify-content: center;">
              ${u.name.charAt(0).toUpperCase()}
            </div>
            <span>${u.name}</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted); margin-left: 32px;">${u.email}</div>
        </td>
        <td>
          <span class="status-pill ${u.status === 'ONLINE' ? 'status-completed' : 'status-pending'}" style="display: inline-flex; align-items: center; gap: 6px;">
            <span class="status-pulse-dot" style="width: 6px; height: 6px; background: ${u.status === 'ONLINE' ? 'var(--neon-emerald)' : 'var(--neon-amber)'};"></span>
            ${u.status}
          </span>
        </td>
        <td>
          <span class="status-pill ${u.role === 'admin' ? 'status-active' : 'status-completed'}">${u.role}</span>
        </td>
        <td>
          <span style="font-family: var(--font-mono); color: var(--neon-cyan); font-size: 0.8rem;">
            /${u.current_page || 'dashboard'}
          </span>
        </td>
        <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-secondary);">
          ${u.ip_address}
        </td>
        <td style="font-size: 0.78rem; color: var(--text-muted);">
          ${u.device || 'Web Browser'}
        </td>
        <td style="font-size: 0.78rem; color: var(--text-secondary);">
          ${u.last_active_seconds_ago <= 3 ? 'Just now' : `${u.last_active_seconds_ago}s ago`}
        </td>
      </tr>
    `).join('');
  }

  async function loadAllUsers() {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;

    try {
      const users = await VAYORA.request('/admin/users');
      if (!users || users.length === 0) return;

      tbody.innerHTML = users.map(u => `
        <tr>
          <td>
            <div style="font-weight: 700; color: var(--text-primary);">${u.name}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${u.email}</div>
          </td>
          <td>
            <span class="status-pill ${u.role === 'admin' ? 'status-active' : 'status-completed'}">${u.role}</span>
          </td>
          <td>
            <div style="font-family: var(--font-mono); color: var(--neon-cyan); font-size: 0.8rem;">
              ${u.wallet_address ? u.wallet_address.slice(0, 10) + '...' + u.wallet_address.slice(-6) : 'N/A'}
            </div>
          </td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--text-primary);">
            $${u.total_usd_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </td>
          <td style="font-family: var(--font-mono); color: var(--neon-emerald);">
            ₹${u.inr_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </td>
          <td>
            <span class="status-pill ${u.email_verified ? 'status-completed' : 'status-pending'}">
              ${u.email_verified ? 'VERIFIED' : 'PENDING'}
            </span>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.warn('Admin users load error', e);
    }
  }

  async function loadAllTransactions() {
    const tbody = document.getElementById('admin-tx-tbody');
    if (!tbody) return;

    try {
      const txs = await VAYORA.request('/admin/transactions');
      if (!txs || txs.length === 0) return;

      tbody.innerHTML = txs.slice(0, 15).map(tx => `
        <tr>
          <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${tx.reference_id}</td>
          <td><span class="status-pill status-active">${tx.type}</span></td>
          <td style="font-size: 0.8rem; color: var(--text-secondary);">${tx.sender || 'System'}</td>
          <td style="font-size: 0.8rem; color: var(--text-secondary);">${tx.receiver || 'System'}</td>
          <td style="font-family: var(--font-mono); font-weight: 700;">${Math.abs(tx.amount)} ${tx.asset_symbol || ''}</td>
          <td><span class="status-pill status-completed">${tx.status}</span></td>
        </tr>
      `).join('');
    } catch (e) {
      console.warn('Admin tx error', e);
    }
  }

  async function loadSecurityEvents() {
    const tbody = document.getElementById('admin-events-tbody');
    if (!tbody) return;

    try {
      const events = await VAYORA.request('/admin/security-events');
      if (!events || events.length === 0) return;

      tbody.innerHTML = events.slice(0, 10).map(ev => `
        <tr>
          <td>${VAYORA.formatDate(ev.created_at)}</td>
          <td>${ev.device}</td>
          <td style="font-family: var(--font-mono);">${ev.ip_address}</td>
          <td><span class="status-pill ${ev.success ? 'status-completed' : 'status-failed'}">${ev.reason}</span></td>
        </tr>
      `).join('');
    } catch (e) {
      console.warn('Admin events error', e);
    }
  }
});

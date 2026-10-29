/**
 * VAYORA WALLET VIEW CONTROLLER
 * Loads all active assets and user balances from the database.
 * Supports realtime balance refresh on deposits and incoming payments.
 */

document.addEventListener('DOMContentLoaded', async () => {
  VAYORA.initShell('wallet');

  const totalInrEl = document.getElementById('wallet-total-inr');
  const totalUsdEl = document.getElementById('wallet-total-usd');
  const inrPoolEl = document.getElementById('wallet-inr-pool');
  const addressEl = document.getElementById('wallet-address-txt');
  const copyBtn = document.getElementById('wallet-copy-addr-btn');
  const assetsGrid = document.getElementById('wallet-assets-grid');

  await loadWalletData();

  // Real-time automatic refresh upon deposit or incoming payment
  window.addEventListener('vayora:deposit_settled', loadWalletData);
  window.addEventListener('vayora:payment_received', loadWalletData);

  async function loadWalletData() {
    try {
      const wallet = await VAYORA.request('/wallet');
      if (!wallet) return;

      if (totalInrEl) totalInrEl.textContent = VAYORA.formatCurrencyINR(wallet.total_inr_value);
      if (totalUsdEl) totalUsdEl.textContent = VAYORA.formatCurrencyUSD(wallet.total_usd_value);
      if (inrPoolEl) inrPoolEl.textContent = VAYORA.formatCurrencyINR(wallet.inr_balance);
      if (addressEl) addressEl.textContent = wallet.address;

      if (copyBtn) {
        copyBtn.onclick = () => {
          navigator.clipboard.writeText(wallet.address);
          VAYORA.showToast('Copied', 'Wallet address copied to clipboard', 'info');
        };
      }

      if (assetsGrid && wallet.balances) {
        assetsGrid.innerHTML = wallet.balances.map(b => {
          const depAddr = b.deposit_address || wallet.address || '';
          const truncatedAddr = depAddr.length > 20 ? `${depAddr.slice(0, 10)}...${depAddr.slice(-6)}` : depAddr;
          return `
          <div class="asset-card">
            <div>
              <div class="asset-card-top">
                <div style="display: flex; align-items: center; gap: 12px;">
                  <div class="asset-icon-box">${b.symbol.slice(0, 3)}</div>
                  <div>
                    <div style="font-family: var(--font-display); font-size: 1.15rem; font-weight: 700; color: var(--text-primary);">${b.name}</div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">${b.network}</div>
                  </div>
                </div>
                <div class="asset-price-tag">$${b.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
              </div>

              <div class="asset-balance-block">
                <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 2px;">Holdings</div>
                <div class="asset-balance-amount">${b.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })} ${b.symbol}</div>
                <div class="asset-balance-fiat">
                  ≈ $${b.usd_value.toLocaleString(undefined, { minimumFractionDigits: 2 })} USD (${VAYORA.formatCurrencyINR(b.inr_value)})
                </div>
              </div>

              <!-- Dedicated Token Address Row -->
              <div style="margin-top: 12px; background: rgba(0, 0, 0, 0.25); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 8px 10px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                <div style="font-size: 0.72rem; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  <span style="color: var(--neon-cyan); font-weight: 700;">${b.symbol} Address:</span>
                  <span style="font-family: var(--font-mono); color: var(--text-secondary); margin-left: 4px;">${truncatedAddr}</span>
                </div>
                <button type="button" onclick="navigator.clipboard.writeText('${depAddr}'); VAYORA.showToast('Copied', '${b.symbol} address copied to clipboard', 'info');" style="background: none; border: none; color: var(--neon-emerald); cursor: pointer; font-size: 0.85rem;" title="Copy ${b.symbol} Address">📋</button>
              </div>
            </div>

            <div class="asset-card-actions" style="margin-top: 14px;">
              <a href="/receive.html?token=${b.symbol}" class="btn btn-outline-emerald btn-sm">Receive (QR)</a>
              <a href="/send.html?token=${b.symbol}" class="btn btn-secondary btn-sm">Send</a>
              <button onclick="VAYORA.openDepositModal('${b.symbol}')" class="btn btn-primary btn-sm">Add Funds</button>
            </div>
          </div>
        `;
        }).join('');
      }

    } catch (err) {
      console.warn('Wallet load error:', err);
    }
  }
});

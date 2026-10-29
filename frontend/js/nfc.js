/**
 * VAYORA NFC CONTACTLESS PROTOTYPE
 * Interactive POS terminal demonstration with animated radar waves and step authorization.
 */

document.addEventListener('DOMContentLoaded', async () => {
  VAYORA.initShell('nfc');

  const nfcTarget = document.getElementById('nfc-tap-target');
  const nfcStatusText = document.getElementById('nfc-status-label');
  const merchantSelect = document.getElementById('nfc-merchant-select');
  const customAmountInput = document.getElementById('nfc-amount-input');
  const assetSelect = document.getElementById('nfc-asset-select');
  const nfcReceiptBox = document.getElementById('nfc-receipt-box');

  const merchantPresets = {
    'Starbucks Digital Terminal': 4.85,
    'Uber Global Rides': 14.20,
    'Blue Tokai Coffee Roasters': 5.50,
    'Apple Store Fifth Ave': 89.00
  };

  if (merchantSelect && customAmountInput) {
    merchantSelect.addEventListener('change', () => {
      const selected = merchantSelect.value;
      if (merchantPresets[selected]) {
        customAmountInput.value = merchantPresets[selected];
      }
    });
  }

  if (nfcTarget) {
    nfcTarget.addEventListener('click', handleNFCTap);
  }

  async function handleNFCTap() {
    const merchant = merchantSelect ? merchantSelect.value : 'Starbucks Digital Terminal';
    const amount = parseFloat(customAmountInput.value) || 5.00;
    const asset = assetSelect ? assetSelect.value : 'USDT';

    // Step 1: Tap Detected
    const pad = document.getElementById('nfc-radar-container');
    if (pad) pad.classList.add('nfc-active');

    nfcStatusText.innerHTML = '<span style="color: var(--neon-cyan);">TAP DETECTED! Reading Secure Element...</span>';
    nfcTarget.style.pointerEvents = 'none';

    // Simulated short delay for device handshake
    await new Promise(r => setTimeout(r, 700));

    // Step 2: Merchant & Amount Identified
    nfcStatusText.innerHTML = `<span style="color: var(--text-primary);">Authorizing $${amount.toFixed(2)} at ${merchant}...</span>`;
    await new Promise(r => setTimeout(r, 600));

    // Step 3: Call Backend Database
    try {
      const res = await VAYORA.request('/nfc/payment', {
        method: 'POST',
        body: {
          merchant: merchant,
          amount: amount,
          asset_symbol: asset
        }
      });

      // Step 4: Success confirmation
      nfcStatusText.innerHTML = '<span style="color: var(--neon-emerald); font-weight: 700;">PAYMENT APPROVED ✓</span>';
      VAYORA.showToast('NFC Tap Approved', `$${amount.toFixed(2)} ${asset} authorized at ${merchant}`, 'success');

      if (nfcReceiptBox) {
        nfcReceiptBox.style.display = 'block';
        document.getElementById('nfc-receipt-merchant').textContent = res.merchant;
        document.getElementById('nfc-receipt-amount').textContent = `$${res.amount.toFixed(2)} ${res.asset_symbol}`;
        document.getElementById('nfc-receipt-ref').textContent = res.reference;
        document.getElementById('nfc-receipt-time').textContent = VAYORA.formatDate(res.created_at);
      }
    } catch (err) {
      nfcStatusText.innerHTML = `<span style="color: var(--neon-pink);">${err.message}</span>`;
      VAYORA.showToast('NFC Declined', err.message, 'error');
    } finally {
      setTimeout(() => {
        if (pad) pad.classList.remove('nfc-active');
        nfcTarget.style.pointerEvents = 'auto';
      }, 1500);
    }
  }
});

/**
 * VAYORA INSTANT SWAP LOGIC
 * Quotes real-time rates, calculates fees, and executes atomic token swaps.
 */

document.addEventListener('DOMContentLoaded', async () => {
  VAYORA.initShell('swap');

  let walletBalances = [];
  const fromSelect = document.getElementById('swap-from-select');
  const toSelect = document.getElementById('swap-to-select');
  const fromAmountInput = document.getElementById('swap-from-amount');
  const toAmountOutput = document.getElementById('swap-to-amount');
  const rateDisplay = document.getElementById('swap-rate-display');
  const feeDisplay = document.getElementById('swap-fee-display');
  const switchBtn = document.getElementById('swap-switch-direction-btn');
  const executeBtn = document.getElementById('swap-execute-btn');
  const availEl = document.getElementById('swap-avail-balance');

  try {
    const wallet = await VAYORA.request('/wallet');
    walletBalances = wallet.balances;

    populateSelects();
    updateAvailable();
    await fetchQuote();

    // Event listeners
    fromSelect.addEventListener('change', () => {
      updateAvailable();
      fetchQuote();
    });

    toSelect.addEventListener('change', fetchQuote);

    let debounceTimer;
    fromAmountInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(fetchQuote, 250);
    });

    if (switchBtn) {
      switchBtn.addEventListener('click', () => {
        const temp = fromSelect.value;
        fromSelect.value = toSelect.value;
        toSelect.value = temp;
        switchBtn.classList.add('swap-switch-active');
        setTimeout(() => switchBtn.classList.remove('swap-switch-active'), 400);
        updateAvailable();
        fetchQuote();
      });
    }

    if (executeBtn) {
      executeBtn.addEventListener('click', handleSwapExecution);
    }

  } catch (err) {
    console.error('Failed to init swap:', err);
    VAYORA.showToast('Error', 'Unable to initialize swap quotes', 'error');
  }

  function populateSelects() {
    if (!fromSelect || !toSelect) return;

    fromSelect.innerHTML = walletBalances.map(b => `
      <option value="${b.symbol}">${b.symbol}</option>
    `).join('');

    toSelect.innerHTML = walletBalances.map(b => `
      <option value="${b.symbol}">${b.symbol}</option>
    `).join('');

    fromSelect.value = 'USDT';
    toSelect.value = 'USDC';
  }

  function updateAvailable() {
    const sym = fromSelect.value;
    const b = walletBalances.find(item => item.symbol === sym);
    if (availEl && b) {
      availEl.textContent = `${b.available_amount.toFixed(4)} ${b.symbol}`;
    }
  }

  async function fetchQuote() {
    const fromSymbol = fromSelect.value;
    const toSymbol = toSelect.value;
    const fromAmt = parseFloat(fromAmountInput.value) || 0;

    if (fromSymbol === toSymbol) {
      toAmountOutput.value = fromAmt.toString();
      rateDisplay.textContent = `1 ${fromSymbol} = 1.00 ${toSymbol}`;
      feeDisplay.textContent = '0.00';
      return;
    }

    if (fromAmt <= 0) {
      toAmountOutput.value = '0.00';
      rateDisplay.textContent = '--';
      feeDisplay.textContent = '--';
      return;
    }

    try {
      const q = await VAYORA.request(`/swap/quote?from_symbol=${fromSymbol}&to_symbol=${toSymbol}&from_amount=${fromAmt}`);
      if (q) {
        toAmountOutput.value = q.to_amount.toFixed(6);
        rateDisplay.textContent = `1 ${fromSymbol} ≈ ${q.rate.toFixed(4)} ${toSymbol}`;
        feeDisplay.textContent = `${q.fee.toFixed(6)} ${toSymbol} (0.1% demo fee)`;
      }
    } catch (e) {
      console.warn('Quote error:', e);
    }
  }

  async function handleSwapExecution() {
    const fromSymbol = fromSelect.value;
    const toSymbol = toSelect.value;
    const fromAmt = parseFloat(fromAmountInput.value);

    if (fromSymbol === toSymbol) {
      VAYORA.showToast('Invalid Pair', 'Cannot swap an asset for itself', 'error');
      return;
    }

    if (!fromAmt || fromAmt <= 0) {
      VAYORA.showToast('Invalid Amount', 'Please specify a positive swap amount', 'error');
      return;
    }

    const b = walletBalances.find(item => item.symbol === fromSymbol);
    if (b && fromAmt > b.available_amount) {
      VAYORA.showToast('Insufficient Balance', `You only have ${b.available_amount.toFixed(4)} ${fromSymbol}`, 'error');
      return;
    }

    executeBtn.disabled = true;
    executeBtn.innerHTML = '<span class="spinner"></span> Swapping on Ledger...';

    try {
      const res = await VAYORA.request('/swap', {
        method: 'POST',
        body: {
          from_symbol: fromSymbol,
          to_symbol: toSymbol,
          from_amount: fromAmt
        }
      });

      VAYORA.showToast('Swap Completed!', `Converted ${fromAmt} ${fromSymbol} to ${res.to_amount} ${toSymbol}`, 'success');

      // Refresh balances
      const updatedWallet = await VAYORA.request('/wallet');
      walletBalances = updatedWallet.balances;
      updateAvailable();
      fromAmountInput.value = '';
      toAmountOutput.value = '';

    } catch (err) {
      VAYORA.showToast('Swap Failed', err.message, 'error');
    } finally {
      executeBtn.disabled = false;
      executeBtn.innerHTML = 'Confirm Instant Swap';
    }
  }
});

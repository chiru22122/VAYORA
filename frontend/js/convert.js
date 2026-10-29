/**
 * VAYORA REAL-TIME LIVE USDT -> INR CONVERSION & CONVERSATIONAL ENGINE
 * High-speed live rate polling, auto-recalculating spot quotes,
 * and conversational AI assistant integration.
 */

// Global state variables
let currentLiveRate = 94.76;
let currentUsdtAvail = 0;
let currentInrBalance = 0;
let ratePollTimer = null;
let lastRateVal = null;

// Expose switchConvertView and helpers to global scope
window.switchConvertView = function(view) {
  const instantView = document.getElementById('view-instant');
  const chatView = document.getElementById('view-chat');
  const tabInstant = document.getElementById('tab-btn-instant');
  const tabChat = document.getElementById('tab-btn-chat');

  if (view === 'chat') {
    if (instantView) instantView.style.display = 'none';
    if (chatView) chatView.style.display = 'block';
    if (tabInstant) tabInstant.classList.remove('active');
    if (tabChat) tabChat.classList.add('active');
    const input = document.getElementById('chat-user-input');
    if (input) input.focus();
    scrollChatToBottom();
  } else {
    if (chatView) chatView.style.display = 'none';
    if (instantView) instantView.style.display = 'block';
    if (tabChat) tabChat.classList.remove('active');
    if (tabInstant) tabInstant.classList.add('active');
  }
};

window.applyQuickPct = function(pct) {
  const usdtInput = document.getElementById('convert-usdt-amount');
  if (!usdtInput) return;
  const amt = Math.floor(currentUsdtAvail * pct * 100) / 100;
  usdtInput.value = amt > 0 ? amt : '';
  recalcLiveConversion();
};

window.sendChatPrompt = function(promptText) {
  const input = document.getElementById('chat-user-input');
  if (input) {
    input.value = promptText;
  }
  handleChatSubmit();
};

function scrollChatToBottom() {
  const container = document.getElementById('chat-messages-container');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

function recalcLiveConversion() {
  const usdtInput = document.getElementById('convert-usdt-amount');
  const inrOutput = document.getElementById('convert-inr-output');
  const receiptLiveRate = document.getElementById('receipt-live-rate');
  const receiptNetInr = document.getElementById('receipt-net-inr');

  const val = parseFloat(usdtInput ? usdtInput.value : 0) || 0;
  const inr = val * currentLiveRate;

  if (inrOutput) {
    inrOutput.value = val > 0 ? `₹${inr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '';
  }
  if (receiptLiveRate) {
    receiptLiveRate.textContent = `₹${currentLiveRate.toFixed(2)} per 1.00 USDT`;
  }
  if (receiptNetInr) {
    receiptNetInr.textContent = `₹${inr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  VAYORA.initShell('convert');

  const usdtInput = document.getElementById('convert-usdt-amount');
  const availUsdtEl = document.getElementById('convert-avail-usdt');
  const convertBtn = document.getElementById('convert-submit-btn');
  const maxUsdtBtn = document.getElementById('convert-max-btn');
  const refreshRateBtn = document.getElementById('manual-refresh-rate-btn');

  // Bank withdrawal elements
  const inrBalanceDisplay = document.getElementById('withdraw-inr-balance');
  const withdrawAmountInput = document.getElementById('withdraw-amount-input');
  const withdrawBankName = document.getElementById('withdraw-bank-name');
  const withdrawAccNo = document.getElementById('withdraw-account-number');
  const withdrawIfsc = document.getElementById('withdraw-ifsc-code');
  const withdrawSubmitBtn = document.getElementById('withdraw-submit-btn');

  try {
    // Initial data fetch
    await fetchLiveRate(false);
    await loadBalances();
    await loadConversionHistory();

    // Event listeners
    if (usdtInput) {
      usdtInput.addEventListener('input', recalcLiveConversion);
    }

    if (maxUsdtBtn) {
      maxUsdtBtn.addEventListener('click', () => {
        if (usdtInput) {
          usdtInput.value = currentUsdtAvail;
          recalcLiveConversion();
        }
      });
    }

    if (convertBtn) {
      convertBtn.addEventListener('click', handleConvert);
    }

    if (withdrawSubmitBtn) {
      withdrawSubmitBtn.addEventListener('click', handleBankWithdrawal);
    }

    if (refreshRateBtn) {
      refreshRateBtn.addEventListener('click', async () => {
        refreshRateBtn.classList.add('spinning');
        await fetchLiveRate(true);
        setTimeout(() => refreshRateBtn.classList.remove('spinning'), 600);
      });
    }

    // Set recurring live rate polling (every 8 seconds)
    if (ratePollTimer) clearInterval(ratePollTimer);
    ratePollTimer = setInterval(() => {
      fetchLiveRate(false);
    }, 8000);

  } catch (err) {
    console.error('Convert init error:', err);
  }

  // --- LIVE RATE FETCHER ---
  async function fetchLiveRate(forceRefresh = false) {
    try {
      const url = `/convert/rate${forceRefresh ? '?refresh=true' : ''}`;
      const data = await VAYORA.request(url);
      if (!data || !data.rate) return;

      const newRate = parseFloat(data.rate);
      const heroVal = document.getElementById('live-rate-hero');
      const deltaPill = document.getElementById('live-rate-delta');
      const oracleTag = document.getElementById('oracle-source-tag');
      const highVal = document.getElementById('meta-24h-high');
      const lowVal = document.getElementById('meta-24h-low');
      const lastRefresh = document.getElementById('meta-last-refresh');
      const badgePill = document.getElementById('badge-live-rate-pill');
      const chatPill = document.getElementById('chat-live-rate-pill');

      // Detect flash direction
      if (lastRateVal !== null && heroVal) {
        if (newRate > lastRateVal) {
          heroVal.classList.add('flash-up');
          setTimeout(() => heroVal.classList.remove('flash-up'), 700);
        } else if (newRate < lastRateVal) {
          heroVal.classList.add('flash-down');
          setTimeout(() => heroVal.classList.remove('flash-down'), 700);
        }
      }
      lastRateVal = newRate;
      currentLiveRate = newRate;

      // Update Hero display
      if (heroVal) heroVal.textContent = `1 USDT = ₹${newRate.toFixed(2)}`;

      if (deltaPill) {
        const delta = data.change_24h || 0;
        const isPos = delta >= 0;
        deltaPill.className = `rate-delta-pill ${isPos ? 'positive' : 'negative'}`;
        deltaPill.textContent = `${isPos ? '▲ +' : '▼ '}${delta.toFixed(2)}%`;
      }

      if (oracleTag) oracleTag.textContent = data.source || 'Live Oracle Feed';
      if (highVal) highVal.textContent = `₹${(data.high_24h || newRate * 1.005).toFixed(2)}`;
      if (lowVal) lowVal.textContent = `₹${(data.low_24h || newRate * 0.995).toFixed(2)}`;
      if (lastRefresh) {
        const d = new Date();
        lastRefresh.textContent = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
      }

      if (badgePill) badgePill.textContent = `Live: 1 USDT = ₹${newRate.toFixed(2)}`;
      if (chatPill) chatPill.textContent = `1 USDT = ₹${newRate.toFixed(2)}`;

      // Update live calculated outputs
      recalcLiveConversion();
    } catch (e) {
      console.warn('Live rate fetch warning:', e);
    }
  }

  // --- BALANCE LOADER ---
  async function loadBalances() {
    try {
      const wallet = await VAYORA.request('/wallet');
      if (!wallet) return;

      const usdt = wallet.balances.find(b => b.symbol === 'USDT');
      currentUsdtAvail = usdt ? usdt.available_amount : 0;
      currentInrBalance = wallet.inr_balance || 0;

      if (availUsdtEl) availUsdtEl.textContent = `${currentUsdtAvail.toFixed(2)} USDT`;
      if (inrBalanceDisplay) inrBalanceDisplay.textContent = VAYORA.formatCurrencyINR(currentInrBalance);
    } catch (e) {
      console.error('Balance load error:', e);
    }
  }

  // --- HANDLE CONVERT ---
  async function handleConvert() {
    const amt = parseFloat(usdtInput.value);
    if (!amt || amt <= 0) {
      VAYORA.showToast('Validation Error', 'Enter a valid USDT conversion amount', 'error');
      return;
    }

    if (amt > currentUsdtAvail) {
      VAYORA.showToast('Insufficient USDT', `Available: ${currentUsdtAvail.toFixed(2)} USDT`, 'error');
      return;
    }

    convertBtn.disabled = true;
    convertBtn.innerHTML = '<span class="spinner"></span> Executing Live Conversion...';

    try {
      const res = await VAYORA.request('/convert/usdt-to-inr', {
        method: 'POST',
        body: {
          usdt_amount: amt,
          rate: currentLiveRate
        }
      });

      VAYORA.showToast(
        'Conversion Executed!',
        `Converted ${amt.toFixed(2)} USDT → ₹${res.inr_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} INR @ ₹${res.exchange_rate.toFixed(2)}/USDT`,
        'success'
      );

      usdtInput.value = '';
      recalcLiveConversion();

      await loadBalances();
      await loadConversionHistory();
    } catch (err) {
      VAYORA.showToast('Conversion Failed', err.message, 'error');
    } finally {
      convertBtn.disabled = false;
      convertBtn.innerHTML = 'Convert to INR Balance';
    }
  }

  // --- HANDLE BANK WITHDRAWAL ---
  async function handleBankWithdrawal() {
    const amt = parseFloat(withdrawAmountInput.value);
    const bank = withdrawBankName.value.trim();
    const acc = withdrawAccNo.value.trim();
    const ifsc = withdrawIfsc.value.trim();

    if (!amt || amt <= 0) {
      VAYORA.showToast('Validation Error', 'Enter a valid withdrawal amount', 'error');
      return;
    }

    if (amt > currentInrBalance) {
      VAYORA.showToast('Insufficient Balance', `Available INR balance: ₹${currentInrBalance.toLocaleString()}`, 'error');
      return;
    }

    if (!bank || !acc || !ifsc) {
      VAYORA.showToast('Validation Error', 'Please complete all bank beneficiary fields', 'error');
      return;
    }

    withdrawSubmitBtn.disabled = true;
    withdrawSubmitBtn.innerHTML = '<span class="spinner"></span> Dispatching IMPS Transfer...';

    try {
      const res = await VAYORA.request('/bank/withdraw', {
        method: 'POST',
        body: {
          amount: amt,
          bank_name: bank,
          account_number: acc,
          ifsc_code: ifsc
        }
      });

      VAYORA.showToast('Withdrawal Dispatched!', `₹${res.amount.toLocaleString()} transferred to ${res.bank_name}. Ref: ${res.bank_reference}`, 'success');

      withdrawAmountInput.value = '';
      await loadBalances();
    } catch (err) {
      VAYORA.showToast('Withdrawal Failed', err.message, 'error');
    } finally {
      withdrawSubmitBtn.disabled = false;
      withdrawSubmitBtn.innerHTML = 'Initiate Bank Payout';
    }
  }

  // Expose loadConversionHistory to window
  window.loadConversionHistory = async function() {
    const historyTbody = document.getElementById('conversion-history-tbody');
    if (!historyTbody) return;
    try {
      const history = await VAYORA.request('/convert/history');
      if (!history || history.length === 0) {
        historyTbody.innerHTML = `
          <tr>
            <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">
              No conversion history recorded yet.
            </td>
          </tr>
        `;
        return;
      }

      historyTbody.innerHTML = history.map(item => `
        <tr>
          <td>${VAYORA.formatDate(item.created_at)}</td>
          <td style="font-family: var(--font-mono); font-weight: 600;">${item.asset_amount.toFixed(2)} USDT</td>
          <td style="font-family: var(--font-mono); color: var(--neon-cyan); font-weight: 600;">
            ₹${item.exchange_rate.toFixed(2)}
          </td>
          <td style="font-family: var(--font-mono); color: var(--neon-emerald); font-weight: 700;">
            ₹${item.inr_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </td>
          <td><span class="status-pill status-completed">COMPLETED</span></td>
        </tr>
      `).join('');
    } catch (e) {
      console.warn('History load error:', e);
    }
  };

  // Expose loadBalances to window
  window.reloadConvertBalances = loadBalances;
});

// ==========================================================================
// CONVERSATIONAL AI ASSISTANT CLIENT ENGINE
// ==========================================================================

window.handleChatSubmit = async function(e) {
  if (e && e.preventDefault) e.preventDefault();

  const input = document.getElementById('chat-user-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const container = document.getElementById('chat-messages-container');
  if (!input || !container) return;

  const msg = input.value.trim();
  if (!msg) return;

  // Append user message bubble
  appendChatBubble('user', escapeHtml(msg));
  input.value = '';

  // Show typing indicator
  const typingId = 'typing-' + Date.now();
  appendTypingIndicator(typingId);
  scrollChatToBottom();

  if (sendBtn) sendBtn.disabled = true;

  try {
    const res = await VAYORA.request('/convert/chat', {
      method: 'POST',
      body: { message: msg }
    });

    removeElement(typingId);

    if (res && res.reply) {
      let botHtml = formatMarkdown(res.reply);

      // If action is CONVERT_CONFIRM, embed interactive conversion deal card!
      if (res.action === 'CONVERT_CONFIRM' && res.usdt_amount && res.inr_amount) {
        const dealId = 'deal-' + Date.now();
        botHtml += `
          <div class="conversation-deal-card" id="${dealId}">
            <div class="deal-card-header">⚡ One-Click Instant Conversion</div>
            <div class="deal-amounts">
              <span class="deal-usdt">${res.usdt_amount.toFixed(2)} USDT</span>
              <span class="deal-arrow">➔</span>
              <span class="deal-inr">₹${res.inr_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} INR</span>
            </div>
            <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between;">
              <span>Rate: ₹${(res.rate || currentLiveRate).toFixed(2)}/USDT</span>
              <span style="color: var(--neon-emerald);">Zero Fee Policy</span>
            </div>
            <button type="button" class="deal-confirm-btn" onclick="executeDealConversion(${res.usdt_amount}, ${res.rate || currentLiveRate}, '${dealId}')">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              <span>Confirm & Convert ${res.usdt_amount.toFixed(2)} USDT</span>
            </button>
          </div>
        `;
      }

      appendChatBubble('bot', botHtml);

      // Update suggested chips if provided
      if (res.suggested_questions && res.suggested_questions.length > 0) {
        updateSuggestedChips(res.suggested_questions);
      }
    }
  } catch (err) {
    removeElement(typingId);
    appendChatBubble('bot', `⚠️ Could not complete request: ${err.message}`);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    scrollChatToBottom();
  }
};

window.executeDealConversion = async function(usdtAmt, quoteRate, dealCardId) {
  const card = document.getElementById(dealCardId);
  const btn = card ? card.querySelector('.deal-confirm-btn') : null;
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Converting...';
  }

  try {
    const res = await VAYORA.request('/convert/usdt-to-inr', {
      method: 'POST',
      body: {
        usdt_amount: usdtAmt,
        rate: quoteRate
      }
    });

    if (btn) {
      btn.style.background = '#10b981';
      btn.innerHTML = '✓ Converted Successfully';
    }

    VAYORA.showToast(
      'Conversion Successful!',
      `Converted ${usdtAmt.toFixed(2)} USDT into ₹${res.inr_amount.toLocaleString()} INR`,
      'success'
    );

    // Append congratulatory bot message
    appendChatBubble('bot', `🎉 **Success!** Your **${usdtAmt.toFixed(2)} USDT** has been converted into **₹${res.inr_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} INR** at **₹${res.exchange_rate.toFixed(2)}/USDT**.\n\nYour domestic INR balance is ready for bank withdrawal!`);

    if (window.reloadConvertBalances) window.reloadConvertBalances();
    if (window.loadConversionHistory) window.loadConversionHistory();

  } catch (err) {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = 'Retry Conversion';
    }
    VAYORA.showToast('Conversion Failed', err.message, 'error');
  } finally {
    scrollChatToBottom();
  }
};

function appendChatBubble(sender, htmlContent) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;
  bubble.innerHTML = htmlContent;
  container.appendChild(bubble);
  scrollChatToBottom();
}

function appendTypingIndicator(id) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble bot';
  bubble.id = id;
  bubble.innerHTML = `
    <div class="typing-dots">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  container.appendChild(bubble);
}

function removeElement(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function updateSuggestedChips(questions) {
  const row = document.getElementById('chat-suggestions-row');
  if (!row) return;

  row.innerHTML = questions.map(q => `
    <button type="button" class="prompt-chip" onclick="sendChatPrompt('${escapeHtml(q)}')">${escapeHtml(q)}</button>
  `).join('');
}

function escapeHtml(str) {
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

function formatMarkdown(text) {
  let out = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/• /g, '&bull; ')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
  return out;
}

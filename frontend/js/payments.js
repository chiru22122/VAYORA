/**
 * VAYORA MULTI-TOKEN PAYMENTS ENGINE: SEND & RECEIVE
 * Supports distinct receiving and sending addresses across different tokens:
 * USDT (TRC-20), USDC (ERC-20), BTC (Native SegWit), ETH (ERC-20), SOL (Solana SPL), INR (UPI)
 */

document.addEventListener('DOMContentLoaded', async () => {
  const isSendPage = window.location.pathname.includes('send.html');
  const isReceivePage = window.location.pathname.includes('receive.html');

  if (isSendPage) {
    VAYORA.initShell('send');
    await initSendPage();
  } else if (isReceivePage) {
    VAYORA.initShell('receive');
    await initReceivePage();
  }

  // =========================================================================
  // LIGHTWEIGHT STANDALONE QR CODE SVG GENERATOR
  // =========================================================================
  function renderQRCodeSvg(container, text) {
    if (!container) return;
    container.innerHTML = '';

    // Deterministic pseudo-random QR matrix representation based on text hash
    // Generates standard 29x29 or 25x25 QR matrix with authentic position finder patterns
    const size = 25;
    const matrix = Array.from({ length: size }, () => Array(size).fill(false));

    // Helper: Mark 7x7 Finder Pattern with 1px quiet border
    function addFinderPattern(startX, startY) {
      for (let y = 0; y < 7; y++) {
        for (let x = 0; x < 7; x++) {
          if (
            y === 0 || y === 6 || x === 0 || x === 6 || // Outer 7x7 border
            (y >= 2 && y <= 4 && x >= 2 && x <= 4)      // Inner 3x3 solid box
          ) {
            matrix[startY + y][startX + x] = true;
          }
        }
      }
    }

    // Add 3 standard corner position finder patterns
    addFinderPattern(0, 0);          // Top-Left
    addFinderPattern(size - 7, 0);   // Top-Right
    addFinderPattern(0, size - 7);   // Bottom-Left

    // Timing patterns
    for (let i = 8; i < size - 8; i++) {
      if (i % 2 === 0) {
        matrix[6][i] = true;
        matrix[i][6] = true;
      }
    }

    // Hash text into bytes to fill data payload deterministically
    let hash = 0;
    const bytes = [];
    for (let i = 0; i < text.length; i++) {
      const code = text.charCodeAt(i);
      hash = ((hash << 5) - hash) + code;
      hash |= 0;
      bytes.push(code);
    }

    let byteIdx = 0;
    let bitIdx = 0;
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        // Skip finder pattern zones
        const inTopLeft = (x < 8 && y < 8);
        const inTopRight = (x >= size - 8 && y < 8);
        const inBottomLeft = (x < 8 && y >= size - 8);
        const inCenterLogo = (x >= 9 && x <= 15 && y >= 9 && y <= 15); // Reserved for logo badge

        if (inTopLeft || inTopRight || inBottomLeft || inCenterLogo) {
          continue;
        }

        // Data bit from string
        const currentByte = bytes[byteIdx % bytes.length] || 0x5a;
        const bit = ((currentByte >> (bitIdx % 8)) & 1) === 1;
        const pseudoMask = ((x + y) % 3 === 0);
        matrix[y][x] = bit ^ pseudoMask;

        bitIdx++;
        if (bitIdx % 8 === 0) byteIdx++;
      }
    }

    // Build SVG
    const svgNs = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.style.shapeRendering = "crispEdges";

    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        if (matrix[y][x]) {
          const rect = document.createElementNS(svgNs, "rect");
          rect.setAttribute("x", x);
          rect.setAttribute("y", y);
          rect.setAttribute("width", 1);
          rect.setAttribute("height", 1);
          rect.setAttribute("fill", "#06070a");
          svg.appendChild(rect);
        }
      }
    }

    container.appendChild(svg);
  }

  // =========================================================================
  // SEND PAGE ENGINE
  // =========================================================================
  async function initSendPage() {
    let balances = [];
    let tokenAddresses = {};
    const assetSelect = document.getElementById('send-asset-select');
    const availBalEl = document.getElementById('send-available-bal');
    const amountInput = document.getElementById('send-amount-input');
    const maxBtn = document.getElementById('send-max-btn');
    const recipientInput = document.getElementById('send-recipient-input');
    const noteInput = document.getElementById('send-note-input');
    const sendBtn = document.getElementById('send-submit-btn');
    const calcFiatEl = document.getElementById('send-calc-fiat');

    // Sender Token Address Elements
    const senderAddrValEl = document.getElementById('sender-token-address-val');
    const senderNetLabelEl = document.getElementById('sender-network-label');
    const copySenderAddrBtn = document.getElementById('copy-sender-addr-btn');

    // Quick Fill Demo Helpers
    const fillDemoReceiverBtn = document.getElementById('fill-demo-receiver-btn');
    const fillDemoEmailBtn = document.getElementById('fill-demo-receiver-email-btn');

    // Pre-known demo addresses map for demo recipient helper
    const DEMO_RECEIVER_ADDRESSES = {
      "USDT": "TY8B2uReceiverUSDT88rMNqQ4x9yW3z6S2",
      "USDC": "0x2222B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A1",
      "BTC":  "bc1qrecv88b9a0z1y2x3v4u5t6s7r8q9p0o1m2k3",
      "ETH":  "0x34A991E47B02D338FA8291410651A827B1390A77",
      "SOL":  "SolReceiverVa2222222222222222222222222222222",
      "INR":  "receiver.vayora@icici"
    };

    const DEMO_SENDER_ADDRESSES = {
      "USDT": "TX7A1vSenderUSDT99qKLmP3w8xV2y5R1",
      "USDC": "0x1111A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8",
      "BTC":  "bc1qsender42a8z9w0y1x2v3u4t5s6r7q8p9o0m1",
      "ETH":  "0x71C94B2E8F19D382A0F8372651B44390C12E7B90",
      "SOL":  "SolSenderVa11111111111111111111111111111111",
      "INR":  "sender.vayora@icici"
    };

    try {
      const wallet = await VAYORA.request('/wallet');
      balances = wallet.balances || [];
      tokenAddresses = wallet.token_addresses || {};

      // Check URL query param for default token selection e.g. /send.html?token=BTC
      const urlParams = new URLSearchParams(window.location.search);
      const urlToken = urlParams.get('token');

      if (assetSelect) {
        assetSelect.innerHTML = balances.map(b => `
          <option value="${b.symbol}" data-avail="${b.available_amount}" data-price="${b.price}" data-net="${b.network}" ${urlToken && urlToken.toUpperCase() === b.symbol ? 'selected' : ''}>
            ${b.symbol} - ${b.name} (${b.available_amount.toFixed(4)} Available)
          </option>
        `).join('');

        updateAvailAndSenderDisplay();

        assetSelect.addEventListener('change', () => {
          updateAvailAndSenderDisplay();
          calculateFiat();
        });
      }
    } catch (err) {
      console.error(err);
      VAYORA.showToast('Wallet Error', 'Failed to load asset balances and token addresses', 'error');
    }

    function getSelectedAsset() {
      if (!assetSelect) return null;
      const sym = assetSelect.value;
      return balances.find(b => b.symbol === sym) || null;
    }

    function updateAvailAndSenderDisplay() {
      const selected = getSelectedAsset();
      if (!selected) return;

      if (availBalEl) {
        availBalEl.textContent = `${selected.available_amount.toFixed(4)} ${selected.symbol}`;
      }

      // Display sender's dedicated address for this token
      const myTokenAddr = selected.deposit_address || tokenAddresses[selected.symbol] || 'Generating...';
      if (senderAddrValEl) {
        senderAddrValEl.textContent = myTokenAddr;
      }
      if (senderNetLabelEl) {
        senderNetLabelEl.textContent = selected.network || selected.symbol;
      }

      // Update placeholder dynamically based on token format
      if (recipientInput) {
        if (selected.symbol === 'BTC') {
          recipientInput.placeholder = "Enter recipient's Bitcoin SegWit address (bc1q...) or email";
        } else if (selected.symbol === 'USDT') {
          recipientInput.placeholder = "Enter recipient's USDT TRC-20 address (TX...) or email";
        } else if (selected.symbol === 'SOL') {
          recipientInput.placeholder = "Enter recipient's Solana address (Sol...) or email";
        } else if (selected.symbol === 'ETH' || selected.symbol === 'USDC') {
          recipientInput.placeholder = "Enter recipient's ERC-20 address (0x...) or email";
        } else if (selected.symbol === 'INR') {
          recipientInput.placeholder = "Enter recipient's UPI ID (user@vayora) or email";
        } else {
          recipientInput.placeholder = `Enter recipient ${selected.symbol} address or email`;
        }
      }
    }

    // Copy Sender Address Button
    if (copySenderAddrBtn) {
      copySenderAddrBtn.addEventListener('click', () => {
        const selected = getSelectedAsset();
        const addr = senderAddrValEl ? senderAddrValEl.textContent : '';
        if (addr && addr !== 'Loading address...') {
          navigator.clipboard.writeText(addr);
          VAYORA.showToast('Address Copied', `Your ${selected ? selected.symbol : ''} address copied to clipboard`, 'info');
        }
      });
    }

    // Quick Fill Recipient Demo Helpers
    if (fillDemoReceiverBtn) {
      fillDemoReceiverBtn.addEventListener('click', () => {
        const selected = getSelectedAsset();
        const sym = selected ? selected.symbol : 'USDT';
        const currentUser = VAYORA.getCurrentUser();
        const isUserSender = (!currentUser || currentUser.email === 'sender@vayora.demo');

        const targetMap = isUserSender ? DEMO_RECEIVER_ADDRESSES : DEMO_SENDER_ADDRESSES;
        const targetAddr = targetMap[sym] || targetMap['USDT'];

        if (recipientInput) {
          recipientInput.value = targetAddr;
          recipientInput.dispatchEvent(new Event('input'));
          VAYORA.showToast('Demo Address Filled', `Filled counterparty ${sym} address: ${targetAddr.slice(0, 10)}...`, 'info');
        }
      });
    }

    if (fillDemoEmailBtn) {
      fillDemoEmailBtn.addEventListener('click', () => {
        const currentUser = VAYORA.getCurrentUser();
        const isUserSender = (!currentUser || currentUser.email === 'sender@vayora.demo');
        const targetEmail = isUserSender ? 'receiver@vayora.demo' : 'sender@vayora.demo';

        if (recipientInput) {
          recipientInput.value = targetEmail;
          recipientInput.dispatchEvent(new Event('input'));
          VAYORA.showToast('Demo Recipient Filled', `Filled ${targetEmail}`, 'info');
        }
      });
    }

    async function calculateFiat() {
      const selected = getSelectedAsset();
      const amt = parseFloat(amountInput.value) || 0;
      if (selected && calcFiatEl) {
        const usd = amt * selected.price;
        const rate = await VAYORA.getLiveRate();
        const inr = usd * rate;
        calcFiatEl.textContent = `≈ $${usd.toFixed(2)} USD (₹${inr.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} INR @ ₹${rate.toFixed(2)}/USDT)`;
      }
    }

    if (amountInput) {
      amountInput.addEventListener('input', calculateFiat);
    }

    if (maxBtn) {
      maxBtn.addEventListener('click', () => {
        const selected = getSelectedAsset();
        if (selected) {
          amountInput.value = selected.available_amount;
          calculateFiat();
        }
      });
    }

    // Real-Time Recipient Online Presence Detection
    const recipientBadge = document.getElementById('recipient-online-badge');
    let recipientDebounce = null;

    if (recipientInput && recipientBadge) {
      recipientInput.addEventListener('input', () => {
        clearTimeout(recipientDebounce);
        recipientDebounce = setTimeout(checkRecipientPresence, 300);
      });
    }

    async function checkRecipientPresence() {
      if (!recipientInput || !recipientBadge) return;
      const target = recipientInput.value.trim().toLowerCase();
      if (!target || target.length < 3) {
        recipientBadge.style.display = 'none';
        return;
      }

      try {
        const res = await VAYORA.request('/user/presence/online');
        const onlineList = res.online_users || [];
        const isOnline = onlineList.some(u => u.email.toLowerCase() === target);

        if (isOnline) {
          recipientBadge.innerHTML = '🟢 Online right now';
          recipientBadge.style.color = 'var(--neon-emerald)';
          recipientBadge.style.display = 'inline-block';
        } else {
          recipientBadge.innerHTML = '⚪ Offline';
          recipientBadge.style.color = 'var(--text-muted)';
          recipientBadge.style.display = 'inline-block';
        }
      } catch (e) {
        recipientBadge.style.display = 'none';
      }
    }

    // Submit handler
    if (sendBtn) {
      sendBtn.addEventListener('click', async (e) => {
        e.preventDefault();

        const recipient = recipientInput.value.trim();
        const assetSymbol = assetSelect.value;
        const amount = parseFloat(amountInput.value);
        const note = noteInput ? noteInput.value.trim() : null;

        if (!recipient) {
          VAYORA.showToast('Validation Error', 'Please enter a recipient email or address', 'error');
          recipientInput.focus();
          return;
        }

        if (!amount || amount <= 0) {
          VAYORA.showToast('Validation Error', 'Please enter a valid positive amount', 'error');
          amountInput.focus();
          return;
        }

        const selected = getSelectedAsset();
        if (selected && amount > selected.available_amount) {
          VAYORA.showToast('Insufficient Balance', `Available: ${selected.available_amount.toFixed(4)} ${selected.symbol}`, 'error');
          return;
        }

        // Trigger Confirm Modal
        openSendConfirmModal({
          recipient,
          assetSymbol,
          amount,
          note,
          price: selected ? selected.price : 1
        });
      });
    }

    function openSendConfirmModal(data) {
      const modal = document.getElementById('send-confirm-modal');
      if (!modal) {
        executeSend(data);
        return;
      }

      document.getElementById('modal-conf-amount').textContent = `${data.amount} ${data.assetSymbol}`;
      document.getElementById('modal-conf-recipient').textContent = data.recipient;
      document.getElementById('modal-conf-note').textContent = data.note || 'None';
      modal.classList.add('open');

      const confirmBtn = document.getElementById('modal-conf-btn');
      confirmBtn.onclick = async () => {
        modal.classList.remove('open');
        await executeSend(data);
      };
    }

    async function executeSend(data) {
      sendBtn.disabled = true;
      sendBtn.innerHTML = '<span class="spinner"></span> Processing on Ledger...';

      try {
        const res = await VAYORA.request('/payments/send', {
          method: 'POST',
          body: {
            recipient: data.recipient,
            asset_symbol: data.assetSymbol,
            amount: data.amount,
            note: data.note
          }
        });

        VAYORA.showToast('Transfer Dispatched', `Successfully sent ${data.amount} ${data.assetSymbol} to ${data.recipient}`, 'success');

        // Show Success Result with Token Addresses
        const successBox = document.getElementById('send-success-box');
        if (successBox) {
          successBox.style.display = 'block';
          document.getElementById('success-ref-id').textContent = res.reference;
          
          const sAddrEl = document.getElementById('success-sender-addr');
          const rAddrEl = document.getElementById('success-receiver-addr');
          if (sAddrEl) sAddrEl.textContent = res.sender_address || res.sender_email;
          if (rAddrEl) rAddrEl.textContent = res.receiver_address || res.receiver_email;
          
          document.getElementById('send-form-card').style.display = 'none';
        }

        // Re-fetch balance
        const updatedWallet = await VAYORA.request('/wallet');
        balances = updatedWallet.balances;
        updateAvailAndSenderDisplay();

      } catch (err) {
        VAYORA.showToast('Transfer Failed', err.message, 'error');
      } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = 'Send Payment Now';
      }
    }
  }

  // =========================================================================
  // RECEIVE PAGE ENGINE: DYNAMIC MULTI-TOKEN SELECTOR
  // =========================================================================
  async function initReceivePage() {
    let tokenList = [];
    let currentToken = "USDT";

    const tokenTabsContainer = document.getElementById('receive-token-tabs');
    const netPillEl = document.getElementById('receive-network-pill');
    const timeEl = document.getElementById('receive-settlement-time');
    const titleEl = document.getElementById('receive-card-title');
    const descEl = document.getElementById('receive-card-desc');
    const qrMountEl = document.getElementById('qr-code-mount');
    const qrCenterIconEl = document.getElementById('qr-center-icon');
    const addrLabelEl = document.getElementById('receive-address-label');
    const addrValEl = document.getElementById('receive-wallet-address');
    const userEmailEl = document.getElementById('receive-user-email');
    const copiedBadgeEl = document.getElementById('copied-badge');
    const copyAddrBtn = document.getElementById('copy-addr-btn');
    const shareAddrBtn = document.getElementById('share-addr-btn');
    const copyEmailBtn = document.getElementById('copy-email-btn');

    // Specs
    const specMinDep = document.getElementById('spec-min-deposit');
    const specConf = document.getElementById('spec-confirmations');
    const specFee = document.getElementById('spec-fee');
    const specStandard = document.getElementById('spec-standard');

    // Simulation elements
    const simBtn = document.getElementById('simulate-receive-btn');
    const simAmtEl = document.getElementById('sim-amt');
    const simSymEl = document.getElementById('sim-sym');

    // Simulation amounts per token
    const SIM_AMOUNTS = {
      "USDT": 25.00,
      "USDC": 25.00,
      "BTC": 0.005,
      "ETH": 0.05,
      "SOL": 0.50,
      "INR": 2500.00
    };

    const TOKEN_ICONS = {
      "USDT": "₮",
      "USDC": "$",
      "BTC": "₿",
      "ETH": "Ξ",
      "SOL": "◎",
      "INR": "₹"
    };

    try {
      // 1. Fetch all token addresses with metadata
      const res = await VAYORA.request('/wallet/addresses');
      tokenList = res || [];
      const user = VAYORA.getCurrentUser();

      if (userEmailEl && user) {
        userEmailEl.textContent = user.email;
      }

      // Check URL query param e.g. /receive.html?token=BTC
      const urlParams = new URLSearchParams(window.location.search);
      const urlToken = urlParams.get('token');
      if (urlToken && tokenList.some(t => t.symbol.toUpperCase() === urlToken.toUpperCase())) {
        currentToken = urlToken.toUpperCase();
      }

      // 2. Render Tabs
      renderTabs();

      // 3. Render Selected Token Details
      renderTokenDetails(currentToken);

      // Copy Address Handler
      if (copyAddrBtn) {
        copyAddrBtn.addEventListener('click', () => {
          const tokenData = tokenList.find(t => t.symbol === currentToken);
          if (tokenData && tokenData.address) {
            navigator.clipboard.writeText(tokenData.address);
            if (copiedBadgeEl) {
              copiedBadgeEl.style.display = 'inline';
              setTimeout(() => { copiedBadgeEl.style.display = 'none'; }, 2000);
            }
            VAYORA.showToast('Address Copied', `${tokenData.symbol} address copied to clipboard`, 'info');
          }
        });
      }

      // Share Address Handler
      if (shareAddrBtn) {
        shareAddrBtn.addEventListener('click', async () => {
          const tokenData = tokenList.find(t => t.symbol === currentToken);
          if (!tokenData) return;
          const shareText = `My VAYORA ${tokenData.symbol} (${tokenData.network}) Deposit Address:\n${tokenData.address}`;
          if (navigator.share) {
            try {
              await navigator.share({
                title: `VAYORA ${tokenData.symbol} Deposit Address`,
                text: shareText
              });
            } catch (e) {}
          } else {
            navigator.clipboard.writeText(shareText);
            VAYORA.showToast('Copied to Clipboard', 'Full deposit details ready to paste', 'info');
          }
        });
      }

      // Copy Email ID Handler
      if (copyEmailBtn && user) {
        copyEmailBtn.addEventListener('click', () => {
          navigator.clipboard.writeText(user.email);
          VAYORA.showToast('VAYORA ID Copied', user.email, 'info');
        });
      }

      // Simulation Incoming Transfer Handler
      if (simBtn) {
        simBtn.addEventListener('click', async () => {
          simBtn.disabled = true;
          simBtn.innerHTML = '<span class="spinner"></span> Simulating incoming transfer...';

          try {
            const amt = SIM_AMOUNTS[currentToken] || 25.00;
            const res = await VAYORA.request('/payments/receive', {
              method: 'POST',
              body: {
                sender_email: 'settlement@vayora.network',
                asset_symbol: currentToken,
                amount: amt,
                note: `Simulated external ${currentToken} network deposit`
              }
            });

            VAYORA.showToast(
              'Funds Received!',
              `+${amt} ${currentToken} credited to your ${currentToken} address (${res.receiver_address ? res.receiver_address.slice(0, 12) + '...' : ''})`,
              'success'
            );

            // Re-render button
            setTimeout(() => {
              simBtn.disabled = false;
              simBtn.innerHTML = `Simulate Incoming +<span id="sim-amt">${amt}</span> <span id="sim-sym">${currentToken}</span> Transfer`;
            }, 1000);

          } catch (err) {
            VAYORA.showToast('Simulation Failed', err.message, 'error');
            simBtn.disabled = false;
            const amt = SIM_AMOUNTS[currentToken] || 25.00;
            simBtn.innerHTML = `Simulate Incoming +<span id="sim-amt">${amt}</span> <span id="sim-sym">${currentToken}</span> Transfer`;
          }
        });
      }

    } catch (err) {
      console.error(err);
      VAYORA.showToast('Error', 'Unable to retrieve token deposit addresses', 'error');
    }

    function renderTabs() {
      if (!tokenTabsContainer) return;
      tokenTabsContainer.innerHTML = tokenList.map(t => `
        <button type="button" class="token-pill-btn ${t.symbol === currentToken ? 'active' : ''}" data-token="${t.symbol}">
          <span class="token-pill-icon">${TOKEN_ICONS[t.symbol] || '●'}</span>
          <span>${t.symbol}</span>
        </button>
      `).join('');

      // Add click listeners to tabs
      const tabBtns = tokenTabsContainer.querySelectorAll('.token-pill-btn');
      tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
          const sym = btn.getAttribute('data-token');
          if (sym && sym !== currentToken) {
            currentToken = sym;
            tabBtns.forEach(b => b.classList.toggle('active', b.getAttribute('data-token') === sym));
            renderTokenDetails(sym);
          }
        });
      });
    }

    function renderTokenDetails(symbol) {
      const token = tokenList.find(t => t.symbol === symbol);
      if (!token) return;

      if (netPillEl) netPillEl.textContent = token.network;
      if (timeEl) timeEl.textContent = token.avg_time || '< 30s Instant';
      if (titleEl) titleEl.textContent = `Receive ${token.name} (${token.symbol})`;
      if (descEl) descEl.textContent = `Send only ${token.symbol} to this address on the ${token.network}. Deposits credit automatically to your VAYORA vault.`;

      if (addrLabelEl) addrLabelEl.textContent = `Your Dedicated ${token.symbol} (${token.network}) Deposit Address`;
      if (addrValEl) addrValEl.textContent = token.address;

      // Update Center Icon on QR
      if (qrCenterIconEl) {
        qrCenterIconEl.textContent = TOKEN_ICONS[token.symbol] || token.symbol.slice(0, 1);
      }

      // Generate Crisp SVG QR Code
      const qrUri = token.qr_uri || token.address;
      renderQRCodeSvg(qrMountEl, qrUri);

      // Update Specifications
      if (specMinDep) specMinDep.textContent = token.min_deposit || `1.00 ${token.symbol}`;
      if (specConf) specConf.textContent = `${token.confirmations} ${token.confirmations === 1 ? 'Confirmation' : 'Confirmations'}`;
      if (specFee) specFee.textContent = token.fee || '0.00 VAYORA Network';
      if (specStandard) specStandard.textContent = token.standard || token.network;

      // Update Simulation Helper
      const amt = SIM_AMOUNTS[token.symbol] || 25.00;
      if (simAmtEl) simAmtEl.textContent = amt;
      if (simSymEl) simSymEl.textContent = token.symbol;
    }
  }
});

/**
 * VAYORA VIRTUAL CARD ENGINE
 * Interactive 3D tilt, card flip, freeze/unfreeze state, and online payment demo.
 */

document.addEventListener('DOMContentLoaded', async () => {
  VAYORA.initShell('card');

  const cardObject = document.getElementById('virtual-card-object');
  const cardScene = document.getElementById('card-scene-container');
  const flipBtn = document.getElementById('card-flip-btn');
  const freezeBtn = document.getElementById('card-freeze-toggle-btn');

  const cardholderNameEl = document.getElementById('card-cardholder-display');
  const cardNumberEl = document.getElementById('card-number-display');
  const cardExpiryEl = document.getElementById('card-expiry-display');
  const cardCvvEl = document.getElementById('card-cvv-display');
  const cardBalanceEl = document.getElementById('card-balance-display');
  const cardStatusBadge = document.getElementById('card-status-badge');

  let currentCard = null;

  try {
    await loadCardDetails();
    setup3DTilt();

    if (flipBtn && cardObject) {
      flipBtn.addEventListener('click', () => {
        cardObject.classList.toggle('is-flipped');
      });
      cardObject.addEventListener('click', (e) => {
        // Toggle flip on card click
        if (!e.target.closest('button')) {
          cardObject.classList.toggle('is-flipped');
        }
      });
    }

    if (freezeBtn) {
      freezeBtn.addEventListener('click', handleToggleFreeze);
    }

    // Demo merchant purchase simulation
    const payDemoBtn = document.getElementById('card-demo-pay-btn');
    if (payDemoBtn) {
      payDemoBtn.addEventListener('click', handleSimulatePurchase);
    }

  } catch (err) {
    console.error('Card init error:', err);
  }

  async function loadCardDetails() {
    currentCard = await VAYORA.request('/card');
    if (!currentCard) return;

    if (cardholderNameEl) cardholderNameEl.textContent = currentCard.cardholder_name;
    if (cardNumberEl) cardNumberEl.textContent = currentCard.masked_number;
    if (cardExpiryEl) cardExpiryEl.textContent = currentCard.expiry;
    if (cardCvvEl) cardCvvEl.textContent = currentCard.cvv;
    if (cardBalanceEl) cardBalanceEl.textContent = `$${currentCard.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

    updateStatusUI(currentCard.status);
  }

  function updateStatusUI(status) {
    if (!cardStatusBadge || !cardObject || !freezeBtn) return;

    if (status === 'FROZEN') {
      cardObject.classList.add('is-frozen');
      cardStatusBadge.className = 'status-pill status-frozen';
      cardStatusBadge.textContent = 'FROZEN';
      freezeBtn.textContent = 'Unfreeze Card';
      freezeBtn.className = 'btn btn-outline-emerald';
    } else {
      cardObject.classList.remove('is-frozen');
      cardStatusBadge.className = 'status-pill status-active';
      cardStatusBadge.textContent = 'ACTIVE';
      freezeBtn.textContent = 'Freeze Card';
      freezeBtn.className = 'btn btn-danger';
    }
  }

  async function handleToggleFreeze() {
    if (!currentCard) return;
    const shouldFreeze = currentCard.status === 'ACTIVE';

    freezeBtn.disabled = true;
    try {
      const updated = await VAYORA.request('/card/freeze', {
        method: 'POST',
        body: { freeze: shouldFreeze }
      });
      currentCard = updated;
      updateStatusUI(updated.status);
      VAYORA.showToast(
        shouldFreeze ? 'Card Frozen' : 'Card Activated',
        `Virtual card ending in ${updated.masked_number.slice(-4)} is now ${updated.status.toLowerCase()}.`,
        shouldFreeze ? 'error' : 'success'
      );
    } catch (err) {
      VAYORA.showToast('Error', err.message, 'error');
    } finally {
      freezeBtn.disabled = false;
    }
  }

  async function handleSimulatePurchase() {
    if (!currentCard) return;
    if (currentCard.status === 'FROZEN') {
      VAYORA.showToast('Declined', 'Card is frozen. Please unfreeze to transact.', 'error');
      return;
    }

    try {
      const res = await VAYORA.request('/card/simulate-payment', {
        method: 'POST',
        body: {
          merchant: 'Amazon Web Services (Cloud Hosting)',
          amount: 45.00
        }
      });
      VAYORA.showToast('Payment Approved', `$45.00 paid to AWS via ${currentCard.masked_number}`, 'success');
      await loadCardDetails();
    } catch (err) {
      VAYORA.showToast('Payment Declined', err.message, 'error');
    }
  }

  // 3D Tilt Effect on Mouse Move
  function setup3DTilt() {
    if (!cardScene || !cardObject) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    cardScene.addEventListener('mousemove', (e) => {
      const rect = cardScene.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      const rotateX = ((y - centerY) / centerY) * -12;
      const rotateY = ((x - centerX) / centerX) * 12;

      const isFlipped = cardObject.classList.contains('is-flipped');
      const baseRotationY = isFlipped ? 180 : 0;

      cardObject.style.transform = `rotateX(${rotateX}deg) rotateY(${baseRotationY + rotateY}deg)`;
    });

    cardScene.addEventListener('mouseleave', () => {
      const isFlipped = cardObject.classList.contains('is-flipped');
      cardObject.style.transform = isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)';
    });
  }
});

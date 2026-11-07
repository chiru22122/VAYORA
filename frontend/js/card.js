/**
 * VAYORA VIRTUAL CARD ENGINE
 * Interactive 3D tilt, card flip, freeze/unfreeze state, online payment demo,
 * and exclusive selectable virtual card editions (including Money Heist Dalí Edition).
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
  const cardTierBadge = document.getElementById('card-tier-badge');
  const currentThemePill = document.getElementById('current-theme-pill');
  const cardDisclaimerEl = document.getElementById('card-disclaimer-display');
  const daliWatermarkEl = document.querySelector('.card-watermark-dali');

  const themeCards = document.querySelectorAll('.theme-picker-card');

  let currentCard = null;

  const THEMES_CONFIG = {
    'MONEY HEIST': {
      className: 'theme-money-heist',
      tierLabel: 'LA RESISTENCIA',
      pillLabel: 'MONEY HEIST (DALI)',
      title: 'Money Heist (Dalí Edition)',
      disclaimer: 'O bella ciao, bella ciao. Authorized for simulated operations by the Professor & VAYORA Network.'
    },
    'BLACK OBSIDIAN': {
      className: 'theme-black-obsidian',
      tierLabel: 'BLACK OBSIDIAN',
      pillLabel: 'BLACK OBSIDIAN',
      title: 'Black Obsidian',
      disclaimer: 'This virtual card is issued for controlled academic prototyping by VAYORA Core.'
    },
    'ROYAL SAPPHIRE': {
      className: 'theme-royal-sapphire',
      tierLabel: 'ROYAL SAPPHIRE',
      pillLabel: 'ROYAL SAPPHIRE',
      title: 'Royal Sapphire',
      disclaimer: 'World Elite private virtual concierge card issued by VAYORA Global.'
    },
    'CYBER HOLOGRAPHIC': {
      className: 'theme-cyber-holographic',
      tierLabel: 'CYBER QUANTUM',
      pillLabel: 'CYBER HOLO',
      title: 'Cyber Holographic',
      disclaimer: 'Iridescent holographic zero-knowledge virtual asset card on VAYORA Layer 2.'
    },
    '24K GOLD': {
      className: 'theme-24k-gold',
      tierLabel: '24K SOVEREIGN',
      pillLabel: '24K GOLD',
      title: '24K Gold Sovereign',
      disclaimer: 'Bullion VIP reserve card authorized for high-velocity global settlement.'
    }
  };

  try {
    // Check initial cached theme from localStorage for instant render
    const initialCachedTheme = localStorage.getItem('vayora_card_theme') || 'BLACK OBSIDIAN';
    applyThemeUI(initialCachedTheme);

    await loadCardDetails();
    setup3DTilt();
    initThemePicker();

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

  function normalizeThemeKey(raw) {
    if (!raw) return 'BLACK OBSIDIAN';
    const s = raw.toString().toUpperCase();
    if (s.includes('HEIST') || s.includes('DALI') || s.includes('RESISTENCIA')) return 'MONEY HEIST';
    if (s.includes('SAPPHIRE')) return 'ROYAL SAPPHIRE';
    if (s.includes('HOLO') || s.includes('CYBER')) return 'CYBER HOLOGRAPHIC';
    if (s.includes('GOLD')) return '24K GOLD';
    return 'BLACK OBSIDIAN';
  }

  function applyThemeUI(rawKey) {
    const key = normalizeThemeKey(rawKey);
    const cfg = THEMES_CONFIG[key] || THEMES_CONFIG['BLACK OBSIDIAN'];

    if (cardObject) {
      // Remove all theme classes
      Object.values(THEMES_CONFIG).forEach(c => cardObject.classList.remove(c.className));
      cardObject.classList.add(cfg.className);
    }

    if (cardTierBadge) {
      cardTierBadge.textContent = cfg.tierLabel;
    }

    if (currentThemePill) {
      currentThemePill.textContent = cfg.pillLabel;
    }

    if (cardDisclaimerEl) {
      cardDisclaimerEl.textContent = cfg.disclaimer;
    }

    if (daliWatermarkEl) {
      daliWatermarkEl.style.display = (key === 'MONEY HEIST') ? 'block' : 'none';
    }

    // Update active highlight in theme gallery
    themeCards.forEach(card => {
      const cardTheme = normalizeThemeKey(card.getAttribute('data-theme'));
      if (cardTheme === key) {
        card.classList.add('active');
      } else {
        card.classList.remove('active');
      }
    });

    localStorage.setItem('vayora_card_theme', key);
  }

  function initThemePicker() {
    themeCards.forEach(card => {
      card.addEventListener('click', async () => {
        const selectedTheme = card.getAttribute('data-theme');
        if (!selectedTheme) return;

        const normKey = normalizeThemeKey(selectedTheme);
        applyThemeUI(normKey);

        // Tactile audio feedback
        if (typeof VAYORA.playSound === 'function') {
          VAYORA.playSound('coin');
        }

        // Morph animation flair
        if (cardObject) {
          cardObject.style.transition = 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
          cardObject.style.transform = 'scale(1.02) rotateY(10deg)';
          setTimeout(() => {
            cardObject.style.transform = '';
            setTimeout(() => {
              cardObject.style.transition = 'transform 0.5s ease';
            }, 300);
          }, 300);
        }

        const cfg = THEMES_CONFIG[normKey];
        VAYORA.showToast('Card Edition Selected', `${cfg.title} design applied.`, 'success');

        // Persist theme to database
        try {
          await VAYORA.request('/card/theme', {
            method: 'POST',
            body: { card_tier: normKey }
          });
          if (currentCard) {
            currentCard.card_tier = normKey;
          }
        } catch (e) {
          console.warn('Could not persist theme to server:', e);
        }
      });
    });
  }

  async function loadCardDetails() {
    currentCard = await VAYORA.request('/card');
    if (!currentCard) return;

    if (cardholderNameEl) cardholderNameEl.textContent = currentCard.cardholder_name;
    if (cardNumberEl) cardNumberEl.textContent = currentCard.masked_number;
    if (cardExpiryEl) cardExpiryEl.textContent = currentCard.expiry;
    if (cardCvvEl) cardCvvEl.textContent = currentCard.cvv;
    if (cardBalanceEl) cardBalanceEl.textContent = `$${currentCard.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

    if (currentCard.card_tier) {
      applyThemeUI(currentCard.card_tier);
    }

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
    // Enable 3D mousemove physics only on desktop devices with precision pointers
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

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

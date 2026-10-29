/**
 * VAYORA AUTHENTICATION CONTROLLER
 * Real Email Sign-In with 2-Step OTP, Registration, and Recovery.
 */

document.addEventListener('DOMContentLoaded', () => {
  const isLoginPage = window.location.pathname.includes('login.html');
  const isRegisterPage = window.location.pathname.includes('register.html');
  const isForgotPage = window.location.pathname.includes('forgot-password.html');

  // --- LOGIN WORKFLOW ---
  if (isLoginPage) {
    const loginForm = document.getElementById('login-form');
    const emailInput = document.getElementById('login-email');
    const passInput = document.getElementById('login-password');
    const require2FaCheck = document.getElementById('require-2fa-check');
    const submitBtn = document.getElementById('login-submit-btn');

    const demoContainer = document.getElementById('demo-credentials-container');
    const otpStepCard = document.getElementById('otp-step-card');
    const otpTargetEmail = document.getElementById('otp-target-email');
    const verifyLoginBtn = document.getElementById('verify-login-btn');
    const backToLoginBtn = document.getElementById('back-to-login-btn');
    const resendLoginOtpBtn = document.getElementById('resend-login-otp-btn');
    const digitInputs = document.querySelectorAll('.otp-digit-box');
    const hiddenOtpInput = document.getElementById('login-otp-code');

    const emailModeIndicator = document.getElementById('email-mode-indicator');
    const emailModeLabel = document.getElementById('email-mode-label');
    const emailOutboxModal = document.getElementById('email-outbox-modal');
    const modalEmailModePill = document.getElementById('modal-email-mode-pill');
    const outboxEmailList = document.getElementById('outbox-email-list');

    let pendingLoginEmail = '';
    let resendTimer = null;

    // Check system email delivery mode
    checkEmailDeliveryStatus();

    async function checkEmailDeliveryStatus() {
      try {
        const status = await VAYORA.request('/auth/email-status');
        if (status && status.smtp_configured) {
          if (emailModeLabel) emailModeLabel.textContent = '📧 Live SMTP Active (Real Inboxes)';
          if (modalEmailModePill) modalEmailModePill.textContent = 'LIVE SMTP DELIVERY';
        } else {
          if (emailModeLabel) emailModeLabel.textContent = '📧 Sandbox Email Mode (Click to View Dispatched Codes)';
          if (modalEmailModePill) modalEmailModePill.textContent = 'SANDBOX / LOCAL LOG';
        }
      } catch (e) {
        console.warn('Email status check failed', e);
      }
    }

    if (emailModeIndicator) {
      emailModeIndicator.addEventListener('click', async () => {
        if (emailOutboxModal) {
          emailOutboxModal.classList.add('open');
          await loadRecentDispatchedEmails();
        }
      });
    }

    async function loadRecentDispatchedEmails() {
      if (!outboxEmailList) return;
      try {
        const emails = await VAYORA.request('/auth/recent-emails');
        if (!emails || emails.length === 0) {
          outboxEmailList.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">No emails dispatched yet in this session.</div>';
          return;
        }

        outboxEmailList.innerHTML = emails.map(em => `
          <div style="background: var(--bg-secondary); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span style="font-weight: 700; color: var(--text-primary); font-size: 0.85rem;">${em.subject}</span>
              <span class="status-pill ${em.mode === 'LIVE_SMTP' ? 'status-completed' : 'status-active'}">${em.mode}</span>
            </div>
            <div style="font-size: 0.78rem; color: var(--neon-cyan); margin-bottom: 4px;">To: ${em.recipient}</div>
            ${em.otp_code ? `
              <div style="background: rgba(0,245,155,0.08); border: 1px dashed rgba(0,245,155,0.3); border-radius: var(--radius-sm); padding: 6px 10px; margin: 8px 0; display: inline-flex; align-items: center; gap: 8px;">
                <span style="font-size: 0.75rem; color: var(--text-secondary);">Security Code:</span>
                <strong style="font-family: var(--font-mono); font-size: 1.1rem; color: var(--neon-emerald); letter-spacing: 2px;">${em.otp_code}</strong>
                <button type="button" class="btn btn-secondary btn-sm" style="padding: 2px 8px; font-size: 0.7rem; margin-left: 6px;" onclick="navigator.clipboard.writeText('${em.otp_code}'); VAYORA.showToast('Copied', 'Code copied to clipboard', 'info');">Copy</button>
              </div>
            ` : ''}
            <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 4px;">${VAYORA.formatDate(em.timestamp)}</div>
          </div>
        `).join('');
      } catch (e) {
        console.warn('Failed to load recent emails', e);
      }
    }

    // Digit Boxes Auto Navigation & Paste Handling
    digitInputs.forEach((input, index) => {
      input.addEventListener('input', (e) => {
        const val = e.target.value.replace(/\D/g, '');
        e.target.value = val ? val[0] : '';
        aggregateOtpDigits();

        if (val && index < digitInputs.length - 1) {
          digitInputs[index + 1].focus();
        }
      });

      input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !input.value && index > 0) {
          digitInputs[index - 1].focus();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          executeVerifyLogin();
        }
      });

      input.addEventListener('paste', (e) => {
        e.preventDefault();
        const pasted = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
        if (pasted.length >= 6) {
          for (let i = 0; i < 6; i++) {
            if (digitInputs[i]) digitInputs[i].value = pasted[i];
          }
          aggregateOtpDigits();
          digitInputs[5].focus();
        }
      });
    });

    function aggregateOtpDigits() {
      let code = '';
      digitInputs.forEach(i => code += i.value);
      if (hiddenOtpInput) hiddenOtpInput.value = code;
      return code;
    }

    function clearOtpDigits() {
      digitInputs.forEach(i => i.value = '');
      if (hiddenOtpInput) hiddenOtpInput.value = '';
      if (digitInputs[0]) digitInputs[0].focus();
    }

    // STEP 1: Submit email + password
    if (loginForm) {
      loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = emailInput.value.trim();
        const password = passInput.value;
        const requireOtp = require2FaCheck ? require2FaCheck.checked : false;

        if (!email || !password) {
          VAYORA.showToast('Validation Error', 'Please enter both email and password', 'error');
          return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Authenticating...';

        try {
          const res = await VAYORA.request('/auth/login', {
            method: 'POST',
            body: {
              email,
              password,
              require_otp: requireOtp
            }
          });

          pendingLoginEmail = email;

          // Check if Real 2-Step OTP is required
          if (res.requires_otp) {
            loginForm.style.display = 'none';
            if (demoContainer) demoContainer.style.display = 'none';
            if (otpStepCard) otpStepCard.style.display = 'block';
            if (otpTargetEmail) otpTargetEmail.textContent = res.email || email;

            clearOtpDigits();
            startResendCountdown();

            VAYORA.showToast('Code Dispatched', res.message || `A verification code was sent to ${email}`, 'info');
            return;
          }

          // Direct login (e.g. demo account without explicit 2FA)
          if (res.access_token) {
            VAYORA.setToken(res.access_token);
            VAYORA.setCurrentUser(res.user);
            VAYORA.showToast('Welcome Back', `Logged in as ${res.user.name}`, 'success');

            setTimeout(() => {
              window.location.href = '/dashboard.html';
            }, 600);
          }
        } catch (err) {
          VAYORA.showToast('Authentication Failed', err.message, 'error');
          submitBtn.disabled = false;
          submitBtn.innerHTML = 'Sign In to VAYORA';
        }
      });
    }

    // STEP 2: Verify Login OTP
    async function executeVerifyLogin() {
      const code = aggregateOtpDigits();
      if (code.length < 6) {
        VAYORA.showToast('Validation Error', 'Please enter the complete 6-digit code', 'error');
        return;
      }

      verifyLoginBtn.disabled = true;
      verifyLoginBtn.innerHTML = '<span class="spinner"></span> Verifying Code...';

      try {
        const res = await VAYORA.request('/auth/verify-login-otp', {
          method: 'POST',
          body: {
            email: pendingLoginEmail,
            otp_code: code
          }
        });

        VAYORA.setToken(res.access_token);
        VAYORA.setCurrentUser(res.user);
        VAYORA.showToast('Authentication Verified', `Welcome back, ${res.user.name}!`, 'success');

        setTimeout(() => {
          window.location.href = '/dashboard.html';
        }, 600);
      } catch (err) {
        VAYORA.showToast('Verification Failed', err.message, 'error');
        verifyLoginBtn.disabled = false;
        verifyLoginBtn.innerHTML = 'Authorize & Sign In';
        clearOtpDigits();
      }
    }

    if (verifyLoginBtn) {
      verifyLoginBtn.addEventListener('click', executeVerifyLogin);
    }

    // Back button (edit email)
    if (backToLoginBtn) {
      backToLoginBtn.addEventListener('click', () => {
        if (otpStepCard) otpStepCard.style.display = 'none';
        if (loginForm) loginForm.style.display = 'block';
        if (demoContainer) demoContainer.style.display = 'block';
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Sign In to VAYORA';
      });
    }

    // Resend Login OTP
    if (resendLoginOtpBtn) {
      resendLoginOtpBtn.addEventListener('click', async () => {
        if (!pendingLoginEmail) return;
        try {
          resendLoginOtpBtn.disabled = true;
          resendLoginOtpBtn.textContent = 'Sending...';

          const res = await VAYORA.request('/auth/resend-login-otp', {
            method: 'POST',
            body: {
              email: pendingLoginEmail,
              otp_type: 'login_otp'
            }
          });

          VAYORA.showToast('Code Resent', res.message || 'A new code has been dispatched to your email', 'info');
          startResendCountdown();
          clearOtpDigits();
        } catch (err) {
          VAYORA.showToast('Resend Failed', err.message, 'error');
          resendLoginOtpBtn.disabled = false;
          resendLoginOtpBtn.textContent = 'Resend Code';
        }
      });
    }

    function startResendCountdown() {
      if (!resendLoginOtpBtn) return;
      clearInterval(resendTimer);
      let seconds = 45;
      resendLoginOtpBtn.disabled = true;
      resendLoginOtpBtn.textContent = `Resend in ${seconds}s`;

      resendTimer = setInterval(() => {
        seconds--;
        if (seconds <= 0) {
          clearInterval(resendTimer);
          resendLoginOtpBtn.disabled = false;
          resendLoginOtpBtn.textContent = 'Resend Code';
        } else {
          resendLoginOtpBtn.textContent = `Resend in ${seconds}s`;
        }
      }, 1000);
    }
  }

  // --- REGISTRATION WORKFLOW ---
  if (isRegisterPage) {
    const regForm = document.getElementById('register-form');
    const nameInput = document.getElementById('reg-name');
    const emailInput = document.getElementById('reg-email');
    const passInput = document.getElementById('reg-password');
    const phoneInput = document.getElementById('reg-phone');
    const regSubmitBtn = document.getElementById('reg-submit-btn');

    const otpModal = document.getElementById('otp-verify-modal');
    const otpInput = document.getElementById('reg-otp-code');
    const verifyOtpBtn = document.getElementById('verify-otp-btn');
    const otpNoticeText = document.getElementById('otp-demo-code-notice');

    let registeredEmail = '';

    if (regForm) {
      regForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = nameInput.value.trim();
        const email = emailInput.value.trim();
        const password = passInput.value;
        const phone = phoneInput ? phoneInput.value.trim() : null;

        if (!name || !email || !password) {
          VAYORA.showToast('Error', 'Please fill in all required fields', 'error');
          return;
        }

        regSubmitBtn.disabled = true;
        regSubmitBtn.innerHTML = '<span class="spinner"></span> Creating Account...';

        try {
          const res = await VAYORA.request('/auth/register', {
            method: 'POST',
            body: { name, email, password, phone }
          });

          VAYORA.setToken(res.access_token);
          VAYORA.setCurrentUser(res.user);
          registeredEmail = email;

          // Open Email Verification Modal with real email alert
          if (otpModal) {
            otpModal.classList.add('open');
            if (otpNoticeText) {
              otpNoticeText.innerHTML = `A verification code was dispatched to <strong>${email}</strong>. Check your inbox or spam folder.`;
            }
          } else {
            VAYORA.showToast('Account Created', 'Welcome to VAYORA! Check your email for verification.', 'success');
            setTimeout(() => window.location.href = '/dashboard.html', 800);
          }
        } catch (err) {
          VAYORA.showToast('Registration Error', err.message, 'error');
          regSubmitBtn.disabled = false;
          regSubmitBtn.innerHTML = 'Create Free Account';
        }
      });
    }

    let isVerifyingOtp = false;

    if (verifyOtpBtn) {
      async function executeVerifyEmailOtp() {
        if (isVerifyingOtp) return;

        const code = otpInput.value.trim();
        if (!code) {
          VAYORA.showToast('Validation Error', 'Please enter your 6-digit verification code', 'error');
          return;
        }

        if (code.length !== 6 || !/^\d{6}$/.test(code)) {
          VAYORA.showToast('Invalid Code', 'Verification code must be exactly 6 numeric digits', 'error');
          return;
        }

        // Ensure registeredEmail is available (fallback to localStorage or input)
        if (!registeredEmail) {
          const currentUser = VAYORA.getCurrentUser();
          if (currentUser && currentUser.email) {
            registeredEmail = currentUser.email;
          } else if (emailInput && emailInput.value.trim()) {
            registeredEmail = emailInput.value.trim();
          }
        }

        if (!registeredEmail) {
          VAYORA.showToast('Session Expired', 'Please enter your email and register again.', 'error');
          return;
        }

        isVerifyingOtp = true;
        verifyOtpBtn.disabled = true;
        const originalBtnText = verifyOtpBtn.innerHTML;
        verifyOtpBtn.innerHTML = '<span class="spinner"></span> Verifying Code...';

        try {
          const res = await VAYORA.request('/auth/verify-email', {
            method: 'POST',
            body: { email: registeredEmail, otp_code: code }
          });

          if (res.access_token) {
            VAYORA.setToken(res.access_token);
          }
          if (res.user) {
            VAYORA.setCurrentUser(res.user);
          }

          verifyOtpBtn.innerHTML = 'Verified!';
          VAYORA.showToast('Verified!', 'Email address verified successfully. Entering dashboard...', 'success');
          setTimeout(() => {
            window.location.href = '/dashboard.html';
          }, 600);
        } catch (err) {
          isVerifyingOtp = false;
          verifyOtpBtn.disabled = false;
          verifyOtpBtn.innerHTML = originalBtnText;
          VAYORA.showToast('Verification Failed', err.message, 'error');
        }
      }

      verifyOtpBtn.addEventListener('click', executeVerifyEmailOtp);

      if (otpInput) {
        otpInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            executeVerifyEmailOtp();
          }
        });
      }
    }

    const resendOtpBtn = document.getElementById('resend-otp-btn');
    if (resendOtpBtn) {
      let isResending = false;
      resendOtpBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (isResending) return;

        if (!registeredEmail) {
          const currentUser = VAYORA.getCurrentUser();
          if (currentUser && currentUser.email) {
            registeredEmail = currentUser.email;
          } else if (emailInput && emailInput.value.trim()) {
            registeredEmail = emailInput.value.trim();
          }
        }

        if (!registeredEmail) {
          VAYORA.showToast('Error', 'Please provide your registered email address.', 'error');
          return;
        }

        isResending = true;
        resendOtpBtn.style.pointerEvents = 'none';
        resendOtpBtn.style.opacity = '0.6';
        resendOtpBtn.textContent = 'Dispatching new code...';

        try {
          const res = await VAYORA.request('/auth/resend-email-otp', {
            method: 'POST',
            body: { email: registeredEmail }
          });

          VAYORA.showToast('Code Dispatched', res.message || `A new verification code was sent to ${registeredEmail}`, 'info');
          if (otpNoticeText) {
            otpNoticeText.innerHTML = `A fresh verification code was dispatched to <strong>${registeredEmail}</strong>.`;
          }

          let cooldown = 30;
          const timer = setInterval(() => {
            cooldown--;
            if (cooldown <= 0) {
              clearInterval(timer);
              isResending = false;
              resendOtpBtn.style.pointerEvents = 'auto';
              resendOtpBtn.style.opacity = '1';
              resendOtpBtn.textContent = 'Resend Code';
            } else {
              resendOtpBtn.textContent = `Resend Code (${cooldown}s)`;
            }
          }, 1000);
        } catch (err) {
          isResending = false;
          resendOtpBtn.style.pointerEvents = 'auto';
          resendOtpBtn.style.opacity = '1';
          resendOtpBtn.textContent = 'Resend Code';
          VAYORA.showToast('Resend Failed', err.message, 'error');
        }
      });
    }
  }

  // --- FORGOT / RESET PASSWORD ---
  if (isForgotPage) {
    const forgotForm = document.getElementById('forgot-form');
    const resetForm = document.getElementById('reset-form');
    const emailInput = document.getElementById('forgot-email');
    const codeNotice = document.getElementById('forgot-code-notice');
    let resetEmail = '';

    if (forgotForm) {
      forgotForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = emailInput.value.trim();
        if (!email) return;

        try {
          const res = await VAYORA.request('/auth/forgot-password', {
            method: 'POST',
            body: { email }
          });

          resetEmail = email;
          forgotForm.style.display = 'none';
          resetForm.style.display = 'block';

          if (codeNotice) {
            codeNotice.textContent = `A password reset code was dispatched to ${email}.`;
          }
          VAYORA.showToast('Code Dispatched', 'Please enter your reset code and new password', 'info');
        } catch (err) {
          VAYORA.showToast('Error', err.message, 'error');
        }
      });
    }

    if (resetForm) {
      resetForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const otp_code = document.getElementById('reset-otp').value.trim();
        const new_password = document.getElementById('reset-new-pass').value;

        try {
          await VAYORA.request('/auth/reset-password', {
            method: 'POST',
            body: { email: resetEmail, otp_code, new_password }
          });

          VAYORA.showToast('Success', 'Password has been reset. Please sign in.', 'success');
          setTimeout(() => window.location.href = '/login.html', 1000);
        } catch (err) {
          VAYORA.showToast('Reset Failed', err.message, 'error');
        }
      });
    }
  }
});

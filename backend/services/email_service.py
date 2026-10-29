import os
import smtplib
import logging
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
import backend.config
logger = logging.getLogger("vayora.email")
logger.setLevel(logging.INFO)

# Thread pool for non-blocking asynchronous email delivery
_email_executor = ThreadPoolExecutor(max_workers=4)

# In-memory circular buffer of recently dispatched emails for audit/sandbox viewing
_recent_emails: List[Dict[str, Any]] = []
_MAX_RECENT_EMAILS = 50

def get_smtp_config() -> Dict[str, Any]:
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip(),
        "from_email": os.getenv("SMTP_FROM_EMAIL", "").strip() or os.getenv("SMTP_USER", "no-reply@vayora.network").strip(),
        "from_name": os.getenv("SMTP_FROM_NAME", "VAYORA Security & FinTech").strip(),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        "use_ssl": os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes"),
    }

def is_smtp_configured() -> bool:
    cfg = get_smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"])

def record_email_dispatch(to_email: str, subject: str, body_text: str, mode: str, status: str, otp_code: Optional[str] = None):
    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production" or bool(os.getenv("VERCEL_ENV"))
    # In production, never retain or expose cleartext OTP codes
    stored_otp = "[REDACTED]" if (is_prod and otp_code) else otp_code

    clean_recipient = to_email.strip().lower()
    for entry in _recent_emails:
        if entry["recipient"] == clean_recipient and entry["subject"] == subject:
            entry["status"] = status
            entry["mode"] = mode
            if otp_code:
                entry["otp_code"] = stored_otp
            return
    entry = {
        "id": len(_recent_emails) + 1,
        "recipient": clean_recipient,
        "subject": subject,
        "summary": body_text[:160] + "..." if len(body_text) > 160 else body_text,
        "otp_code": stored_otp,
        "mode": mode,
        "status": status,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    _recent_emails.insert(0, entry)
    if len(_recent_emails) > _MAX_RECENT_EMAILS:
        _recent_emails.pop()

def get_recent_emails(limit: int = 15) -> List[Dict[str, Any]]:
    return _recent_emails[:limit]

def send_email_sync(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    otp_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends an email via real SMTP if credentials exist in .env.
    If SMTP credentials are not configured, dispatches in Sandbox/Local mode
    so no errors break the user flow while still logging the full OTP code.
    """
    cfg = get_smtp_config()
    clean_recipient = to_email.strip().lower()

    if not text_content:
        # Fallback text content strip
        text_content = html_content.replace("<br>", "\n").replace("</p>", "\n")

    if is_smtp_configured():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{cfg['from_name']} <{cfg['from_email']}>"
            msg["To"] = clean_recipient

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            if cfg["use_ssl"] or cfg["port"] == 465:
                server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=12)
            else:
                server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=12)
                if cfg["use_tls"]:
                    server.starttls()

            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_email"], [clean_recipient], msg.as_string())
            server.quit()

            logger.info(f"[REAL EMAIL DELIVERED] Successfully sent email to {clean_recipient} | Subject: {subject}")
            record_email_dispatch(clean_recipient, subject, text_content, "LIVE_SMTP", "DELIVERED", otp_code)
            return {
                "success": True,
                "mode": "LIVE_SMTP",
                "recipient": clean_recipient,
                "message": f"Real email delivered to {clean_recipient}"
            }
        except Exception as e:
            err_msg = str(e)
            if "@" in err_msg:
                err_msg = err_msg.split("@")[-1]
            logger.error(f"[SMTP SEND ERROR] Failed sending to {clean_recipient}: {err_msg[:120]}")
            record_email_dispatch(clean_recipient, subject, text_content, "LIVE_SMTP_ERROR", f"Delivery failed: {err_msg[:80]}", otp_code)
            return {
                "success": False,
                "mode": "SMTP_FAILED_FALLBACK",
                "recipient": clean_recipient,
                "error": "Email delivery failed",
                "message": "SMTP delivery failed. Please check SMTP configuration."
            }
    else:
        # Sandbox simulated mode
        is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production" or bool(os.getenv("VERCEL_ENV"))
        logged_otp = "[REDACTED]" if is_prod else (otp_code or "N/A")
        logger.info(f"[SANDBOX EMAIL LOG] To: {clean_recipient} | Subject: {subject} | OTP: {logged_otp}")
        record_email_dispatch(clean_recipient, subject, text_content, "SANDBOX_SIMULATION", "RECORDED", otp_code)
        display_msg = "Email recorded in Sandbox mode (SMTP not configured)."
        if not is_prod and otp_code:
            display_msg += f" OTP: {otp_code}"
        return {
            "success": True,
            "mode": "SANDBOX_SIMULATION",
            "recipient": clean_recipient,
            "message": display_msg
        }

def send_email_async(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    otp_code: Optional[str] = None
):
    """
    Dispatches email sending. In persistent servers, runs in background thread.
    In serverless environments (e.g. Vercel Functions), executes synchronously
    to prevent container freeze from interrupting SMTP network transmission.
    """
    clean_recipient = to_email.strip().lower()
    summary = text_content or html_content.replace("<br>", "\n").replace("</p>", "\n")
    mode = "LIVE_SMTP" if is_smtp_configured() else "SANDBOX_SIMULATION"
    record_email_dispatch(clean_recipient, subject, summary, mode, "DISPATCHING", otp_code)
    
    is_serverless = os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV"))
    if is_serverless:
        send_email_sync(to_email, subject, html_content, text_content, otp_code)
    else:
        _email_executor.submit(send_email_sync, to_email, subject, html_content, text_content, otp_code)


# --- HTML EMAIL TEMPLATES WITH VAYORA FINTECH BRANDING ---

def _render_base_email(title: str, content_html: str, action_note: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #07090e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #d1d5db;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #07090e; padding: 30px 10px;">
    <tr>
      <td align="center">
        <!-- Main Container -->
        <table role="presentation" width="100%" style="max-width: 540px; background-color: #0d111a; border: 1px solid #1a2233; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.6);" cellspacing="0" cellpadding="0">
          <!-- Top Accent Line -->
          <tr>
            <td style="height: 3px; background: linear-gradient(90deg, #00f59b 0%, #00d2ff 100%);"></td>
          </tr>
          <!-- Header -->
          <tr>
            <td style="padding: 32px 36px 20px 36px; text-align: center; border-bottom: 1px solid #141b2a;">
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto;">
                <tr>
                  <td style="background: linear-gradient(135deg, rgba(0,245,155,0.15) 0%, rgba(0,210,255,0.15) 100%); border: 1px solid rgba(0,245,155,0.3); border-radius: 12px; width: 44px; height: 44px; text-align: center; vertical-align: middle;">
                    <span style="font-size: 22px; font-weight: 900; color: #00f59b; font-family: monospace;">V</span>
                  </td>
                  <td style="padding-left: 12px; text-align: left;">
                    <div style="font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: 1.5px;">VAYORA<span style="color: #00f59b;">.</span></div>
                    <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Unified Digital Value</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Content -->
          <tr>
            <td style="padding: 32px 36px;">
              {content_html}
            </td>
          </tr>
          <!-- Footer Note -->
          {f'<tr><td style="padding: 0 36px 24px 36px; font-size: 11px; color: #64748b; line-height: 1.5;">{action_note}</td></tr>' if action_note else ''}
          <!-- Footer -->
          <tr>
            <td style="background-color: #090c14; padding: 24px 36px; text-align: center; border-top: 1px solid #141b2a;">
              <div style="font-size: 11px; color: #64748b; margin-bottom: 6px;">
                Secured by VAYORA Cryptographic Dual-Entry Ledger
              </div>
              <div style="font-size: 10px; color: #475569;">
                &copy; {datetime.datetime.utcnow().year} VAYORA Network. All rights reserved.
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_login_otp_email(
    to_email: str,
    otp_code: str,
    user_name: str = "User",
    ip_address: str = "Unknown IP",
    device: str = "Web Browser"
) -> Dict[str, Any]:
    """Generates and sends a 2-Step Verification Login OTP email."""
    subject = f"🔐 Your VAYORA Sign-In Code: {otp_code}"
    
    content = f"""
      <h2 style="font-size: 20px; font-weight: 700; color: #ffffff; margin: 0 0 12px 0;">Sign-In Verification</h2>
      <p style="font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 0 0 24px 0;">
        Hello <strong style="color: #ffffff;">{user_name}</strong>, we received a sign-in request for your VAYORA account.
        Use the one-time security code below to complete your authentication:
      </p>

      <!-- OTP Display Box -->
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 0 0 24px 0;">
        <tr>
          <td align="center" style="background: rgba(0, 245, 155, 0.05); border: 1px solid rgba(0, 245, 155, 0.3); border-radius: 12px; padding: 22px 20px;">
            <div style="font-size: 11px; font-weight: 700; color: #00f59b; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px;">
              One-Time Login Code
            </div>
            <div style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; color: #ffffff; letter-spacing: 10px; text-shadow: 0 0 20px rgba(0,245,155,0.4);">
              {otp_code}
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 8px;">
              Valid for <strong style="color: #cbd5e1;">10 minutes</strong>. Never share this code with anyone.
            </div>
          </td>
        </tr>
      </table>

      <!-- Device Metadata -->
      <div style="background: #090c14; border: 1px solid #1a2233; border-radius: 8px; padding: 14px 16px; font-size: 12px; color: #94a3b8; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
          <span>Requested From:</span>
          <span style="color: #ffffff; font-family: monospace;">{ip_address}</span>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span>Client / Device:</span>
          <span style="color: #ffffff;">{device}</span>
        </div>
      </div>
    """

    action_note = "If you did not request this login code, someone may be trying to access your account. Please change your password immediately."
    html = _render_base_email("Sign-In Security Code", content, action_note)
    text = f"Your VAYORA Sign-In Code is: {otp_code}. Valid for 10 minutes. IP: {ip_address}, Device: {device}."
    
    send_email_async(to_email, subject, html, text, otp_code=otp_code)
    return {"subject": subject, "otp_code": otp_code, "recipient": to_email}


def send_registration_otp_email(
    to_email: str,
    otp_code: str,
    user_name: str = "User"
) -> Dict[str, Any]:
    """Generates and sends Email Verification OTP upon registration."""
    subject = f"✨ Welcome to VAYORA — Verify Your Email: {otp_code}"
    
    content = f"""
      <h2 style="font-size: 20px; font-weight: 700; color: #ffffff; margin: 0 0 12px 0;">Welcome to VAYORA!</h2>
      <p style="font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 0 0 24px 0;">
        Hello <strong style="color: #ffffff;">{user_name}</strong>, thank you for joining VAYORA.
        Please confirm your email address using the verification code below:
      </p>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 0 0 24px 0;">
        <tr>
          <td align="center" style="background: rgba(0, 210, 255, 0.05); border: 1px solid rgba(0, 210, 255, 0.3); border-radius: 12px; padding: 22px 20px;">
            <div style="font-size: 11px; font-weight: 700; color: #00d2ff; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px;">
              Email Activation Code
            </div>
            <div style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; color: #ffffff; letter-spacing: 10px;">
              {otp_code}
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 8px;">
              Expires in 30 minutes.
            </div>
          </td>
        </tr>
      </table>
    """

    action_note = "By verifying your email, you activate your unified multi-asset wallet and instant digital payments."
    html = _render_base_email("Verify Your VAYORA Account", content, action_note)
    text = f"Welcome to VAYORA! Your email verification code is: {otp_code}."
    
    send_email_async(to_email, subject, html, text, otp_code=otp_code)
    return {"subject": subject, "otp_code": otp_code, "recipient": to_email}


def send_password_reset_email(
    to_email: str,
    otp_code: str,
    user_name: str = "User"
) -> Dict[str, Any]:
    """Generates and sends Password Recovery OTP email."""
    subject = f"🔑 VAYORA Password Reset Code: {otp_code}"
    
    content = f"""
      <h2 style="font-size: 20px; font-weight: 700; color: #ffffff; margin: 0 0 12px 0;">Password Recovery</h2>
      <p style="font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 0 0 24px 0;">
        Hello <strong style="color: #ffffff;">{user_name}</strong>, a request was received to reset your VAYORA account password.
        Use this one-time code to proceed:
      </p>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 0 0 24px 0;">
        <tr>
          <td align="center" style="background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 22px 20px;">
            <div style="font-size: 11px; font-weight: 700; color: #f87171; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px;">
              Reset Authorization Code
            </div>
            <div style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; color: #ffffff; letter-spacing: 10px;">
              {otp_code}
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 8px;">
              Valid for 15 minutes.
            </div>
          </td>
        </tr>
      </table>
    """

    action_note = "If you did not request a password reset, please ignore this email or review your account activity."
    html = _render_base_email("Password Reset", content, action_note)
    text = f"Your VAYORA Password Reset Code is: {otp_code}."
    
    send_email_async(to_email, subject, html, text, otp_code=otp_code)
    return {"subject": subject, "otp_code": otp_code, "recipient": to_email}


def send_payment_notification_email(
    to_email: str,
    user_name: str,
    amount: float,
    asset_symbol: str,
    reference: str,
    counterparty_email: str,
    is_sender: bool,
    note: Optional[str] = None
) -> Dict[str, Any]:
    """Generates and sends transaction receipt email to sender or receiver."""
    if is_sender:
        subject = f"💸 Payment Sent: {amount:.4f} {asset_symbol} to {counterparty_email}"
        headline = "Transfer Dispatched"
        color = "#00d2ff"
        desc = f"You sent <strong style='color:#ffffff;'>{amount:.4f} {asset_symbol}</strong> to <strong style='color:#00d2ff;'>{counterparty_email}</strong>."
    else:
        subject = f"💰 Payment Received: +{amount:.4f} {asset_symbol} from {counterparty_email}"
        headline = "Funds Received!"
        color = "#00f59b"
        desc = f"You received <strong style='color:#00f59b;'>+{amount:.4f} {asset_symbol}</strong> from <strong style='color:#ffffff;'>{counterparty_email}</strong>."

    content = f"""
      <h2 style="font-size: 20px; font-weight: 700; color: #ffffff; margin: 0 0 12px 0;">{headline}</h2>
      <p style="font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 0 0 20px 0;">
        Hello <strong style="color: #ffffff;">{user_name}</strong>,<br>
        {desc}
      </p>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #090c14; border: 1px solid #1a2233; border-radius: 12px; padding: 18px; margin: 0 0 20px 0;">
        <tr>
          <td style="padding-bottom: 8px; font-size: 12px; color: #64748b;">Amount:</td>
          <td align="right" style="padding-bottom: 8px; font-size: 15px; font-weight: 700; color: {color}; font-family: monospace;">
            {amount:.4f} {asset_symbol}
          </td>
        </tr>
        <tr>
          <td style="padding-bottom: 8px; font-size: 12px; color: #64748b;">Counterparty:</td>
          <td align="right" style="padding-bottom: 8px; font-size: 13px; color: #ffffff;">
            {counterparty_email}
          </td>
        </tr>
        <tr>
          <td style="padding-bottom: 8px; font-size: 12px; color: #64748b;">Reference ID:</td>
          <td align="right" style="padding-bottom: 8px; font-size: 12px; color: #00d2ff; font-family: monospace;">
            {reference}
          </td>
        </tr>
        {f'<tr><td style="font-size: 12px; color: #64748b;">Note:</td><td align="right" style="font-size: 12px; color: #e2e8f0;">{note}</td></tr>' if note else ''}
      </table>
    """

    html = _render_base_email(headline, content, "Settled instantly on VAYORA Ledger.")
    text = f"{headline}: {amount} {asset_symbol} | Counterparty: {counterparty_email} | Ref: {reference}"
    
    send_email_async(to_email, subject, html, text)
    return {"subject": subject, "recipient": to_email}


def send_deposit_receipt_email(
    to_email: str,
    user_name: str,
    amount: float,
    currency: str,
    reference: str,
    payment_method: str,
    new_balance: float
) -> Dict[str, Any]:
    """Receipt email for real payment checkout / deposit."""
    subject = f"🧾 Payment Receipt: {amount:.2f} {currency} Added to Your VAYORA Wallet"
    
    content = f"""
      <h2 style="font-size: 20px; font-weight: 700; color: #ffffff; margin: 0 0 12px 0;">Deposit Confirmed</h2>
      <p style="font-size: 14px; color: #94a3b8; line-height: 1.6; margin: 0 0 20px 0;">
        Hello <strong style="color: #ffffff;">{user_name}</strong>, your payment has been processed successfully.
        The funds have been credited to your active wallet.
      </p>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #090c14; border: 1px solid #1a2233; border-radius: 12px; padding: 18px; margin: 0 0 20px 0;">
        <tr>
          <td style="padding-bottom: 8px; font-size: 12px; color: #64748b;">Deposit Amount:</td>
          <td align="right" style="padding-bottom: 8px; font-size: 16px; font-weight: 700; color: #00f59b; font-family: monospace;">
            +{amount:.2f} {currency}
          </td>
        </tr>
        <tr>
          <td style="padding-bottom: 8px; font-size: 12px; color: #64748b;">Payment Method:</td>
          <td align="right" style="padding-bottom: 8px; font-size: 13px; color: #ffffff;">
            {payment_method}
          </td>
        </tr>
        <tr>
          <td style="padding-bottom: 8px; font-size: 12px; color: #64748b;">Invoice Reference:</td>
          <td align="right" style="padding-bottom: 8px; font-size: 12px; color: #00d2ff; font-family: monospace;">
            {reference}
          </td>
        </tr>
        <tr>
          <td style="font-size: 12px; color: #64748b;">Updated Balance:</td>
          <td align="right" style="font-size: 14px; font-weight: 700; color: #ffffff; font-family: monospace;">
            {new_balance:.2f} {currency}
          </td>
        </tr>
      </table>
    """

    html = _render_base_email("Payment Receipt", content, "Thank you for funding your VAYORA digital value account.")
    text = f"Deposit Receipt: {amount} {currency} via {payment_method}. Ref: {reference}."
    
    send_email_async(to_email, subject, html, text)
    return {"subject": subject, "recipient": to_email}

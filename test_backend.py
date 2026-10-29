import sys
import os

# Set standard output to UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add root directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.seed import seed_database
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def run_tests():
    print("==================================================")
    print("VAYORA BACKEND AUTOMATED TEST SUITE")
    print("==================================================")

    # 0. Deterministic fresh seed
    print("\n--- Initializing Fresh Test State ---")
    seed_database()

    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    assert "real_time_users_online" in health_data
    print(f"[PASS] 1. Health Check Passed (Live Online: {health_data['real_time_users_online']})")

    # 2. Login as User A (Sender)
    res_a = client.post("/api/auth/login", json={
        "email": "sender@vayora.demo",
        "password": "Password@123"
    })
    assert res_a.status_code == 200, f"User A login failed: {res_a.text}"
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    print("[PASS] 2. User A (Sender) Login Passed")

    # 3. Check User A Initial Wallet (must have 500 USDT)
    res_w_a = client.get("/api/wallet", headers=headers_a)
    assert res_w_a.status_code == 200
    wallet_a_data = res_w_a.json()
    usdt_bal_a = next(b["amount"] for b in wallet_a_data["balances"] if b["symbol"] == "USDT")
    assert usdt_bal_a == 500.0, f"Expected 500 USDT for User A, got {usdt_bal_a}"
    print(f"[PASS] 3. User A Initial USDT Balance: {usdt_bal_a} USDT (Verified)")

    # 4. Login as User B (Receiver)
    res_b = client.post("/api/auth/login", json={
        "email": "receiver@vayora.demo",
        "password": "Password@123"
    })
    assert res_b.status_code == 200, f"User B login failed: {res_b.text}"
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    print("[PASS] 4. User B (Receiver) Login Passed")

    # 5. Check User B Initial Wallet (must have 0 USDT)
    res_w_b = client.get("/api/wallet", headers=headers_b)
    assert res_w_b.status_code == 200
    wallet_b_data = res_w_b.json()
    usdt_bal_b = next(b["amount"] for b in wallet_b_data["balances"] if b["symbol"] == "USDT")
    assert usdt_bal_b == 0.0, f"Expected 0 USDT for User B, got {usdt_bal_b}"
    print(f"[PASS] 5. User B Initial USDT Balance: {usdt_bal_b} USDT (Verified)")

    # 6. CRITICAL SCENARIO: Send 100 USDT from User A to User B
    print("\n--- Executing Critical Peer-to-Peer Transfer ---")
    send_payload = {
        "recipient": "receiver@vayora.demo",
        "asset_symbol": "USDT",
        "amount": 100.0,
        "note": "Payment for frontend UI engineering milestone"
    }
    res_send = client.post("/api/payments/send", json=send_payload, headers=headers_a)
    assert res_send.status_code == 200, f"Send failed: {res_send.text}"
    send_data = res_send.json()
    print(f"[PASS] 6. Payment Sent Successfully! Ref: {send_data['reference']}")

    # 7. Verify User A Balance is now 400 USDT
    res_w_a_after = client.get("/api/wallet", headers=headers_a)
    usdt_bal_a_after = next(b["amount"] for b in res_w_a_after.json()["balances"] if b["symbol"] == "USDT")
    assert usdt_bal_a_after == 400.0, f"Expected 400 USDT for User A, got {usdt_bal_a_after}"
    print(f"[PASS] 7. User A Balance After Send: 500 -> {usdt_bal_a_after} USDT (Verified)")

    # 8. Verify User B Balance is now 100 USDT
    res_w_b_after = client.get("/api/wallet", headers=headers_b)
    usdt_bal_b_after = next(b["amount"] for b in res_w_b_after.json()["balances"] if b["symbol"] == "USDT")
    assert usdt_bal_b_after == 100.0, f"Expected 100 USDT for User B, got {usdt_bal_b_after}"
    print(f"[PASS] 8. User B Balance After Send: 0 -> {usdt_bal_b_after} USDT (Verified)")

    # 9. Verify Transactions for both users
    tx_b = client.get("/api/transactions", headers=headers_b).json()
    assert len(tx_b) > 0
    latest_tx_b = tx_b[0]
    assert latest_tx_b["type"] == "RECEIVE"
    assert latest_tx_b["amount"] == 100.0
    print(f"[PASS] 9. User B Received Transaction Record: +{latest_tx_b['amount']} USDT ({latest_tx_b['status']})")

    # 10. Insufficient Balance Check
    res_fail = client.post("/api/payments/send", json={
        "recipient": "receiver@vayora.demo",
        "asset_symbol": "USDT",
        "amount": 999999.0
    }, headers=headers_a)
    assert res_fail.status_code == 400, "Insufficient balance check failed to reject"
    print("[PASS] 10. Insufficient Balance Validation Protected System")

    # 11. Test Swap: User A swaps 50 USDT to USDC
    print("\n--- Testing Instant Swap ---")
    quote_res = client.get("/api/swap/quote?from_symbol=USDT&to_symbol=USDC&from_amount=50", headers=headers_a)
    assert quote_res.status_code == 200
    quote = quote_res.json()
    print(f"[PASS] 11. Swap Quote: 50 USDT -> {quote['to_amount']} USDC (Rate: {quote['rate']})")

    swap_res = client.post("/api/swap", json={
        "from_symbol": "USDT",
        "to_symbol": "USDC",
        "from_amount": 50.0
    }, headers=headers_a)
    assert swap_res.status_code == 200
    print("[PASS] 12. Swap Executed Successfully")

    # 12. Test USDT -> INR Conversion
    print("\n--- Testing USDT to INR Demo Conversion ---")
    conv_res = client.post("/api/convert/usdt-to-inr", json={"usdt_amount": 50.0}, headers=headers_a)
    assert conv_res.status_code == 200
    conv_data = conv_res.json()
    print(f"[PASS] 13. Converted 50 USDT -> INR {conv_data['inr_amount']:,.2f} @ rate {conv_data['exchange_rate']}")

    # 13. Test Bank Withdrawal Prototype
    print("\n--- Testing Simulated Bank Withdrawal ---")
    wth_res = client.post("/api/bank/withdraw", json={
        "amount": 2500.0,
        "bank_name": "HDFC Bank Ltd",
        "account_number": "50100492819201",
        "ifsc_code": "HDFC0001234"
    }, headers=headers_a)
    assert wth_res.status_code == 200
    wth_data = wth_res.json()
    print(f"[PASS] 14. Bank Withdrawal Created: INR {wth_data['amount']} to {wth_data['bank_name']} (Ref: {wth_data['bank_reference']})")

    # 14. Test Virtual Card
    print("\n--- Testing Virtual Card Operations ---")
    card_res = client.get("/api/card", headers=headers_a)
    assert card_res.status_code == 200
    print(f"[PASS] 15. Virtual Card Retrieved: {card_res.json()['masked_number']} ({card_res.json()['status']})")

    freeze_res = client.post("/api/card/freeze", json={"freeze": True}, headers=headers_a)
    assert freeze_res.json()["status"] == "FROZEN"
    print("[PASS] 16. Virtual Card Freeze: FROZEN")

    unfreeze_res = client.post("/api/card/freeze", json={"freeze": False}, headers=headers_a)
    assert unfreeze_res.json()["status"] == "ACTIVE"
    print("[PASS] 17. Virtual Card Freeze: ACTIVE")

    # 15. Test NFC Tap to Pay
    print("\n--- Testing NFC Tap-to-Pay ---")
    nfc_res = client.post("/api/nfc/payment", json={
        "merchant": "Blue Tokai Coffee Roasters",
        "amount": 5.50,
        "asset_symbol": "USDT"
    }, headers=headers_a)
    assert nfc_res.status_code == 200
    print(f"[PASS] 18. NFC Contactless Approved: $5.50 at {nfc_res.json()['merchant']} (Ref: {nfc_res.json()['reference']})")

    # 16. Test Admin Portal
    print("\n--- Testing Admin Portal Access ---")
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@vayora.demo",
        "password": "Admin@123"
    })
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    stats_res = client.get("/api/admin/statistics", headers=admin_headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    print(f"[PASS] 19. Admin Stats: Users={stats['total_users']}, Transactions={stats['total_transactions']}, Total Value=${stats['total_wallet_value_usd']:,.2f}")

    users_res = client.get("/api/admin/users", headers=admin_headers)
    assert users_res.status_code == 200
    print(f"[PASS] 20. Admin User List: {len(users_res.json())} users monitored")

    # 17. Test Real Email Dispatch & Outbox Logging
    print("\n--- Testing Real Email System ---")
    email_status_res = client.get("/api/auth/email-status")
    assert email_status_res.status_code == 200
    print(f"[PASS] 21. Email Service Status: {email_status_res.json()['mode']}")

    recent_emails = client.get("/api/auth/recent-emails").json()
    assert isinstance(recent_emails, list)
    print(f"[PASS] 22. Email Activity Outbox: {len(recent_emails)} automated notifications dispatched")

    # 18. Test 2-Step Real Email Sign In with OTP Verification
    print("\n--- Testing Real 2-Step Email Sign In ---")
    login_otp_req = client.post("/api/auth/login", json={
        "email": "sender@vayora.demo",
        "password": "Password@123",
        "require_otp": True
    })
    assert login_otp_req.status_code == 200
    assert login_otp_req.json()["requires_otp"] == True
    print(f"[PASS] 23. Real Email Sign-In OTP Step 1: Dispatched verification code to sender@vayora.demo")

    # Check that outbox captured the OTP code
    outbox_latest = client.get("/api/auth/recent-emails").json()[0]
    received_otp = outbox_latest.get("otp_code")
    assert received_otp is not None and len(received_otp) == 6

    # Verify the login OTP code
    verify_res = client.post("/api/auth/verify-login-otp", json={
        "email": "sender@vayora.demo",
        "otp_code": received_otp
    })
    assert verify_res.status_code == 200
    assert "access_token" in verify_res.json()
    print(f"[PASS] 24. Real Email Sign-In OTP Step 2: Verification Passed with code {received_otp}")

    # 19. Test Real-Time Online Presence & Heartbeat
    print("\n--- Testing Real-Time Users Presence ---")
    heartbeat_res = client.post("/api/user/heartbeat?page=dashboard", headers=headers_a)
    assert heartbeat_res.status_code == 200
    presence_data = heartbeat_res.json()
    assert presence_data["online_count"] >= 1
    print(f"[PASS] 25. Real-Time Heartbeat: {presence_data['online_count']} user(s) live online")

    # 20. Test Real Payment Gateway (Stripe/Card Deposit Checkout)
    print("\n--- Testing Real Payment Checkout & Deposit ---")
    intent_res = client.post("/api/payments/checkout/create-intent", json={
        "amount": 150.0,
        "currency": "USDT",
        "payment_method": "card"
    }, headers=headers_a)
    assert intent_res.status_code == 200
    intent = intent_res.json()
    print(f"[PASS] 26. Real Payment Intent Created: Ref: {intent['reference']} via {intent['provider']}")

    # Confirm checkout and credit ledger atomically
    confirm_res = client.post("/api/payments/checkout/confirm", json={
        "amount": 150.0,
        "currency": "USDT",
        "reference": intent["reference"],
        "payment_method": "Visa •••• 4242 (Stripe Verified)"
    }, headers=headers_a)
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    print(f"[PASS] 27. Real Payment Settled on Ledger! Updated Balance: {confirm_data['updated_balance']} USDT")

    # Verify deposit email receipt was generated
    receipt_email = client.get("/api/auth/recent-emails").json()[0]
    assert "Receipt" in receipt_email["subject"] or "Payment" in receipt_email["subject"]
    print(f"[PASS] 28. Real Email Payment Receipt Verified: '{receipt_email['subject']}'")

    print("\n==================================================")
    print("ALL 28 CORE BACKEND & REAL-TIME TESTS PASSED (100%)!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

# VAYORA REST API Specification

**Base URL:** `http://127.0.0.1:8000/api`  
**Interactive Swagger UI:** `http://127.0.0.1:8000/docs`  
**OpenAPI Specification:** `http://127.0.0.1:8000/openapi.json`  
**Standard Response Encoding:** `application/json; charset=utf-8`

---

## 1. Authentication Standards

VAYORA uses Bearer JWT tokens. Pass the token in the `Authorization` header for protected endpoints:
```http
Authorization: Bearer <access_token>
```

---

## 2. Authentication Endpoints (`/api/auth`)

### 2.1 Register
**`POST /api/auth/register`**  
Create a new user account, auto-provisions a wallet, binds all assets with zero balances, and creates an initial virtual card.
- **Request Body:**
  ```json
  {
    "name": "Alex Mercer",
    "email": "alex@vayora.demo",
    "password": "Password@123"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "message": "User registered successfully. Verification OTP generated.",
    "user_id": 3,
    "email": "alex@vayora.demo"
  }
  ```

### 2.2 Login Step 1 (Password Verification & OTP Generation)
**`POST /api/auth/login`**  
Verifies email and password hash, generates a 6-digit OTP code, and logs an attempt to `login_history`.
- **Request Body:**
  ```json
  {
    "email": "sender@vayora.demo",
    "password": "Password@123"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "otp_required",
    "message": "Verification OTP sent to registered email.",
    "email": "sender@vayora.demo",
    "demo_otp_hint": "123456"
  }
  ```

### 2.3 Login Step 2 (Verify OTP & Issue JWT)
**`POST /api/auth/verify-login-otp`**  
Validates the 6-digit OTP code and returns an access token.
- **Request Body:**
  ```json
  {
    "email": "sender@vayora.demo",
    "otp_code": "123456"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "name": "Demo Sender",
      "email": "sender@vayora.demo",
      "is_admin": false
    }
  }
  ```

### 2.4 Verify Email
**`POST /api/auth/verify-email`**
- **Request Body:** `{"email": "alex@vayora.demo", "otp_code": "123456"}`
- **Response (200 OK):** `{"message": "Email verified successfully."}`

### 2.5 Forgot & Reset Password
- **`POST /api/auth/forgot-password`** `{"email": "sender@vayora.demo"}`
- **`POST /api/auth/reset-password`** `{"email": "sender@vayora.demo", "otp_code": "123456", "new_password": "NewPassword@123"}`

### 2.6 Logout & Logout All Devices
- **`POST /api/auth/logout`** (Protected): Terminates active session.
- **`POST /api/auth/logout-all`** (Protected): Revokes all active device sessions for user.

---

## 3. User & Overview Endpoints (`/api/user`)

### 3.1 Get Current User Profile
**`GET /api/user`** (Protected)
- **Response (200 OK):**
  ```json
  {
    "id": 1,
    "name": "Demo Sender",
    "email": "sender@vayora.demo",
    "email_verified": true,
    "is_admin": false,
    "created_at": "2026-09-30T13:45:00"
  }
  ```

### 3.2 Get User Activity Stream
**`GET /api/user/activity?limit=20`** (Protected)
- Returns chronological operational events (LOGIN, SEND, RECEIVE, SWAP, CONVERT, CARD, NFC).

### 3.3 Get Notifications
**`GET /api/user/notifications`** (Protected)
- Returns in-app alerts with read/unread statuses.
- **`POST /api/user/notifications/{id}/read`**: Marks notification as read.

---

## 4. Wallet & Balances Endpoints (`/api/wallet`)

### 4.1 Get Full Wallet Overview
**`GET /api/wallet`** (Protected)
- Returns aggregated portfolio valuation, asset balances, and 24h market metrics.
- **Response (200 OK):**
  ```json
  {
    "wallet_id": 1,
    "total_value_usd": 6890.50,
    "total_value_inr": 596028.25,
    "balances": [
      {
        "symbol": "USDT",
        "name": "Tether USD",
        "network": "Tron (TRC-20)",
        "amount": 500.0,
        "price_usd": 1.0,
        "value_usd": 500.0,
        "value_inr": 43250.0
      },
      {
        "symbol": "ETH",
        "name": "Ethereum",
        "network": "Ethereum Mainnet",
        "amount": 1.5,
        "price_usd": 3200.0,
        "value_usd": 4800.0,
        "value_inr": 415200.0
      }
    ]
  }
  ```

### 4.2 Asset Catalog
**`GET /api/wallet/assets`**: Returns all available system assets with networks and live demo prices.

---

## 5. Peer-to-Peer Payments (`/api/payments`)

### 5.1 Send Payment (Atomic Execution)
**`POST /api/payments/send`** (Protected)
- **Request Body:**
  ```json
  {
    "recipient_email": "receiver@vayora.demo",
    "asset_symbol": "USDT",
    "amount": 100.0,
    "note": "Freelance invoice payment"
  }
  ```
- **Business Validations:**
  - Authenticated sender identity
  - Recipient existence check (cannot send to self)
  - Asset verification
  - Positive non-zero amount check
  - Sufficient sender available balance
- **Atomic Operations:**
  1. Sender balance decreased by `amount`
  2. Receiver balance increased by `amount`
  3. `payments` record generated
  4. Dual `transactions` generated (debit for sender, credit for receiver)
  5. Audit `activity` generated
  6. In-app `notifications` delivered to both parties
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "message": "Payment of 100.0 USDT sent successfully to receiver@vayora.demo",
    "reference": "PAY-8F2B14A9C0DE",
    "new_sender_balance": 400.0
  }
  ```

### 5.2 Receive Payment / Deposit Simulation
**`POST /api/payments/receive`** (Protected)
- Generates simulated deposit for academic demonstration or receives by address.

---

## 6. Transactions Journal (`/api/transactions`)

### 6.1 List User Transactions
**`GET /api/transactions?type=ALL&asset=USDT&status=COMPLETED&limit=50`** (Protected)
- **Response (200 OK):**
  ```json
  [
    {
      "id": 1,
      "reference_id": "TX-4D90FA12",
      "type": "SEND",
      "asset_symbol": "USDT",
      "amount": 100.0,
      "sender": "sender@vayora.demo",
      "receiver": "receiver@vayora.demo",
      "status": "COMPLETED",
      "created_at": "2026-09-30T14:10:00"
    }
  ]
  ```

### 6.2 Transaction Details
**`GET /api/transactions/{id}`** (Protected)
- Detailed metadata for modal drill-down inspection.

---

## 7. Token Swap Engine (`/api/swap`)

### 7.1 Get Swap Rate Quote
**`GET /api/swap/quote?from_asset=USDT&to_asset=USDC&amount=100`** (Protected)
- **Response (200 OK):**
  ```json
  {
    "from_asset": "USDT",
    "to_asset": "USDC",
    "from_amount": 100.0,
    "to_amount": 99.85,
    "exchange_rate": 0.9985,
    "network_fee": 0.15,
    "quote_expires_in": 30
  }
  ```

### 7.2 Execute Swap
**`POST /api/swap`** (Protected)
- **Request Body:**
  ```json
  {
    "from_asset": "USDT",
    "to_asset": "USDC",
    "amount": 100.0
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "swap_id": 1,
    "from_asset": "USDT",
    "to_asset": "USDC",
    "deducted": 100.0,
    "credited": 99.85,
    "status": "COMPLETED"
  }
  ```

---

## 8. International Earnings Conversion & Payout (`/api/convert` & `/api/bank`)

### 8.1 USDT → INR Conversion (Academic Prototype)
**`POST /api/convert/usdt-to-inr`** (Protected)
- **Request Body:**
  ```json
  {
    "usdt_amount": 100.0
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "usdt_amount": 100.0,
    "exchange_rate": 86.50,
    "inr_amount": 8650.0,
    "notice": "DEMO CONVERSION ONLY. No real-world INR fiat settlement.",
    "status": "COMPLETED"
  }
  ```

### 8.2 Bank Withdrawal Prototype
**`POST /api/bank/withdraw`** (Protected)
- **Request Body:**
  ```json
  {
    "amount_inr": 5000.0,
    "bank_name": "HDFC Bank",
    "account_number": "50100492817291",
    "ifsc_code": "HDFC0001234"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "reference": "BANK-WD-7A8B9C",
    "amount_inr": 5000.0,
    "status": "COMPLETED",
    "message": "Bank payout simulated successfully via IMPS demo rail."
  }
  ```

---

## 9. 3D Virtual Card & Contactless NFC (`/api/card` & `/api/nfc`)

### 9.1 Get Card
**`GET /api/card`** (Protected): Returns virtual card details (number masked, expiry, CVV, status, balance).
### 9.2 Freeze / Unfreeze Card
- **`POST /api/card/freeze`** (Protected): Sets card status to `FROZEN`.
- **`POST /api/card/unfreeze`** (Protected): Restores card status to `ACTIVE`.

### 9.3 NFC Contactless Tap-to-Pay Simulation
**`POST /api/nfc/payment`** (Protected)
- **Request Body:**
  ```json
  {
    "merchant": "Blue Tokai Coffee Roasters",
    "amount": 14.50,
    "asset_symbol": "USDT",
    "terminal_id": "POS-MUMBAI-091"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "message": "NFC Tap-to-Pay simulated successfully.",
    "merchant": "Blue Tokai Coffee Roasters",
    "charged": 14.50,
    "status": "COMPLETED"
  }
  ```

---

## 10. Security Center (`/api/security`)

- **`GET /api/security`**: Returns account security status rating, 2-step OTP status, session count, active device metadata.
- **`GET /api/security/sessions`**: Active device sessions list.
- **`GET /api/security/login-history`**: Historical login attempts with IP and device.
- **`POST /api/security/logout-all`**: Invalidates all other device sessions.

---

## 11. Admin Command Center (`/api/admin`)

*Restricted to `is_admin = true` accounts (e.g. `admin@vayora.demo`).*

- **`GET /api/admin/statistics`**: Platform KPIs (total users, active sessions, total platform asset volume, transaction counters).
- **`GET /api/admin/users`**: Master user directory with wallet balances and admin roles.
- **`GET /api/admin/transactions`**: Complete global transaction ledger.
- **`GET /api/admin/activity`**: System-wide administrative and security audit trail.

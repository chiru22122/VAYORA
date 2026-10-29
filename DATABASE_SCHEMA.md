# VAYORA Database Schema Specification

**Platform Tagline:** *Your Digital Value, One Journey.*  
**Engine:** SQLite 3 (Production Compatible with PostgreSQL / MySQL via SQLAlchemy)  
**ORM:** SQLAlchemy 2.0  
**Design Principle:** Zero fake frontend balances. Strict relational normalization with atomic balance mutation consistency.

---

## 1. Relational Entities Summary

The VAYORA database architecture consists of **17 normalized tables** engineered specifically for a controlled fintech demonstration:

| Table Name | Primary Key | Description |
|---|---|---|
| `users` | `id` (INT) | Core user account profile, email, bcrypt password hash, verification status |
| `email_otps` | `id` (INT) | Ephemeral 6-digit authentication OTP codes for secure 2-step login |
| `wallets` | `id` (INT) | Financial wallet containers bound 1:1 to user accounts |
| `assets` | `id` (INT) | Digital asset registry (`USDT`, `USDC`, `BTC`, `ETH`, `SOL`, `INR`) with network metadata and live demo prices |
| `wallet_balances` | `id` (INT) | Atomic ledger balances per asset per wallet |
| `payments` | `id` (INT) | Internal peer-to-peer payment order records |
| `transactions` | `id` (INT) | Master immutable double-entry transaction journal records |
| `swaps` | `id` (INT) | Instant decentralized token-to-token swap records |
| `conversions` | `id` (INT) | International earnings conversion records (USDT → INR demo rate ₹86.50) |
| `bank_withdrawals` | `id` (INT) | Prototype Indian bank payout settlement requests (IMPS/NEFT) |
| `cards` | `id` (INT) | 3D virtual debit card instances (masked number, CVV, expiry, freeze controls) |
| `nfc_payments` | `id` (INT) | Simulated contactless NFC point-of-sale tap-to-pay charges |
| `activity` | `id` (INT) | User operational audit trail and security activity events |
| `notifications` | `id` (INT) | Real-time user event notifications with read/unread flags |
| `sessions` | `id` (INT) | Device session registry with IP, user-agent, and remote kill support |
| `login_history` | `id` (INT) | Historical sign-in logs with IP, user agent, timestamp, and status |
| `recovery_codes` | `id` (INT) | Hashed emergency backup account recovery codes |

> **Academic Constraint Verification:**  
> - Strictly **NO KYC** tables or verification modules.  
> - Strictly **NO Tax Records** tables or calculation modules.

---

## 2. Table Schemas & Column Definitions

### 2.1 `users`
Represents customer identity records.
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email_verified BOOLEAN DEFAULT 1,
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_users_email ON users(email);
```

### 2.2 `email_otps`
Stores time-bound verification codes for login OTP authentication.
```sql
CREATE TABLE email_otps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) NOT NULL,
    otp_code VARCHAR(6) NOT NULL,
    expires_at DATETIME NOT NULL,
    is_used BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_email_otps_email ON email_otps(email);
```

### 2.3 `wallets`
The master digital vault for a user.
```sql
CREATE TABLE wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    wallet_type VARCHAR(50) DEFAULT 'STANDARD',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.4 `assets`
Curated digital assets supported within the platform.
```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    network VARCHAR(50) NOT NULL,
    price FLOAT NOT NULL,
    icon VARCHAR(255),
    status VARCHAR(20) DEFAULT 'ACTIVE'
);
CREATE INDEX ix_assets_symbol ON assets(symbol);
```

### 2.5 `wallet_balances`
Master balance storage per asset per wallet. Guaranteed atomic mutation.
```sql
CREATE TABLE wallet_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL REFERENCES wallets(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    amount FLOAT DEFAULT 0.0 NOT NULL,
    available_amount FLOAT DEFAULT 0.0 NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_wallet_asset UNIQUE (wallet_id, asset_id)
);
```

### 2.6 `payments`
Peer-to-peer value transfer ledger between VAYORA accounts.
```sql
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    amount FLOAT NOT NULL,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    reference VARCHAR(100) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.7 `transactions`
Double-entry accounting journal displaying balance modifications.
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payment_id INTEGER REFERENCES payments(id) ON DELETE SET NULL,
    type VARCHAR(50) NOT NULL,            -- SEND, RECEIVE, SWAP, CONVERSION, CARD_PAYMENT, NFC_PAYMENT, BANK_WITHDRAWAL
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    amount FLOAT NOT NULL,
    sender VARCHAR(100),
    receiver VARCHAR(100),
    status VARCHAR(20) DEFAULT 'COMPLETED', -- PENDING, COMPLETED, FAILED, CANCELLED
    reference_id VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_transactions_reference ON transactions(reference_id);
```

### 2.8 `swaps`
Decentralized-style asset exchange executions.
```sql
CREATE TABLE swaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    from_asset_id INTEGER NOT NULL REFERENCES assets(id),
    to_asset_id INTEGER NOT NULL REFERENCES assets(id),
    from_amount FLOAT NOT NULL,
    to_amount FLOAT NOT NULL,
    rate FLOAT NOT NULL,
    fee FLOAT DEFAULT 0.0,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.9 `conversions`
Converts digital earnings (USDT) to simulated fiat valuation (INR).
```sql
CREATE TABLE conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    asset_amount FLOAT NOT NULL,
    exchange_rate FLOAT NOT NULL,         -- Default 86.50 INR per USDT
    inr_amount FLOAT NOT NULL,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.10 `bank_withdrawals`
Simulated payout workflow into regional domestic bank accounts.
```sql
CREATE TABLE bank_withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount FLOAT NOT NULL,
    bank_reference VARCHAR(100) NOT NULL,
    account_number VARCHAR(50),
    ifsc_code VARCHAR(20),
    bank_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'COMPLETED', -- PROCESSING, COMPLETED, FAILED
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.11 `cards`
3D Virtual Debit Cards issued against the user's digital asset wallet.
```sql
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    card_holder VARCHAR(120) NOT NULL,
    masked_number VARCHAR(30) NOT NULL,
    expiry VARCHAR(10) NOT NULL,
    cvv VARCHAR(4) NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, FROZEN, TERMINATED
    balance FLOAT DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.12 `nfc_payments`
Simulated point-of-sale contactless wave transactions.
```sql
CREATE TABLE nfc_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    merchant VARCHAR(120) NOT NULL,
    amount FLOAT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    status VARCHAR(20) DEFAULT 'COMPLETED',
    terminal_id VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.13 `activity`
Chronological operational and security audit logs.
```sql
CREATE TABLE activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,          -- LOGIN, SEND, RECEIVE, SWAP, CONVERT, CARD, NFC, SECURITY
    description TEXT NOT NULL,
    reference_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'SUCCESS',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.14 `notifications`
Push/in-app alert records for financial and security events.
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.15 `sessions`
Device authorization sessions with remote revocation capability.
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device VARCHAR(150) NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.16 `login_history`
Audit records of every authenticated or unauthenticated sign-in attempt.
```sql
CREATE TABLE login_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device VARCHAR(150) NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    success BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.17 `recovery_codes`
Pre-hashed single-use recovery credentials for emergency access.
```sql
CREATE TABLE recovery_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash VARCHAR(255) NOT NULL,
    used BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Data Integrity & Concurrency Rules

1. **Foreign Key Enforcement**: SQLite PRAGMA `foreign_keys = ON` is initialized on every connection pool checkout.
2. **Atomic Ledger Transactions**: Transfer of funds from sender to receiver occurs strictly inside a single database transaction block (`db.begin()` / `db.commit()`), ensuring an operation either fully completes or automatically rolls back.
3. **Double Entry Logging**: Every transfer spawns complementary records:
   - Debit transaction for sender (`type='SEND'`, negative balance delta)
   - Credit transaction for receiver (`type='RECEIVE'`, positive balance delta)
   - Immutable `payments` row capturing mutual reference UUID.

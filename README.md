# VAYORA — Your Digital Value, One Journey.

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy%202.0-d71f00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org)
[![SQLite](https://img.shields.io/badge/Database-SQLite%203-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org)
[![UI Design](https://img.shields.io/badge/Design%20Language-NEXA%20WORLD%20Futuristic%20Fintech-00f59b)](/)

> **VAYORA** is a unified digital asset and cross-border payment management platform built for freelancers, international earners, and modern digital professionals. It unifies multi-asset storage, internal peer-to-peer transfers, decentralized token swaps, simulated USDT-to-INR earnings conversion, domestic bank withdrawal prototyping, interactive 3D virtual cards, and simulated contactless NFC tap-to-pay.

---

## 🌟 Visual Identity: The NEXA WORLD UI Experience

VAYORA directly inherits the **NEXA WORLD / NexaVault** visual language:
- **Canvas**: Deep carbon and charcoal surfaces (`#070a12`, `#0b1120`, `#0f172a`).
- **Gradients & Accents**: Neon emerald (`#00f59b`), cyber cyan (`#00d2ff`), royal purple (`#a855f7`), and electric yellow (`#fbbf24`).
- **Depth & Surfaces**: Frosted glassmorphism (`backdrop-filter: blur(16px)`), micro-borders with subtle glow, and responsive cards.
- **Interactions**: Animated number count-ups, 3D virtual card tilt & flip, concentric NFC radar rings, and full `prefers-reduced-motion` compliance.

---

## ⚡ Core Value Pipeline

```text
INTERNATIONAL EARNINGS (Freelance / Remote Contracts)
       ↓
    VAYORA
       ↓
DIGITAL ASSET WALLET (USDT, USDC, BTC, ETH, SOL)
       ↓
MANAGE / SEND / RECEIVE / SWAP
       ↓
USDT → INR CONVERSION (Demo Benchmark: ₹86.50)
       ↓
BANK WITHDRAWAL PROTOTYPE (IMPS / NEFT Settlement)
       ↓
3D VIRTUAL CARD & CONTACTLESS NFC PROTOTYPE
```

---

## 🚀 Key Feature Matrix

| Feature | Description | Status |
|---|---|---|
| **Multi-Asset Wallet** | Real-time tracking of USDT, USDC, BTC, ETH, SOL, and INR balances with live demo valuations. | ✅ Complete |
| **Atomic P2P Transfer** | Instant balance updates between registered accounts with ACID guarantees and transaction journaling. | ✅ Complete |
| **Token Swap Engine** | Simulated instant decentralized swaps with live rate quotes and network fee calculations. | ✅ Complete |
| **USDT → INR Conversion** | Dedicated conversion workflow for international earners converting digital earnings to domestic currency. | ✅ Complete |
| **Bank Withdrawal** | Simulated domestic bank payout flow (IMPS/NEFT) deducting converted INR balances. | ✅ Complete |
| **3D Virtual Card** | Interactive card with dynamic 3D cursor tilt, flip interaction, and instant freeze/unfreeze controls. | ✅ Complete |
| **Contactless NFC Pay** | Simulated point-of-sale tap-to-pay with merchant detection, radar waves, and wallet debit. | ✅ Complete |
| **Security Center** | Email OTP 2-step verification, device session manager, remote kill switch, and login audit trails. | ✅ Complete |
| **Admin Command Center** | Global system health metrics, full transaction monitoring, and user registry controls. | ✅ Complete |
| **Notification Engine** | In-app push notifications for every balance change, transfer, swap, and security event. | ✅ Complete |

> **Academic Prototype Boundaries:**  
> - Strictly **NO KYC module** or verification hurdles.  
> - Strictly **NO Tax Records table** or calculation engine.  
> - Strictly **NO real-money settlement** or fiat payment processor integrations.

---

## 🔑 Demo Credentials

The database comes pre-seeded with dedicated demonstration accounts:

### 1. User A (Demo Sender)
- **Role:** Primary sender & international earner
- **Email:** `sender@vayora.demo`
- **Password:** `Password@123`
- **Login OTP:** `123456`
- **Initial Balances:** **500.00 USDT**, 250 USDC, 0.05 BTC, 1.5 ETH, 10 SOL, ₹5,000 INR

### 2. User B (Demo Receiver)
- **Role:** Recipient account for P2P transfers
- **Email:** `receiver@vayora.demo`
- **Password:** `Password@123`
- **Login OTP:** `123456`
- **Initial Balances:** **0.00 USDT**, 50 USDC, 0.01 BTC, 0.2 ETH, 1 SOL, ₹0 INR

### 3. Administrator
- **Role:** Platform Operations & Security Officer
- **Email:** `admin@vayora.demo`
- **Password:** `Admin@123`
- **Login OTP:** `123456`

---

## 🧪 Verified Demonstration Scenario (Test Case #26)

The application has been verified against the exact requirement scenario:

```text
1. Login as User A (sender@vayora.demo)
   → Dashboard loads: 500.00 USDT available

2. Navigate to Send (send.html)
   → Recipient: receiver@vayora.demo
   → Asset: USDT
   → Amount: 100.00
   → Click "Send 100 USDT"

3. Backend Execution:
   ✓ Validates sender balance (500 >= 100)
   ✓ Deducts 100 USDT from User A (Balance becomes 400.00 USDT)
   ✓ Credits 100 USDT to User B (Balance becomes 100.00 USDT)
   ✓ Creates payment record (PAY-XXXXX)
   ✓ Creates dual transaction records (SEND for User A, RECEIVE for User B)
   ✓ Logs activity audit trail
   ✓ Dispatches notification to both accounts

4. Login as User B (receiver@vayora.demo)
   → Dashboard reflects: 100.00 USDT received
   → Transactions list displays: +100.00 USDT [RECEIVED] [COMPLETED]
```

---

## 🛠️ Quick Start & Setup Instructions

### Prerequisites
- Python 3.10+ installed
- Modern web browser (Chrome, Edge, Firefox, Brave)

### 1. Installation
Clone or navigate to the project directory and install the requirements:
```bash
cd "d:\VAYORA NEW"
pip install -r requirements.txt
```

### 2. Database Initialization & Seeding (Pre-configured)
The SQLite database at `database/vayora.db` is already created and seeded. To re-seed at any point:
```bash
python database/seed.py
```

### 3. Launch the Platform
Start the unified backend and frontend server using either:

**Option A: Windows Batch Script**
```bash
start.bat
```

**Option B: Python CLI**
```bash
python run.py
```

The application will launch on:
- **Web Platform:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📁 Repository Structure

```text
VAYORA NEW/
│
├── frontend/                     # Premium NEXA WORLD UI System
│   ├── index.html                # Public Landing Page
│   ├── login.html                # 2-Step Login with OTP modal
│   ├── register.html             # Account Registration
│   ├── forgot-password.html      # Password Recovery
│   ├── dashboard.html            # Main Financial Console
│   ├── wallet.html               # Multi-Asset Vault
│   ├── portfolio.html            # Analytics & Asset Distribution
│   ├── send.html                 # P2P Transfer Terminal
│   ├── receive.html              # Address & Deposit Simulation
│   ├── swap.html                 # Decentralized Token Swap
│   ├── convert.html              # USDT → INR Earnings Conversion
│   ├── transactions.html         # Double-Entry Ledger History
│   ├── activity.html             # Audit Trail & Security Timeline
│   ├── card.html                 # 3D Virtual Debit Card
│   ├── nfc.html                  # Contactless NFC Tap-to-Pay
│   ├── security.html             # Security Dashboard & Session Revocation
│   ├── notifications.html        # Notification Alerts
│   ├── profile.html              # User Identity
│   ├── settings.html             # Preferences & Network Modes
│   ├── admin.html                # Admin Command Center
│   │
│   ├── css/
│   │   ├── global.css            # Design tokens, persistent sidebar, topbar
│   │   ├── animations.css        # Glow, radar waves, card transitions
│   │   ├── dashboard.css         # Grid layouts & portfolio cards
│   │   ├── wallet.css            # Balance tables & asset cards
│   │   └── card.css              # 3D perspective, tilt & flip styles
│   │
│   └── js/
│       ├── api.js                # HTTP client, bearer token, demo switcher
│       ├── auth.js               # Sign in, registration, OTP handlers
│       ├── dashboard.js          # Metric count-ups & charts
│       ├── wallet.js             # Asset list rendering
│       ├── payments.js           # Send/receive forms & confirmation modals
│       ├── swap.js               # Rate quoting and swap execution
│       ├── convert.js            # USDT → INR & bank withdrawal forms
│       ├── card.js               # 3D gyro/cursor tilt & freeze toggle
│       ├── nfc.js                # Contactless wave interaction
│       ├── security.js           # Session termination & password updates
│       └── admin.js              # Platform monitoring & metrics
│
├── backend/                      # High-Performance FastAPI Engine
│   ├── main.py                   # App initialization & static mount
│   ├── database.py               # SQLite engine & connection pooling
│   ├── models.py                 # 17 normalized SQLAlchemy entities
│   ├── schemas.py                # Pydantic validation models
│   ├── auth.py                   # Bcrypt hashing & PyJWT tokens
│   ├── dependencies.py           # User & Admin route guards
│   │
│   ├── routes/                   # 12 Modular REST Route Handlers
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── wallet.py
│   │   ├── payments.py
│   │   ├── transactions.py
│   │   ├── swap.py
│   │   ├── conversion.py
│   │   ├── bank.py
│   │   ├── card.py
│   │   ├── nfc.py
│   │   ├── security.py
│   │   └── admin.py
│   │
│   └── services/                 # Atomic Business Logic Services
│       ├── payment_service.py    # Atomic transfers & double-entry ledger
│       ├── wallet_service.py     # Real-time portfolio valuations
│       ├── swap_service.py       # Liquidity quotes & swap settlement
│       ├── conversion_service.py # USDT → INR & bank payout handling
│       └── security_service.py   # Sessions, audit logs & OTPs
│
├── database/
│   ├── vayora.db                 # Seeded SQLite database
│   └── seed.py                   # Database generator script
│
├── test_backend.py               # 20 Automated Integration Tests
├── run.py                        # Python server launcher
├── start.bat                     # Windows 1-click startup batch file
├── README.md                     # Master project documentation
├── DATABASE_SCHEMA.md            # Detailed schema definitions
├── API_DOCUMENTATION.md          # REST API endpoint reference
├── ARCHITECTURE.md               # System design & ER diagram
├── requirements.txt              # Production Python dependencies
└── .env                          # Environment secrets configuration
```

---

## 🛡️ Security Architecture

1. **Password Hashing**: Passwords stored using industry-standard `bcrypt` with salt rounds.
2. **Stateless JWT Authentication**: Tokens issued using `HS256` with expiration windows and user identification payloads.
3. **Two-Step Email OTP**: Mandatory 6-digit code verification on sign-in attempts.
4. **Session Monitoring**: Every login logs device user-agent and IP with remote single-click session revocation.
5. **Server-Side Authorization**: Route-level dependency guards prevent users from reading or manipulating balances belonging to other accounts.
6. **Double-Entry Balance Integrity**: Financial balances mutate strictly within server-side ACID database transactions.

---

## 📄 License & Academic Note

This software was engineered as a comprehensive fintech demonstration. It models real-world enterprise software patterns (RESTful micro-routers, atomic ledger commits, reactive UI design systems) while maintaining strict sandbox isolation from real-world payment networks and monetary clearinghouses.

# VAYORA System Architecture Specification

**Product Identity:** VAYORA  
**Tagline:** *Your Digital Value, One Journey.*  
**Design Paradigm:** NEXA WORLD / NexaVault Futuristic Dark Fintech  
**Platform Type:** Unified Digital Asset & Cross-Border Payment Management Operating System (Controlled Academic / Demo Prototype)

---

## 1. System Vision & Core Value Pipeline

International earners, remote professionals, and digital freelancers receive remuneration across diverse currencies and networks. Traditional banking rails subject them to excessive intermediary fees, delayed settlements, and disjointed digital tooling.

VAYORA resolves this fragmentation through a unified multi-asset digital hub:

```mermaid
flowchart TD
    IE[International Earnings / Client Invoices] --> VAYORA[VAYORA Core Hub]
    VAYORA --> VAULT[Digital Asset Vault\nUSDT • USDC • BTC • ETH • SOL]
    
    VAULT --> P2P[Peer-to-Peer Transfer\nInstant Atomic Internal Transfer]
    VAULT --> SWAP[Decentralized Token Swap\nZero Slippage Execution]
    VAULT --> CONV[USDT to INR Conversion Engine\nDemo Benchmark: ₹86.50]
    
    CONV --> BANK[Bank Withdrawal Prototype\nIMPS / NEFT Simulated Payout]
    VAULT --> CARD[3D Virtual Debit Card\nReal-time Asset Backed Card]
    VAULT --> NFC[Contactless NFC Tap-to-Pay\nSimulated Point-of-Sale Waves]

    style VAYORA fill:#0b1120,stroke:#00f59b,stroke-width:3px,color:#fff
    style VAULT fill:#0f172a,stroke:#00d2ff,stroke-width:2px,color:#fff
    style CONV fill:#1e1b4b,stroke:#a855f7,stroke-width:2px,color:#fff
    style CARD fill:#064e3b,stroke:#00f59b,stroke-width:2px,color:#fff
    style NFC fill:#312e81,stroke:#00d2ff,stroke-width:2px,color:#fff
```

---

## 2. Architectural Layers

VAYORA is engineered with high separation of concerns across 4 distinct layers:

### 2.1 Presentation Layer (NEXA WORLD UI System)
- **Design Tokens**: Neon Emerald (`#00f59b`), Cyber Cyan (`#00d2ff`), Royal Purple (`#a855f7`), Electric Yellow (`#fbbf24`), Carbon Slate (`#0a0f1d`), Soft Glass (`rgba(255,255,255,0.03)`).
- **Component Architecture**: Persistent glowing sidebar with responsive collapsing, topbar status bar with real-time demo account switcher (`Demo Sender` / `Demo Receiver` / `Admin`), animated metric counters, interactive 3D card tilt & flip, and concentric NFC radar waves.
- **Accessibility & Motion**: Seamless support for standard CSS transitions paired with strict `prefers-reduced-motion` compliance.

### 2.2 API & Application Gateway Layer (FastAPI)
- **Authentication Gateway**: High-speed JWT issuing, Bcrypt password hashing, and 2-step email OTP verification.
- **Modular Routers**: 12 dedicated route modules (`auth`, `user`, `wallet`, `payments`, `transactions`, `swap`, `conversion`, `bank`, `card`, `nfc`, `security`, `admin`).
- **Dependency Injection**: Centralized database session handling and token parsing via `get_current_user` and `require_admin`.

### 2.3 Business Logic & Service Layer
- **`PaymentService`**: Dual-entry balance updates, verification of recipient existence, self-transfer guards, and atomic transaction persistence.
- **`WalletService`**: Real-time asset aggregation, live demo price multipliers, and portfolio valuation calculations.
- **`ConversionService`**: Safe simulated fiat calculations (USDT → INR) and prototype bank withdrawal validation.1
- **`SwapService`**: Dynamic quote generation and bi-directional atomic asset swaps.
- **`SecurityService`**: Session revocation, activity journaling, and suspicious login logging.

### 2.4 Persistence Layer (SQLAlchemy 2.0 & Relational SQLite)
- **Normalization**: 17 relational entities.
- **ACID Transactions**: Atomic commits guarantee that sender deduction and receiver credit occur together or fail completely.

---

## 3. Entity Relationship (ER) Diagram

```mermaid
erDiagram
    USERS ||--|| WALLETS : owns
    USERS ||--o{ CARDS : holds
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ ACTIVITY : logs
    USERS ||--o{ SESSIONS : establishes
    USERS ||--o{ LOGIN_HISTORY : records
    USERS ||--o{ RECOVERY_CODES : holds
    USERS ||--o{ EMAIL_OTPS : requests
    
    WALLETS ||--|{ WALLET_BALANCES : contains
    ASSETS ||--|{ WALLET_BALANCES : tracks
    
    USERS ||--o{ PAYMENTS : initiates
    USERS ||--o{ PAYMENTS : receives
    ASSETS ||--o{ PAYMENTS : denomination
    
    USERS ||--o{ TRANSACTIONS : journalizes
    PAYMENTS ||--o{ TRANSACTIONS : references
    ASSETS ||--o{ TRANSACTIONS : denom
    
    USERS ||--o{ SWAPS : executes
    ASSETS ||--o{ SWAPS : source_asset
    ASSETS ||--o{ SWAPS : target_asset
    
    USERS ||--o{ CONVERSIONS : converts
    ASSETS ||--o{ CONVERSIONS : digital_asset
    
    USERS ||--o{ BANK_WITHDRAWALS : withdraws
    USERS ||--o{ NFC_PAYMENTS : taps
    ASSETS ||--o{ NFC_PAYMENTS : debited_asset

    USERS {
        int id PK
        string name
        string email UK
        string password_hash
        boolean email_verified
        boolean is_admin
        datetime created_at
    }

    WALLETS {
        int id PK
        int user_id FK
        string wallet_type
        datetime created_at
    }

    ASSETS {
        int id PK
        string symbol UK
        string name
        string network
        float price
        string status
    }

    WALLET_BALANCES {
        int id PK
        int wallet_id FK
        int asset_id FK
        float amount
        float available_amount
        datetime updated_at
    }

    PAYMENTS {
        int id PK
        int sender_id FK
        int receiver_id FK
        int asset_id FK
        float amount
        string status
        string reference UK
        datetime created_at
    }

    TRANSACTIONS {
        int id PK
        int user_id FK
        int payment_id FK
        string type
        int asset_id FK
        float amount
        string sender
        string receiver
        string status
        string reference_id
        datetime created_at
    }

    CARDS {
        int id PK
        int user_id FK
        string card_holder
        string masked_number
        string expiry
        string cvv
        string status
        float balance
    }
```

---

## 4. Controlled Academic / Demo Prototype Boundaries

VAYORA explicitly differentiates between **production-grade software engineering** and **simulated financial infrastructure**:

| Platform Component | Technical Implementation | Demo / Academic Prototype Constraint |
|---|---|---|
| **Identity & Access** | Bcrypt hash + JWT tokens + 6-digit Email OTP | Academic test bypass: OTP `123456` or database-seeded OTPs |
| **Asset Balances** | Relational database atomic commits with transaction rollback | Simulated assets (USDT, USDC, BTC, ETH, SOL) with static/demo pricing |
| **Peer-to-Peer Transfer** | Full double-entry ledgering and validation | Occurs exclusively between registered internal VAYORA users |
| **USDT → INR Conversion** | Mathematical conversion with atomic deduction & INR balance credit | Demo exchange rate (₹86.50). **No actual banking settlement or FX clearing.** |
| **Bank Withdrawal** | Input validation (IFSC, Account number), balance debit, state progression | Simulated IMPS/NEFT payout rail without real SWIFT or RBI gateway |
| **Virtual Card** | Full 3D tilt/flip CSS, card freeze/unfreeze state mutations | Simulated BIN and card generation without real payment network (Visa/Mastercard) |
| **NFC Contactless** | Interactive POS animation and automated wallet debit | Simulated browser-based NFC terminal communication |
| **Compliance & Regulation** | Clean user directory and activity audit logs | **Strictly NO KYC verification module** and **Strictly NO Tax Records table** |

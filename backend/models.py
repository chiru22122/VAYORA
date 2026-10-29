import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Index, Numeric
)
from sqlalchemy.orm import relationship
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    role = Column(String(20), default="user", nullable=False)  # 'user' or 'admin'
    phone = Column(String(30), nullable=True)
    avatar_color = Column(String(20), default="#00f59b", nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="user", cascade="all, delete-orphan")
    sent_payments = relationship("Payment", foreign_keys="[Payment.sender_id]", back_populates="sender")
    received_payments = relationship("Payment", foreign_keys="[Payment.receiver_id]", back_populates="receiver")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    swaps = relationship("Swap", back_populates="user", cascade="all, delete-orphan")
    conversions = relationship("Conversion", back_populates="user", cascade="all, delete-orphan")
    bank_withdrawals = relationship("BankWithdrawal", back_populates="user", cascade="all, delete-orphan")
    nfc_payments = relationship("NFCPayment", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    login_history = relationship("LoginHistory", back_populates="user", cascade="all, delete-orphan")
    recovery_codes = relationship("RecoveryCode", back_populates="user", cascade="all, delete-orphan")
    token_addresses = relationship("TokenAddress", back_populates="user", cascade="all, delete-orphan")


class Wallet(Base):
    __tablename__ = "wallets"

    wallet_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    wallet_type = Column(String(50), default="MAIN", nullable=False)
    address = Column(String(100), unique=True, index=True, nullable=False)
    inr_balance_paise = Column(BigInteger, default=0, nullable=False)  # Stored strictly in integer paise (1 INR = 100 paise)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    @property
    def inr_balance(self) -> float:
        return (self.inr_balance_paise or 0) / 100.0

    @inr_balance.setter
    def inr_balance(self, value: float):
        self.inr_balance_paise = int(round(float(value or 0) * 100))

    # Relationships
    user = relationship("User", back_populates="wallets")
    balances = relationship("WalletBalance", back_populates="wallet", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    symbol = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    network = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)  # Demo USD price
    icon = Column(String(50), nullable=False)  # Token icon tag/symbol
    status = Column(String(20), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    balances = relationship("WalletBalance", back_populates="asset")


class WalletBalance(Base):
    __tablename__ = "wallet_balances"

    balance_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    wallet_id = Column(Integer, ForeignKey("wallets.wallet_id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False, index=True)
    amount = Column(Numeric(18, 6), default=Decimal('0.0'), nullable=False)
    available_amount = Column(Numeric(18, 6), default=Decimal('0.0'), nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("wallet_id", "asset_id", name="uq_wallet_asset"),
    )

    # Relationships
    wallet = relationship("Wallet", back_populates="balances")
    asset = relationship("Asset", back_populates="balances")


class TokenAddress(Base):
    __tablename__ = "token_addresses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    asset_symbol = Column(String(20), nullable=False, index=True)  # USDT, USDC, BTC, ETH, SOL, INR
    network = Column(String(50), nullable=False)                   # TRC-20, Native SegWit, ERC-20, SPL, UPI
    address = Column(String(120), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "asset_symbol", name="uq_user_token_address"),
    )

    # Relationships
    user = relationship("User", back_populates="token_addresses")


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    sender_address = Column(String(120), nullable=True)
    receiver_address = Column(String(120), nullable=True)
    status = Column(String(20), default="COMPLETED", nullable=False)  # COMPLETED, PENDING, FAILED
    reference = Column(String(64), unique=True, index=True, nullable=False)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_payments")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_payments")
    asset = relationship("Asset")
    transactions = relationship("Transaction", back_populates="payment")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.payment_id"), nullable=True, index=True)
    type = Column(String(30), nullable=False)  # SEND, RECEIVE, SWAP, CONVERSION, CARD_PAYMENT, NFC_PAYMENT, BANK_WITHDRAWAL
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=True)
    amount = Column(Float, nullable=False)
    sender = Column(String(255), nullable=True)
    receiver = Column(String(255), nullable=True)
    sender_address = Column(String(120), nullable=True)
    receiver_address = Column(String(120), nullable=True)
    status = Column(String(20), default="COMPLETED", nullable=False)  # COMPLETED, PENDING, FAILED, CANCELLED
    reference_id = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="transactions")
    payment = relationship("Payment", back_populates="transactions")
    asset = relationship("Asset")



class Swap(Base):
    __tablename__ = "swaps"

    swap_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    from_asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    to_asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    from_amount = Column(Float, nullable=False)
    to_amount = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    fee = Column(Float, default=0.0, nullable=False)
    status = Column(String(20), default="COMPLETED", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="swaps")
    from_asset = relationship("Asset", foreign_keys=[from_asset_id])
    to_asset = relationship("Asset", foreign_keys=[to_asset_id])


class Conversion(Base):
    __tablename__ = "conversions"

    conversion_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    asset_amount = Column(Float, nullable=False)
    exchange_rate = Column(Float, nullable=False)  # e.g., 86.50 INR per USDT
    inr_amount = Column(Float, nullable=False)
    status = Column(String(20), default="COMPLETED", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="conversions")
    asset = relationship("Asset")


class BankWithdrawal(Base):
    __tablename__ = "bank_withdrawals"

    withdrawal_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)  # in INR
    bank_name = Column(String(100), nullable=False)
    account_number = Column(String(50), nullable=False)
    ifsc_code = Column(String(20), nullable=False)
    bank_reference = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(20), default="COMPLETED", nullable=False)  # PROCESSING, COMPLETED, FAILED
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="bank_withdrawals")


class Card(Base):
    __tablename__ = "cards"

    card_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    cardholder_name = Column(String(100), nullable=False)
    masked_number = Column(String(30), nullable=False)
    full_number = Column(String(30), nullable=False)
    expiry = Column(String(10), nullable=False)  # MM/YY
    cvv = Column(String(10), nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, FROZEN
    balance = Column(Float, default=1500.0, nullable=False)
    daily_limit = Column(Float, default=5000.0, nullable=False)
    card_tier = Column(String(30), default="BLACK OBSIDIAN", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="cards")


class NFCPayment(Base):
    __tablename__ = "nfc_payments"

    nfc_payment_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    merchant = Column(String(150), nullable=False)
    amount = Column(Float, nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=True)
    status = Column(String(20), default="COMPLETED", nullable=False)
    reference = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="nfc_payments")
    asset = relationship("Asset")


class Activity(Base):
    __tablename__ = "activity"

    activity_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # LOGIN, SEND, RECEIVE, SWAP, CONVERT, CARD, NFC, SECURITY
    description = Column(Text, nullable=False)
    reference_id = Column(String(64), nullable=True)
    ip_address = Column(String(50), default="127.0.0.1", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="activities")


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(30), default="INFO", nullable=False)  # PAYMENT, SWAP, SECURITY, SYSTEM
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    token_id = Column(String(64), unique=True, index=True, nullable=False)
    device = Column(String(150), nullable=False)
    ip_address = Column(String(50), default="127.0.0.1", nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, REVOKED
    last_active = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")


class LoginHistory(Base):
    __tablename__ = "login_history"

    login_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    device = Column(String(150), nullable=False)
    ip_address = Column(String(50), default="127.0.0.1", nullable=False)
    success = Column(Boolean, default=True, nullable=False)
    reason = Column(String(100), default="Success", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="login_history")


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    recovery_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="recovery_codes")


class EmailOTP(Base):
    __tablename__ = "email_otps"

    otp_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    otp_code = Column(String(10), nullable=False)
    otp_type = Column(String(30), nullable=False)  # verify_email, login_otp, reset_password
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


# ==============================================================================
# AUTHORITATIVE DOUBLE-ENTRY FINANCIAL LEDGER MODELS (ACID & AUDIT COMPLIANT)
# ==============================================================================

class Account(Base):
    """
    Authoritative currency account per user.
    Maintains exact integer paise for INR and exact Decimal for USDT/crypto.
    """
    __tablename__ = "accounts"

    account_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    currency = Column(String(10), nullable=False)  # 'USDT', 'INR', 'USDC', 'BTC', 'ETH', 'SOL'
    account_number = Column(String(64), unique=True, index=True, nullable=False)
    balance = Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    available_balance = Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    balance_paise = Column(BigInteger, default=0, nullable=False)  # For INR: strictly integer paise
    status = Column(String(20), default="ACTIVE", nullable=False)  # 'ACTIVE', 'FROZEN'
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_user_currency"),
        Index("idx_accounts_user_currency", "user_id", "currency"),
    )

    # Relationships
    user = relationship("User", back_populates="accounts")
    entries = relationship("LedgerEntry", back_populates="account")


class LedgerTransaction(Base):
    """
    Authoritative operations record representing an atomic financial transaction.
    """
    __tablename__ = "ledger_transactions"

    transaction_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    reference = Column(String(64), unique=True, index=True, nullable=False)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=True)
    type = Column(String(50), nullable=False)  # 'TRANSFER', 'SWAP', 'CONVERSION', 'DEPOSIT', 'WITHDRAWAL', 'NFC_PAYMENT'
    description = Column(Text, nullable=False)
    status = Column(String(20), default="COMPLETED", nullable=False)  # 'COMPLETED', 'FAILED', 'REVERSED'
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    entries = relationship("LedgerEntry", back_populates="transaction", cascade="all, delete-orphan")


class LedgerEntry(Base):
    """
    Immutable double-entry debits and credits.
    For every transaction, sum(DEBIT) == sum(CREDIT) for each currency.
    """
    __tablename__ = "ledger_entries"

    entry_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ledger_transaction_id = Column(Integer, ForeignKey("ledger_transactions.transaction_id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    currency = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)  # 'DEBIT', 'CREDIT'
    amount = Column(Numeric(20, 8), nullable=False)
    amount_paise = Column(BigInteger, default=0, nullable=False)  # For INR: integer paise
    balance_after = Column(Numeric(20, 8), nullable=False)
    balance_after_paise = Column(BigInteger, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    transaction = relationship("LedgerTransaction", back_populates="entries")
    account = relationship("Account", back_populates="entries")
    user = relationship("User")


class Transfer(Base):
    """
    Authoritative peer-to-peer internal transfer record.
    """
    __tablename__ = "transfers"

    transfer_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    reference = Column(String(64), unique=True, index=True, nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    sender_account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    recipient_account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False)
    currency = Column(String(10), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    amount_paise = Column(BigInteger, default=0, nullable=False)
    fee = Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    note = Column(String(255), nullable=True)
    status = Column(String(20), default="COMPLETED", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    sender = relationship("User", foreign_keys=[sender_user_id])
    recipient = relationship("User", foreign_keys=[recipient_user_id])
    sender_account = relationship("Account", foreign_keys=[sender_account_id])
    recipient_account = relationship("Account", foreign_keys=[recipient_account_id])


class AuditLog(Base):
    """
    Tamper-evident security and financial audit trail.
    """
    __tablename__ = "audit_logs"

    log_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=False)
    ip_address = Column(String(50), default="127.0.0.1", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User")


class EmailOutbox(Base):
    """
    Durable transactional email outbox for guaranteed delivery tracking.
    """
    __tablename__ = "email_outbox"

    outbox_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    to_email = Column(String(255), index=True, nullable=False)
    subject = Column(String(255), nullable=False)
    template = Column(String(100), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    otp_code = Column(String(20), nullable=True)
    status = Column(String(20), default="QUEUED", nullable=False)  # 'SENT', 'QUEUED', 'FAILED'
    error_message = Column(Text, nullable=True)
    delivery_attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)


from fastapi.openapi.models import EmailStr
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_serializer

def serialize_datetime(dt: Optional[datetime.datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()

# --- AUTH SCHEMAS ---

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str
    password: str = Field(..., min_length=6, max_length=100)
    phone: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: str
    password: str
    otp_code: Optional[str] = None
    require_otp: Optional[bool] = None
    device_info: Optional[str] = "Web Browser / Desktop"

class ResendOTPRequest(BaseModel):
    email: str
    otp_type: str = "login_otp"

class VerifyEmailRequest(BaseModel):
    email: str
    otp_code: str = Field(..., min_length=4, max_length=10)

class VerifyLoginOTPRequest(BaseModel):
    email: str
    otp_code: str = Field(..., min_length=4, max_length=10)
    device_info: Optional[str] = "Web Browser / Desktop"

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp_code: str
    new_password: str = Field(..., min_length=6, max_length=100)

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=100)

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None

class UserResponse(BaseModel):
    user_id: int
    name: str
    email: str
    email_verified: bool
    role: str
    phone: Optional[str] = None
    avatar_color: Optional[str] = "#00f59b"
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    requires_otp: bool = False
    email: Optional[str] = None
    message: Optional[str] = None

# --- ASSET & WALLET SCHEMAS ---

class AssetResponse(BaseModel):
    asset_id: int
    symbol: str
    name: str
    network: str
    price: float
    icon: str
    status: str

    class Config:
        from_attributes = True

class BalanceResponse(BaseModel):
    balance_id: int
    asset_id: int
    symbol: str
    name: str
    network: str
    price: float
    amount: float
    available_amount: float
    usd_value: float
    inr_value: float
    icon: str
    deposit_address: Optional[str] = None
    qr_uri: Optional[str] = None
    updated_at: datetime.datetime

class TokenAddressResponse(BaseModel):
    symbol: str
    name: str
    network: str
    standard: str
    address: str
    qr_uri: str
    min_deposit: str
    confirmations: int
    fee: str
    avg_time: str
    contract: Optional[str] = None
    updated_at: Optional[str] = None

class WalletResponse(BaseModel):
    wallet_id: int
    address: str
    wallet_type: str
    inr_balance: float
    total_usd_value: float
    total_inr_value: float
    balances: List[BalanceResponse]
    token_addresses: Optional[Dict[str, str]] = None

# --- PAYMENT SCHEMAS ---

class SendPaymentRequest(BaseModel):
    recipient: str = Field(..., description="Recipient email address, wallet address, or token address")
    asset_symbol: str = Field(..., description="Asset symbol e.g. USDT, BTC")
    amount: float = Field(..., gt=0, description="Amount to send")
    note: Optional[str] = Field(None, max_length=255)
    idempotency_key: Optional[str] = Field(None, description="Optional client idempotency key to prevent duplicate transfers")

class PaymentResponse(BaseModel):
    payment_id: int
    reference: str
    sender_email: str
    receiver_email: str
    sender_address: Optional[str] = None
    receiver_address: Optional[str] = None
    asset_symbol: str
    amount: float
    status: str
    note: Optional[str] = None
    created_at: datetime.datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime.datetime, _info):
        return serialize_datetime(dt)

class ReceiveSimulateRequest(BaseModel):
    sender_email: Optional[str] = "settlement@vayora.network"
    sender_address: Optional[str] = None
    asset_symbol: str = "USDT"
    amount: float = Field(..., gt=0)
    note: Optional[str] = None

# --- TRANSACTION SCHEMAS ---

class TransactionResponse(BaseModel):
    transaction_id: int
    type: str
    asset_symbol: Optional[str] = None
    amount: float
    sender: Optional[str] = None
    receiver: Optional[str] = None
    sender_address: Optional[str] = None
    receiver_address: Optional[str] = None
    status: str
    reference_id: str
    created_at: datetime.datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime.datetime, _info):
        return serialize_datetime(dt)

    class Config:
        from_attributes = True

# --- SWAP SCHEMAS ---

class SwapQuoteRequest(BaseModel):
    from_symbol: str
    to_symbol: str
    from_amount: float = Field(..., gt=0)

class SwapQuoteResponse(BaseModel):
    from_symbol: str
    to_symbol: str
    from_amount: float
    to_amount: float
    rate: float
    fee: float
    network_fee_usd: float = 0.0
    expires_in_seconds: int = 60

class SwapExecuteRequest(BaseModel):
    from_symbol: str
    to_symbol: str
    from_amount: float = Field(..., gt=0)

class SwapResponse(BaseModel):
    swap_id: int
    from_symbol: str
    to_symbol: str
    from_amount: float
    to_amount: float
    rate: float
    fee: float
    status: str
    created_at: datetime.datetime

# --- CONVERSION SCHEMAS ---

class LiveRateResponse(BaseModel):
    rate: float
    currency_pair: str = "USDT/INR"
    base_currency: str = "USDT"
    quote_currency: str = "INR"
    change_24h: Optional[float] = 0.0
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    source: str
    cached: bool = False
    last_updated: str
    benchmark_demo_rate: float
    server_time: str

class ConvertUSDTRequest(BaseModel):
    usdt_amount: float = Field(..., gt=0)
    rate: Optional[float] = Field(None, gt=0, description="Optional verified live rate quote from client")

class ConversionResponse(BaseModel):
    conversion_id: int
    asset_symbol: str = "USDT"
    asset_amount: float
    exchange_rate: float
    inr_amount: float
    status: str
    created_at: datetime.datetime

class ConversionChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="User conversational prompt")

class ConversionChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None
    usdt_amount: Optional[float] = None
    rate: Optional[float] = None
    inr_amount: Optional[float] = None
    source: Optional[str] = None
    suggested_questions: Optional[List[str]] = None

# --- BANK WITHDRAWAL SCHEMAS ---

class BankWithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in INR")
    bank_name: str = Field(..., min_length=2, max_length=100)
    account_number: str = Field(..., min_length=6, max_length=30)
    ifsc_code: str = Field(..., min_length=6, max_length=15)

class BankWithdrawalResponse(BaseModel):
    withdrawal_id: int
    amount: float
    bank_name: str
    account_number: str
    ifsc_code: str
    bank_reference: str
    status: str
    created_at: datetime.datetime

# --- VIRTUAL CARD SCHEMAS ---

class CardResponse(BaseModel):
    card_id: int
    cardholder_name: str
    masked_number: str
    full_number: str
    expiry: str
    cvv: str
    status: str
    balance: float
    daily_limit: float
    card_tier: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class CardFreezeRequest(BaseModel):
    freeze: bool

class CardSimulatePaymentRequest(BaseModel):
    merchant: str = Field(..., min_length=2, max_length=100)
    amount: float = Field(..., gt=0)

# --- NFC SCHEMAS ---

class NFCPaymentRequest(BaseModel):
    merchant: str = Field(..., min_length=2, max_length=100)
    amount: float = Field(..., gt=0)
    asset_symbol: Optional[str] = "USDT"

class NFCPaymentResponse(BaseModel):
    nfc_payment_id: int
    merchant: str
    amount: float
    asset_symbol: str
    status: str
    reference: str
    created_at: datetime.datetime

# --- SECURITY & ACTIVITY SCHEMAS ---

class SessionResponse(BaseModel):
    session_id: int
    device: str
    ip_address: str
    status: str
    last_active: datetime.datetime
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class LoginHistoryResponse(BaseModel):
    login_id: int
    device: str
    ip_address: str
    success: bool
    reason: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class SecurityOverviewResponse(BaseModel):
    email_verified: bool
    security_score: int
    active_sessions_count: int
    recent_logins: List[LoginHistoryResponse]
    recovery_codes_count: int

class ActivityResponse(BaseModel):
    activity_id: int
    action: str
    description: str
    reference_id: Optional[str] = None
    ip_address: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    notification_id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- ADMIN SCHEMAS ---

class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_wallet_value_usd: float
    total_transactions: int
    completed_transactions: int
    failed_transactions: int
    total_volume_usd: float
    system_status: str = "OPTIMAL"

class AdminUserListItem(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    email_verified: bool
    created_at: datetime.datetime
    wallet_address: str
    total_usd_value: float
    inr_balance: float

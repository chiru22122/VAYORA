from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Payment
from backend.schemas import SendPaymentRequest, PaymentResponse, ReceiveSimulateRequest
from backend.dependencies import get_current_user
from backend.services.payment_service import execute_send_payment

router = APIRouter(prefix="/api/payments", tags=["Payments"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("/send", response_model=PaymentResponse)
def send_payment(
    req: SendPaymentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    payment = execute_send_payment(
        db=db,
        sender=current_user,
        recipient_identifier=req.recipient,
        asset_symbol=req.asset_symbol,
        amount=req.amount,
        note=req.note,
        idempotency_key=req.idempotency_key,
        ip_address=ip
    )
    
    sender_user = db.query(User).filter(User.user_id == payment.sender_id).first()
    receiver_user = db.query(User).filter(User.user_id == payment.receiver_id).first()
    
    return PaymentResponse(
        payment_id=payment.payment_id,
        reference=payment.reference,
        sender_email=sender_user.email if sender_user else "Unknown",
        receiver_email=receiver_user.email if receiver_user else "Unknown",
        sender_address=payment.sender_address,
        receiver_address=payment.receiver_address,
        asset_symbol=req.asset_symbol.upper(),
        amount=payment.amount,
        status=payment.status,
        note=payment.note,
        created_at=payment.created_at
    )

@router.post("/receive", response_model=PaymentResponse)
def simulate_receive(
    req: ReceiveSimulateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Simulate receiving from another VAYORA user or external crypto address."""
    from decimal import Decimal
    from backend.auth import hash_password
    import datetime
    from backend.models import Account
    from backend.services.payment_service import ensure_user_accounts

    # Find counterparty sender
    sender_user = None
    if req.sender_email:
        sender_user = db.query(User).filter(User.email.ilike(req.sender_email.strip())).first()

    # If not found or same as current user, resolve a valid settlement counterparty
    if not sender_user or sender_user.user_id == current_user.user_id:
        sender_user = db.query(User).filter(User.email == "settlement@vayora.network").first()
        if not sender_user:
            sender_user = User(
                name="VAYORA Settlement Network",
                email="settlement@vayora.network",
                password_hash=hash_password("SettlementPass123!"),
                email_verified=True,
                role="system",
                phone="+1 (800) 555-0199",
                avatar_color="#00f59b",
                created_at=datetime.datetime.utcnow()
            )
            db.add(sender_user)
            db.flush()

    # Auto-fund the simulation sender so the incoming deposit simulation is 100% reliable
    curr = req.asset_symbol.upper().strip()
    ensure_user_accounts(db, sender_user)
    sender_acct = db.query(Account).filter(Account.user_id == sender_user.user_id, Account.currency == curr).first()
    req_amt_dec = Decimal(f"{req.amount:.6f}")

    if curr == "INR":
        req_paise = int(round(req.amount * 100))
        if not sender_acct or (sender_acct.balance_paise or 0) < req_paise:
            if not sender_acct:
                ensure_user_accounts(db, sender_user)
                sender_acct = db.query(Account).filter(Account.user_id == sender_user.user_id, Account.currency == curr).first()
            sender_acct.balance_paise = max(sender_acct.balance_paise or 0, req_paise * 20)
            sender_acct.balance = Decimal(str(sender_acct.balance_paise / 100.0))
            sender_acct.available_balance = sender_acct.balance
            db.flush()
    else:
        if not sender_acct or sender_acct.available_balance < req_amt_dec:
            if not sender_acct:
                ensure_user_accounts(db, sender_user)
                sender_acct = db.query(Account).filter(Account.user_id == sender_user.user_id, Account.currency == curr).first()
            sender_acct.balance = max(sender_acct.balance, req_amt_dec * Decimal("20"))
            sender_acct.available_balance = sender_acct.balance
            db.flush()

    ip = get_client_ip(request)
    payment = execute_send_payment(
        db=db,
        sender=sender_user,
        recipient_identifier=current_user.email,
        asset_symbol=req.asset_symbol,
        amount=req.amount,
        note=req.note or f"Incoming {req.asset_symbol.upper()} deposit confirmation",
        ip_address=ip
    )

    return PaymentResponse(
        payment_id=payment.payment_id,
        reference=payment.reference,
        sender_email=sender_user.email,
        receiver_email=current_user.email,
        sender_address=payment.sender_address,
        receiver_address=payment.receiver_address,
        asset_symbol=req.asset_symbol.upper(),
        amount=payment.amount,
        status=payment.status,
        note=payment.note,
        created_at=payment.created_at
    )

@router.get("", response_model=List[PaymentResponse])
def list_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    payments = db.query(Payment).filter(
        (Payment.sender_id == current_user.user_id) | (Payment.receiver_id == current_user.user_id)
    ).order_by(Payment.created_at.desc()).limit(100).all()

    result = []
    for p in payments:
        s_user = db.query(User).filter(User.user_id == p.sender_id).first()
        r_user = db.query(User).filter(User.user_id == p.receiver_id).first()
        asset_sym = p.asset.symbol if p.asset else "INR"
        result.append(PaymentResponse(
            payment_id=p.payment_id,
            reference=p.reference,
            sender_email=s_user.email if s_user else "Unknown",
            receiver_email=r_user.email if r_user else "Unknown",
            sender_address=p.sender_address,
            receiver_address=p.receiver_address,
            asset_symbol=asset_sym,
            amount=p.amount,
            status=p.status,
            note=p.note,
            created_at=p.created_at
        ))
    return result

@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    p = db.query(Payment).filter(
        Payment.payment_id == payment_id,
        (Payment.sender_id == current_user.user_id) | (Payment.receiver_id == current_user.user_id)
    ).first()

    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    s_user = db.query(User).filter(User.user_id == p.sender_id).first()
    r_user = db.query(User).filter(User.user_id == p.receiver_id).first()

    return PaymentResponse(
        payment_id=p.payment_id,
        reference=p.reference,
        sender_email=s_user.email if s_user else "Unknown",
        receiver_email=r_user.email if r_user else "Unknown",
        sender_address=p.sender_address,
        receiver_address=p.receiver_address,
        asset_symbol=p.asset.symbol if p.asset else "INR",
        amount=p.amount,
        status=p.status,
        note=p.note,
        created_at=p.created_at
    )


import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Asset, WalletBalance, NFCPayment, Transaction, Activity, Notification
from backend.schemas import NFCPaymentRequest, NFCPaymentResponse
from backend.dependencies import get_current_user
from backend.auth import generate_reference
from backend.services.wallet_service import get_or_create_wallet

router = APIRouter(prefix="/api/nfc", tags=["NFC Contactless"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("/payment", response_model=NFCPaymentResponse)
def execute_nfc_tap_payment(
    req: NFCPaymentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than 0")
        
    asset_sym = (req.asset_symbol or "USDT").upper()
    asset = db.query(Asset).filter(Asset.symbol == asset_sym).first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_sym} not found")
        
    wallet = get_or_create_wallet(db, current_user)
    wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == asset.asset_id
    ).first()
    
    if not wb or wb.available_amount < req.amount:
        avail = wb.available_amount if wb else 0.0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"NFC Tap Declined: Insufficient balance ({avail:.2f} {asset.symbol} available, {req.amount:.2f} required)"
        )
        
    ref = generate_reference(prefix="NFC")
    ip = get_client_ip(request)
    
    try:
        from decimal import Decimal
        amt_dec = Decimal(f"{req.amount:.6f}")
        wb.amount -= amt_dec
        wb.available_amount -= amt_dec
        wb.updated_at = datetime.datetime.utcnow()
        
        nfc_pay = NFCPayment(
            user_id=current_user.user_id,
            merchant=req.merchant.strip(),
            amount=req.amount,
            asset_id=asset.asset_id,
            status="COMPLETED",
            reference=ref,
            created_at=datetime.datetime.utcnow()
        )
        db.add(nfc_pay)
        db.flush()
        
        # Transaction
        tx = Transaction(
            user_id=current_user.user_id,
            type="NFC_PAYMENT",
            asset_id=asset.asset_id,
            amount=req.amount,
            sender=f"VAYORA NFC Device ({current_user.name})",
            receiver=req.merchant,
            status="COMPLETED",
            reference_id=ref,
            created_at=datetime.datetime.utcnow()
        )
        db.add(tx)
        
        # Activity
        act = Activity(
            user_id=current_user.user_id,
            action="NFC",
            description=f"NFC Tap-to-Pay authorized: {req.amount:.2f} {asset.symbol} at {req.merchant}",
            reference_id=ref,
            ip_address=ip,
            created_at=datetime.datetime.utcnow()
        )
        db.add(act)
        
        # Notification
        notif = Notification(
            user_id=current_user.user_id,
            title="NFC Contactless Payment Successful",
            message=f"{req.amount:.2f} {asset.symbol} paid to {req.merchant} via NFC Wave.",
            type="PAYMENT",
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)
        
        db.commit()
        db.refresh(nfc_pay)
        
        return NFCPaymentResponse(
            nfc_payment_id=nfc_pay.nfc_payment_id,
            merchant=nfc_pay.merchant,
            amount=nfc_pay.amount,
            asset_symbol=asset.symbol,
            status=nfc_pay.status,
            reference=nfc_pay.reference,
            created_at=nfc_pay.created_at
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[NFCPaymentResponse])
def get_nfc_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(NFCPayment).filter(
        NFCPayment.user_id == current_user.user_id
    ).order_by(NFCPayment.created_at.desc()).all()
    
    return [
        NFCPaymentResponse(
            nfc_payment_id=item.nfc_payment_id,
            merchant=item.merchant,
            amount=item.amount,
            asset_symbol=item.asset.symbol if item.asset else "USDT",
            status=item.status,
            reference=item.reference,
            created_at=item.created_at
        ) for item in items
    ]

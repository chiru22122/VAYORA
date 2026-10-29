from typing import List, Optional
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Conversion, Asset, WalletBalance, Wallet
from backend.schemas import (
    ConvertUSDTRequest, ConversionResponse, LiveRateResponse,
    ConversionChatRequest, ConversionChatResponse
)
from backend.dependencies import get_current_user
from backend.services.conversion_service import execute_usdt_to_inr_conversion
from backend.services.price_service import get_live_usdt_inr_rate, process_conversion_conversation
from backend.services.wallet_service import get_or_create_wallet

router = APIRouter(prefix="/api/convert", tags=["Conversion"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.get("/rate", response_model=LiveRateResponse)
@router.get("/live-rate", response_model=LiveRateResponse)
def get_live_rate(refresh: bool = False):
    """Returns the real-time live USDT to INR exchange rate with 24h change & oracle source."""
    return get_live_usdt_inr_rate(force_refresh=refresh)

@router.post("/usdt-to-inr", response_model=ConversionResponse)
def convert_usdt_to_inr(
    req: ConvertUSDTRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    conv = execute_usdt_to_inr_conversion(
        db=db,
        user=current_user,
        usdt_amount=req.usdt_amount,
        custom_rate=req.rate,
        ip_address=ip
    )
    return ConversionResponse(
        conversion_id=conv.conversion_id,
        asset_symbol="USDT",
        asset_amount=conv.asset_amount,
        exchange_rate=conv.exchange_rate,
        inr_amount=conv.inr_amount,
        status=conv.status,
        created_at=conv.created_at
    )

@router.post("/chat", response_model=ConversionChatResponse)
def conversion_chat_assistant(
    req: ConversionChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Real-time live conversation assistant for USDT -> INR conversions, quotes, and advice.
    """
    wallet = get_or_create_wallet(db, current_user)
    usdt_asset = db.query(Asset).filter(Asset.symbol == "USDT").first()
    avail_usdt = 0.0
    if usdt_asset:
        wb = db.query(WalletBalance).filter(
            WalletBalance.wallet_id == wallet.wallet_id,
            WalletBalance.asset_id == usdt_asset.asset_id
        ).first()
        if wb:
            avail_usdt = float(wb.available_amount or 0.0)

    avail_inr = float(wallet.inr_balance or 0.0)

    result = process_conversion_conversation(
        message=req.message,
        user_name=current_user.name,
        avail_usdt=avail_usdt,
        avail_inr=avail_inr
    )
    return ConversionChatResponse(**result)

@router.get("/history", response_model=List[ConversionResponse])
def get_conversion_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    history = db.query(Conversion).filter(
        Conversion.user_id == current_user.user_id
    ).order_by(Conversion.created_at.desc()).all()
    
    return [
        ConversionResponse(
            conversion_id=c.conversion_id,
            asset_symbol="USDT",
            asset_amount=c.asset_amount,
            exchange_rate=c.exchange_rate,
            inr_amount=c.inr_amount,
            status=c.status,
            created_at=c.created_at
        ) for c in history
    ]

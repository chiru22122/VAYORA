from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Asset
from backend.schemas import WalletResponse, AssetResponse, BalanceResponse, TokenAddressResponse
from backend.dependencies import get_current_user
from backend.services.wallet_service import get_wallet_details
from backend.services.address_service import get_all_token_addresses_with_metadata, ensure_user_token_addresses, NETWORK_SPECS

router = APIRouter(prefix="/api/wallet", tags=["Wallet"])

@router.get("", response_model=WalletResponse)
def get_user_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    details = get_wallet_details(db, current_user)
    return details

@router.get("/assets", response_model=List[AssetResponse])
def get_available_assets(db: Session = Depends(get_db)):
    assets = db.query(Asset).filter(Asset.status == "ACTIVE").all()
    return assets

@router.get("/balances", response_model=List[BalanceResponse])
def get_user_balances(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    details = get_wallet_details(db, current_user)
    return details["balances"]

@router.get("/addresses", response_model=List[TokenAddressResponse])
def get_user_token_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns dedicated receiving addresses for all supported tokens with network metadata."""
    return get_all_token_addresses_with_metadata(db, current_user)

@router.get("/address/{symbol}", response_model=TokenAddressResponse)
def get_single_token_address(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the dedicated receiving address for a single digital asset."""
    sym = symbol.upper().strip()
    all_addrs = get_all_token_addresses_with_metadata(db, current_user)
    for a in all_addrs:
        if a["symbol"] == sym:
            return a
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Token '{symbol}' not supported on VAYORA network."
    )


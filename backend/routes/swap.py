from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Asset
from backend.schemas import SwapQuoteResponse, SwapExecuteRequest, SwapResponse
from backend.dependencies import get_current_user
from backend.services.swap_service import calculate_swap_quote, execute_swap

router = APIRouter(prefix="/api/swap", tags=["Swap"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.get("/quote", response_model=SwapQuoteResponse)
def get_swap_quote(
    from_symbol: str = Query(..., description="Source asset symbol e.g. USDT"),
    to_symbol: str = Query(..., description="Target asset symbol e.g. USDC"),
    from_amount: float = Query(..., gt=0, description="Amount to convert"),
    db: Session = Depends(get_db)
):
    quote = calculate_swap_quote(db, from_symbol, to_symbol, from_amount)
    return SwapQuoteResponse(**quote)

@router.post("", response_model=SwapResponse)
def perform_swap(
    req: SwapExecuteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    swap = execute_swap(
        db=db,
        user=current_user,
        from_symbol=req.from_symbol,
        to_symbol=req.to_symbol,
        from_amount=req.from_amount,
        ip_address=ip
    )
    
    from_asset = db.query(Asset).filter(Asset.asset_id == swap.from_asset_id).first()
    to_asset = db.query(Asset).filter(Asset.asset_id == swap.to_asset_id).first()
    
    return SwapResponse(
        swap_id=swap.swap_id,
        from_symbol=from_asset.symbol if from_asset else "UNKNOWN",
        to_symbol=to_asset.symbol if to_asset else "UNKNOWN",
        from_amount=swap.from_amount,
        to_amount=swap.to_amount,
        rate=swap.rate,
        fee=swap.fee,
        status=swap.status,
        created_at=swap.created_at
    )

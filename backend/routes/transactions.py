from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from backend.database import get_db
from backend.models import User, Transaction, Asset
from backend.schemas import TransactionResponse
from backend.dependencies import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

@router.get("", response_model=List[TransactionResponse])
def get_transactions(
    type: Optional[str] = Query(None, description="Transaction type filter (SEND, RECEIVE, SWAP, CONVERSION, etc.)"),
    asset: Optional[str] = Query(None, description="Asset symbol filter"),
    status: Optional[str] = Query(None, description="Status filter"),
    search: Optional[str] = Query(None, description="Search in reference, sender, receiver"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Transaction).options(joinedload(Transaction.asset)).filter(Transaction.user_id == current_user.user_id)
    
    if type and type != "ALL":
        query = query.filter(Transaction.type == type.upper())
        
    if status and status != "ALL":
        query = query.filter(Transaction.status == status.upper())
        
    if asset and asset != "ALL":
        matching_asset = db.query(Asset).filter(Asset.symbol == asset.upper()).first()
        if matching_asset:
            query = query.filter(Transaction.asset_id == matching_asset.asset_id)
            
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            (Transaction.reference_id.ilike(search_fmt)) |
            (Transaction.sender.ilike(search_fmt)) |
            (Transaction.receiver.ilike(search_fmt))
        )
        
    txs = query.order_by(Transaction.created_at.desc()).limit(limit).all()
    
    result = []
    for t in txs:
        sym = t.asset.symbol if t.asset else None
        result.append(TransactionResponse(
            transaction_id=t.transaction_id,
            type=t.type,
            asset_symbol=sym,
            amount=t.amount,
            sender=t.sender,
            receiver=t.receiver,
            sender_address=t.sender_address,
            receiver_address=t.receiver_address,
            status=t.status,
            reference_id=t.reference_id,
            created_at=t.created_at
        ))
    return result

@router.get("/{tx_id}", response_model=TransactionResponse)
def get_transaction(
    tx_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    t = db.query(Transaction).filter(
        Transaction.transaction_id == tx_id,
        Transaction.user_id == current_user.user_id
    ).first()
    
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        
    return TransactionResponse(
        transaction_id=t.transaction_id,
        type=t.type,
        asset_symbol=t.asset.symbol if t.asset else None,
        amount=t.amount,
        sender=t.sender,
        receiver=t.receiver,
        sender_address=t.sender_address,
        receiver_address=t.receiver_address,
        status=t.status,
        reference_id=t.reference_id,
        created_at=t.created_at
    )


from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models import (
    User, Wallet, WalletBalance, Asset, Transaction, Activity, LoginHistory
)
from backend.schemas import (
    AdminStatsResponse, AdminUserListItem, TransactionResponse, ActivityResponse, LoginHistoryResponse
)
from backend.dependencies import get_current_admin
from backend.services.wallet_service import get_wallet_details

router = APIRouter(prefix="/api/admin", tags=["Admin Portal"])

@router.get("/statistics", response_model=AdminStatsResponse)
def get_admin_statistics(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.email_verified == True).count()
    
    total_tx = db.query(Transaction).count()
    completed_tx = db.query(Transaction).filter(Transaction.status == "COMPLETED").count()
    failed_tx = db.query(Transaction).filter(Transaction.status == "FAILED").count()
    
    # Calculate total wallet value across all users
    all_users = db.query(User).all()
    total_value_usd = 0.0
    for u in all_users:
        try:
            w_details = get_wallet_details(db, u)
            total_value_usd += w_details["total_usd_value"]
        except Exception:
            pass
            
    # Calculate total volume transferred
    vol = db.query(func.sum(func.abs(Transaction.amount))).scalar() or 0.0
    
    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_wallet_value_usd=round(total_value_usd, 2),
        total_transactions=total_tx,
        completed_transactions=completed_tx,
        failed_transactions=failed_tx,
        total_volume_usd=round(float(vol), 2),
        system_status="OPTIMAL"
    )

@router.get("/users", response_model=List[AdminUserListItem])
def get_all_users(
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).order_by(User.created_at.desc()).limit(limit).all()
    result = []
    for u in users:
        w_details = get_wallet_details(db, u)
        result.append(AdminUserListItem(
            user_id=u.user_id,
            name=u.name,
            email=u.email,
            role=u.role,
            email_verified=u.email_verified,
            created_at=u.created_at,
            wallet_address=w_details["address"],
            total_usd_value=w_details["total_usd_value"],
            inr_balance=w_details["inr_balance"]
        ))
    return result

@router.get("/transactions", response_model=List[TransactionResponse])
def get_all_transactions(
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    txs = db.query(Transaction).order_by(Transaction.created_at.desc()).limit(limit).all()
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
            status=t.status,
            reference_id=t.reference_id,
            created_at=t.created_at
        ))
    return result

@router.get("/activity", response_model=List[ActivityResponse])
def get_all_activity(
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    acts = db.query(Activity).order_by(Activity.created_at.desc()).limit(limit).all()
    return [ActivityResponse.from_orm(a) for a in acts]

@router.get("/security-events", response_model=List[LoginHistoryResponse])
def get_all_security_events(
    limit: int = 100,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    events = db.query(LoginHistory).order_by(LoginHistory.created_at.desc()).limit(limit).all()
    return [LoginHistoryResponse.from_orm(e) for e in events]

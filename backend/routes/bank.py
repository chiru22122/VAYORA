from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, BankWithdrawal
from backend.schemas import BankWithdrawRequest, BankWithdrawalResponse
from backend.dependencies import get_current_user
from backend.services.conversion_service import execute_bank_withdrawal

router = APIRouter(prefix="/api/bank", tags=["Bank Prototype"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.post("/withdraw", response_model=BankWithdrawalResponse)
def withdraw_to_bank(
    req: BankWithdrawRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    w = execute_bank_withdrawal(
        db=db,
        user=current_user,
        amount_inr=req.amount,
        bank_name=req.bank_name,
        account_number=req.account_number,
        ifsc_code=req.ifsc_code,
        ip_address=ip
    )
    return BankWithdrawalResponse(
        withdrawal_id=w.withdrawal_id,
        amount=w.amount,
        bank_name=w.bank_name,
        account_number=w.account_number,
        ifsc_code=w.ifsc_code,
        bank_reference=w.bank_reference,
        status=w.status,
        created_at=w.created_at
    )

@router.get("/withdrawals", response_model=List[BankWithdrawalResponse])
def get_bank_withdrawals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(BankWithdrawal).filter(
        BankWithdrawal.user_id == current_user.user_id
    ).order_by(BankWithdrawal.created_at.desc()).all()
    
    return [
        BankWithdrawalResponse(
            withdrawal_id=w.withdrawal_id,
            amount=w.amount,
            bank_name=w.bank_name,
            account_number=w.account_number,
            ifsc_code=w.ifsc_code,
            bank_reference=w.bank_reference,
            status=w.status,
            created_at=w.created_at
        ) for w in items
    ]

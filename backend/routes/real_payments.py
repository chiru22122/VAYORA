from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.dependencies import get_current_user
from backend.services.real_payment_service import (
    get_gateway_config, create_checkout_intent, settle_deposit_payment
)

router = APIRouter(prefix="/api/payments/checkout", tags=["Real Payment Checkout"])

class CheckoutIntentRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to deposit")
    currency: str = Field("USD", description="Currency code (USD, USDT, INR, EUR)")
    payment_method: str = Field("card", description="Payment method: card, upi, netbanking, applepay")

class ConfirmCheckoutRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field("USD")
    reference: str
    payment_method: str = Field("Visa •••• 4242")
    gateway_txn_id: Optional[str] = None

@router.get("/config")
def get_payment_gateway_config():
    """Returns active gateway configuration and publishable keys for frontend checkout."""
    return get_gateway_config()

@router.post("/create-intent")
def create_intent(
    req: CheckoutIntentRequest,
    current_user: User = Depends(get_current_user)
):
    """Initializes a real payment intent with Stripe or local sandbox gateway."""
    intent = create_checkout_intent(
        user=current_user,
        amount=req.amount,
        currency=req.currency,
        payment_method=req.payment_method
    )
    return intent

@router.post("/confirm")
def confirm_checkout(
    req: ConfirmCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirms payment processing, atomically credits the user's wallet on the ledger,
    and sends a real email receipt.
    """
    result = settle_deposit_payment(
        db=db,
        user=current_user,
        amount=req.amount,
        currency=req.currency,
        reference=req.reference,
        payment_method=req.payment_method,
        gateway_txn_id=req.gateway_txn_id
    )
    return result

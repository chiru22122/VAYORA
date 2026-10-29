import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Card, Transaction, Activity, Notification
from backend.schemas import CardResponse, CardFreezeRequest, CardSimulatePaymentRequest
from backend.dependencies import get_current_user
from backend.auth import generate_virtual_card_number, generate_reference

router = APIRouter(prefix="/api/card", tags=["Virtual Card"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.get("", response_model=CardResponse)
def get_user_card(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.user_id == current_user.user_id).first()
    if not card:
        num = generate_virtual_card_number()
        card = Card(
            user_id=current_user.user_id,
            cardholder_name=current_user.name.upper(),
            masked_number=f"•••• •••• •••• {num[-4:]}",
            full_number=num,
            expiry="08/29",
            cvv="782",
            status="ACTIVE",
            balance=1500.0,
            daily_limit=5000.0,
            card_tier="BLACK OBSIDIAN"
        )
        db.add(card)
        db.commit()
        db.refresh(card)
    return CardResponse.from_orm(card)

@router.post("/freeze", response_model=CardResponse)
def toggle_freeze_card(
    req: CardFreezeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.user_id == current_user.user_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No card found for user")
        
    card.status = "FROZEN" if req.freeze else "ACTIVE"
    
    # Activity
    action_text = "Frozen" if req.freeze else "Unfrozen"
    act = Activity(
        user_id=current_user.user_id,
        action="CARD",
        description=f"Virtual Card ending in {card.masked_number[-4:]} was {action_text.lower()}",
        reference_id=f"CRD-{card.card_id}"
    )
    db.add(act)
    
    # Notification
    notif = Notification(
        user_id=current_user.user_id,
        title=f"Virtual Card {action_text}",
        message=f"Your card {card.masked_number} is now {card.status.lower()}.",
        type="SECURITY"
    )
    db.add(notif)
    
    db.commit()
    db.refresh(card)
    return CardResponse.from_orm(card)

@router.post("/unfreeze", response_model=CardResponse)
def unfreeze_card(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.user_id == current_user.user_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        
    card.status = "ACTIVE"
    db.commit()
    db.refresh(card)
    return CardResponse.from_orm(card)

@router.post("/simulate-payment")
def simulate_card_payment(
    req: CardSimulatePaymentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    card = db.query(Card).filter(Card.user_id == current_user.user_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        
    if card.status == "FROZEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction declined. Virtual Card is currently FROZEN."
        )
        
    if card.balance < req.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction declined. Insufficient card balance (${card.balance:.2f} available)."
        )
        
    ip = get_client_ip(request)
    ref = generate_reference(prefix="CRD")
    
    try:
        card.balance -= req.amount
        
        # Transaction
        tx = Transaction(
            user_id=current_user.user_id,
            type="CARD_PAYMENT",
            amount=req.amount,
            sender=f"Card {card.masked_number}",
            receiver=req.merchant,
            status="COMPLETED",
            reference_id=ref,
            created_at=datetime.datetime.utcnow()
        )
        db.add(tx)
        
        # Activity
        act = Activity(
            user_id=current_user.user_id,
            action="CARD",
            description=f"Online payment of ${req.amount:.2f} at {req.merchant} via {card.masked_number}",
            reference_id=ref,
            ip_address=ip,
            created_at=datetime.datetime.utcnow()
        )
        db.add(act)
        
        # Notification
        notif = Notification(
            user_id=current_user.user_id,
            title="Card Payment Approved",
            message=f"${req.amount:.2f} authorized at {req.merchant}.",
            type="PAYMENT",
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)
        
        db.commit()
        return {
            "status": "APPROVED",
            "reference": ref,
            "merchant": req.merchant,
            "amount": req.amount,
            "remaining_card_balance": round(card.balance, 2)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

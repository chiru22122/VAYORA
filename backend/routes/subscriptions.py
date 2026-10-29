import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Wallet, WalletBalance, Asset, Transaction, Activity, Notification
from backend.dependencies import get_current_user
from backend.auth import generate_reference

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions & Auto-Pay"])

DEFAULT_SUBSCRIPTIONS = [
    {
        "sub_id": "sub_openai_01",
        "service_name": "OpenAI ChatGPT Plus & API",
        "category": "AI / Developer Services",
        "icon": "🤖",
        "amount": 20.00,
        "currency": "USDT",
        "billing_cycle": "Monthly",
        "next_billing": "2026-10-25",
        "status": "ACTIVE",
        "color": "#00ff9d"
    },
    {
        "sub_id": "sub_aws_02",
        "service_name": "AWS Cloud Infrastructure",
        "category": "Cloud Hosting",
        "icon": "☁️",
        "amount": 45.50,
        "currency": "USDT",
        "billing_cycle": "Monthly",
        "next_billing": "2026-11-01",
        "status": "ACTIVE",
        "color": "#ffb703"
    },
    {
        "sub_id": "sub_netflix_03",
        "service_name": "Netflix Premium 4K UHD",
        "category": "Streaming & Entertainment",
        "icon": "🎬",
        "amount": 22.99,
        "currency": "USDT",
        "billing_cycle": "Monthly",
        "next_billing": "2026-10-18",
        "status": "ACTIVE",
        "color": "#ff2a85"
    },
    {
        "sub_id": "sub_github_04",
        "service_name": "GitHub Enterprise & Copilot",
        "category": "Developer Tools",
        "icon": "🐙",
        "amount": 10.00,
        "currency": "USDT",
        "billing_cycle": "Monthly",
        "next_billing": "2026-10-30",
        "status": "ACTIVE",
        "color": "#00f0ff"
    },
    {
        "sub_id": "sub_spotify_05",
        "service_name": "Spotify Family Hi-Fi",
        "category": "Music Streaming",
        "icon": "🎵",
        "amount": 16.99,
        "currency": "USDT",
        "billing_cycle": "Monthly",
        "next_billing": "2026-11-05",
        "status": "PAUSED",
        "color": "#05f2db"
    }
]

# Simple in-memory/session state for subscription toggles
_user_sub_states = {}

class ToggleSubRequest(BaseModel):
    sub_id: str
    active: bool

class TriggerBillRequest(BaseModel):
    sub_id: str

@router.get("")
def get_user_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_state = _user_sub_states.setdefault(current_user.user_id, {})
    subs = []
    total_monthly_burn = 0.0

    for s in DEFAULT_SUBSCRIPTIONS:
        sub_copy = dict(s)
        if s["sub_id"] in user_state:
            sub_copy["status"] = user_state[s["sub_id"]]
        if sub_copy["status"] == "ACTIVE":
            total_monthly_burn += sub_copy["amount"]
        subs.append(sub_copy)

    return {
        "subscriptions": subs,
        "total_monthly_burn": round(total_monthly_burn, 2),
        "active_count": sum(1 for s in subs if s["status"] == "ACTIVE"),
        "paused_count": sum(1 for s in subs if s["status"] == "PAUSED")
    }

@router.post("/toggle")
def toggle_subscription(
    req: ToggleSubRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_state = _user_sub_states.setdefault(current_user.user_id, {})
    new_status = "ACTIVE" if req.active else "PAUSED"
    user_state[req.sub_id] = new_status

    act = Activity(
        user_id=current_user.user_id,
        action="SUBSCRIPTION",
        description=f"Subscription {req.sub_id} set to {new_status}",
        reference_id=req.sub_id
    )
    db.add(act)
    db.commit()

    return {"success": True, "sub_id": req.sub_id, "status": new_status}

@router.post("/trigger-billing")
def trigger_subscription_billing(
    req: TriggerBillRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sub = next((s for s in DEFAULT_SUBSCRIPTIONS if s["sub_id"] == req.sub_id), None)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.user_id).first()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    asset = db.query(Asset).filter(Asset.symbol == sub["currency"]).first()
    if not asset:
        asset = db.query(Asset).filter(Asset.symbol == "USDT").first()

    wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == asset.asset_id
    ).first()

    if not wb or wb.available_amount < sub["amount"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient balance to execute auto-debit for {sub['service_name']}")

    # Deduct balance
    from decimal import Decimal
    amt_dec = Decimal(f"{sub['amount']:.6f}")
    wb.amount -= amt_dec
    wb.available_amount -= amt_dec
    wb.updated_at = datetime.datetime.utcnow()

    ref = generate_reference("SUB")
    tx = Transaction(
        user_id=current_user.user_id,
        asset_id=asset.asset_id,
        type="AUTO_BILLING",
        amount=-sub["amount"],
        sender=current_user.email,
        receiver=sub["service_name"],
        status="COMPLETED",
        reference_id=ref
    )
    db.add(tx)

    act = Activity(
        user_id=current_user.user_id,
        action="AUTO_BILLING",
        description=f"Auto-debit processed: {sub['amount']} {sub['currency']} for {sub['service_name']}",
        reference_id=ref
    )
    db.add(act)

    notif = Notification(
        user_id=current_user.user_id,
        title="Subscription Billed",
        message=f"Auto-debit of {sub['amount']} {sub['currency']} settled for {sub['service_name']}.",
        type="BILLING"
    )
    db.add(notif)

    db.commit()
    return {
        "success": True,
        "message": f"Successfully billed {sub['amount']} {sub['currency']} for {sub['service_name']}",
        "reference": ref,
        "new_balance": wb.available_amount,
        "amount": sub["amount"],
        "currency": sub["currency"],
        "service_name": sub["service_name"]
    }

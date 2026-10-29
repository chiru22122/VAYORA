import os
import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.models import (
    User, Asset, WalletBalance, Conversion, BankWithdrawal, Transaction, Activity, Notification
)
from backend.auth import generate_reference
from backend.services.wallet_service import get_or_create_wallet
from backend.services.price_service import get_current_usdt_inr_rate_value, get_live_usdt_inr_rate

DEMO_EXCHANGE_RATE_USDT_INR = float(os.getenv("DEMO_EXCHANGE_RATE_USDT_INR", "86.50"))

def execute_usdt_to_inr_conversion(
    db: Session,
    user: User,
    usdt_amount: float,
    custom_rate: float = None,
    ip_address: str = "127.0.0.1"
) -> Conversion:
    if usdt_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversion amount must be greater than 0 USDT"
        )
        
    wallet = get_or_create_wallet(db, user)
    
    usdt_asset = db.query(Asset).filter(Asset.symbol == "USDT").first()
    if not usdt_asset:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="USDT asset configuration missing in system"
        )
        
    wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == usdt_asset.asset_id
    ).first()

    if not wb or float(wb.available_amount or 0.0) < usdt_amount:
        avail = float(wb.available_amount) if wb else 0.0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient USDT balance. Available: {avail:.2f} USDT, Requested: {usdt_amount:.2f} USDT"
        )
        
    # Obtain real-time live market exchange rate
    live_rate_data = get_live_usdt_inr_rate()
    live_rate = float(live_rate_data["rate"])
    
    # If client passed custom_rate, validate within 5% slippage tolerance to protect from stale pricing
    if custom_rate and custom_rate > 0:
        if abs(custom_rate - live_rate) / live_rate <= 0.05:
            rate = round(custom_rate, 2)
        else:
            rate = live_rate
    else:
        rate = live_rate

    inr_amount = round(usdt_amount * rate, 2)
    dec_usdt = Decimal(str(round(usdt_amount, 6)))
    
    try:
        # Atomic balance mutation
        wb.amount = wb.amount - dec_usdt
        wb.available_amount = wb.available_amount - dec_usdt
        wb.updated_at = datetime.datetime.utcnow()

        # Credit wallet INR balance
        wallet.inr_balance = round(wallet.inr_balance + inr_amount, 2)
        wallet.inr_balance_paise = (wallet.inr_balance_paise or 0) + int(round(inr_amount * 100))

        # Sync authoritative double-entry Account balances
        from backend.models import Account
        from backend.services.payment_service import ensure_user_accounts
        ensure_user_accounts(db, user)

        usdt_acct = db.query(Account).filter(Account.user_id == user.user_id, Account.currency == "USDT").first()
        inr_acct = db.query(Account).filter(Account.user_id == user.user_id, Account.currency == "INR").first()
        if usdt_acct:
            usdt_acct.balance -= dec_usdt
            usdt_acct.available_balance -= dec_usdt
            usdt_acct.updated_at = datetime.datetime.utcnow()
        if inr_acct:
            inr_acct.balance_paise = (inr_acct.balance_paise or 0) + int(round(inr_amount * 100))
            inr_acct.balance = Decimal(str(round(inr_acct.balance_paise / 100.0, 2)))
            inr_acct.available_balance = inr_acct.balance
            inr_acct.updated_at = datetime.datetime.utcnow()
        
        # Record conversion
        conv = Conversion(
            user_id=user.user_id,
            asset_id=usdt_asset.asset_id,
            asset_amount=usdt_amount,
            exchange_rate=rate,
            inr_amount=inr_amount,
            status="COMPLETED",
            created_at=datetime.datetime.utcnow()
        )
        db.add(conv)
        db.flush()
        
        # Transaction record
        ref = generate_reference(prefix="CVT")
        tx = Transaction(
            user_id=user.user_id,
            type="CONVERSION",
            asset_id=usdt_asset.asset_id,
            amount=usdt_amount,
            sender=f"{usdt_amount:.2f} USDT",
            receiver=f"₹{inr_amount:,.2f} INR (Local Balance)",
            status="COMPLETED",
            reference_id=ref,
            created_at=datetime.datetime.utcnow()
        )
        db.add(tx)
        
        # Activity record
        act = Activity(
            user_id=user.user_id,
            action="CONVERT",
            description=f"Converted {usdt_amount:.2f} USDT to ₹{inr_amount:,.2f} INR @ Live Rate ₹{rate:.2f}/USDT ({live_rate_data['source']})",
            reference_id=ref,
            ip_address=ip_address,
            created_at=datetime.datetime.utcnow()
        )
        db.add(act)
        
        # Notification
        notif = Notification(
            user_id=user.user_id,
            title="USDT → INR Conversion Executed (Live Rate)",
            message=f"Received ₹{inr_amount:,.2f} INR from {usdt_amount:.2f} USDT @ live market rate ₹{rate:.2f}/USDT.",
            type="PAYMENT",
            is_read=False,
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)
        
        db.commit()
        db.refresh(conv)
        return conv
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"USDT to INR conversion failed: {str(e)}"
        )

def execute_bank_withdrawal(
    db: Session,
    user: User,
    amount_inr: float,
    bank_name: str,
    account_number: str,
    ifsc_code: str,
    ip_address: str = "127.0.0.1"
) -> BankWithdrawal:
    if amount_inr <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawal amount must be greater than ₹0.00"
        )
        
    wallet = get_or_create_wallet(db, user)
    
    if wallet.inr_balance < amount_inr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient INR balance for withdrawal. Available: ₹{wallet.inr_balance:,.2f}, Requested: ₹{amount_inr:,.2f}"
        )
        
    masked_acc = f"•••• {account_number[-4:]}" if len(account_number) >= 4 else account_number
    bank_ref = generate_reference(prefix="WTH")
    
    try:
        # Deduct INR balance
        wallet.inr_balance -= amount_inr
        
        withdrawal = BankWithdrawal(
            user_id=user.user_id,
            amount=amount_inr,
            bank_name=bank_name.strip(),
            account_number=masked_acc,
            ifsc_code=ifsc_code.strip().upper(),
            bank_reference=bank_ref,
            status="COMPLETED",
            created_at=datetime.datetime.utcnow()
        )
        db.add(withdrawal)
        db.flush()
        
        # Transaction record
        tx = Transaction(
            user_id=user.user_id,
            type="BANK_WITHDRAWAL",
            asset_id=None,
            amount=amount_inr,
            sender="VAYORA INR Balance",
            receiver=f"{bank_name} ({masked_acc})",
            status="COMPLETED",
            reference_id=bank_ref,
            created_at=datetime.datetime.utcnow()
        )
        db.add(tx)
        
        # Activity
        act = Activity(
            user_id=user.user_id,
            action="WITHDRAWAL",
            description=f"Simulated bank withdrawal of ₹{amount_inr:,.2f} to {bank_name} ({masked_acc})",
            reference_id=bank_ref,
            ip_address=ip_address,
            created_at=datetime.datetime.utcnow()
        )
        db.add(act)
        
        # Notification
        notif = Notification(
            user_id=user.user_id,
            title="Bank Withdrawal Dispatched",
            message=f"₹{amount_inr:,.2f} transferred to {bank_name} {masked_acc}. Ref: {bank_ref}",
            type="PAYMENT",
            is_read=False,
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)
        
        db.commit()
        db.refresh(withdrawal)
        return withdrawal
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bank withdrawal processing failed: {str(e)}"
        )

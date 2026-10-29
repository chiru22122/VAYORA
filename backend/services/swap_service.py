import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.models import User, Asset, WalletBalance, Swap, Transaction, Activity, Notification
from backend.auth import generate_reference
from backend.services.wallet_service import get_or_create_wallet

def calculate_swap_quote(db: Session, from_symbol: str, to_symbol: str, from_amount: float) -> dict:
    if from_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Swap amount must be greater than 0"
        )
    
    from_asset = db.query(Asset).filter(Asset.symbol == from_symbol.upper()).first()
    to_asset = db.query(Asset).filter(Asset.symbol == to_symbol.upper()).first()
    
    if not from_asset or not to_asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both selected assets do not exist"
        )
        
    if from_asset.asset_id == to_asset.asset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot swap an asset for itself"
        )
        
    # Rate = from_price / to_price
    rate = from_asset.price / to_asset.price
    gross_to_amount = from_amount * rate
    fee_pct = 0.001  # 0.1% demo fee
    fee = gross_to_amount * fee_pct
    net_to_amount = gross_to_amount - fee
    
    return {
        "from_symbol": from_asset.symbol,
        "to_symbol": to_asset.symbol,
        "from_amount": from_amount,
        "to_amount": round(net_to_amount, 6),
        "rate": round(rate, 6),
        "fee": round(fee, 6),
        "network_fee_usd": 0.0,
        "expires_in_seconds": 60
    }

def execute_swap(
    db: Session,
    user: User,
    from_symbol: str,
    to_symbol: str,
    from_amount: float,
    ip_address: str = "127.0.0.1"
) -> Swap:
    quote = calculate_swap_quote(db, from_symbol, to_symbol, from_amount)
    from_asset = db.query(Asset).filter(Asset.symbol == from_symbol.upper()).first()
    to_asset = db.query(Asset).filter(Asset.symbol == to_symbol.upper()).first()
    
    wallet = get_or_create_wallet(db, user)
    
    from_wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == from_asset.asset_id
    ).first()
    
    if not from_wb or from_wb.available_amount < from_amount:
        curr = from_wb.available_amount if from_wb else 0.0
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient {from_asset.symbol} balance for swap. Available: {curr:.4f}, Requested: {from_amount:.4f}"
        )
        
    to_wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == to_asset.asset_id
    ).first()
    
    if not to_wb:
        to_wb = WalletBalance(
            wallet_id=wallet.wallet_id,
            asset_id=to_asset.asset_id,
            amount=0.0,
            available_amount=0.0
        )
        db.add(to_wb)
        db.flush()
        
    try:
        # Atomic deduction and credit
        from_amount_dec = Decimal(f"{from_amount:.6f}")
        to_amount_dec = Decimal(f"{quote['to_amount']:.6f}")

        from_wb.amount -= from_amount_dec
        from_wb.available_amount -= from_amount_dec
        from_wb.updated_at = datetime.datetime.utcnow()

        to_wb.amount += to_amount_dec
        to_wb.available_amount += to_amount_dec
        to_wb.updated_at = datetime.datetime.utcnow()

        # Sync authoritative double-entry Account balances
        from backend.models import Account
        from backend.services.payment_service import ensure_user_accounts
        ensure_user_accounts(db, user)

        from_acct = db.query(Account).filter(Account.user_id == user.user_id, Account.currency == from_symbol.upper()).first()
        to_acct = db.query(Account).filter(Account.user_id == user.user_id, Account.currency == to_symbol.upper()).first()
        if from_acct:
            from_acct.balance -= Decimal(str(from_amount))
            from_acct.available_balance -= Decimal(str(from_amount))
            from_acct.updated_at = datetime.datetime.utcnow()
        if to_acct:
            to_acct.balance += Decimal(str(quote["to_amount"]))
            to_acct.available_balance += Decimal(str(quote["to_amount"]))
            to_acct.updated_at = datetime.datetime.utcnow()
        
        # Create swap record
        swap_record = Swap(
            user_id=user.user_id,
            from_asset_id=from_asset.asset_id,
            to_asset_id=to_asset.asset_id,
            from_amount=from_amount,
            to_amount=quote["to_amount"],
            rate=quote["rate"],
            fee=quote["fee"],
            status="COMPLETED",
            created_at=datetime.datetime.utcnow()
        )
        db.add(swap_record)
        db.flush()
        
        # Transaction record
        tx_ref = generate_reference(prefix="SWP")
        tx = Transaction(
            user_id=user.user_id,
            type="SWAP",
            asset_id=from_asset.asset_id,
            amount=from_amount,
            sender=f"{from_asset.symbol} ({from_amount:.4f})",
            receiver=f"{to_asset.symbol} ({quote['to_amount']:.4f})",
            status="COMPLETED",
            reference_id=tx_ref,
            created_at=datetime.datetime.utcnow()
        )
        db.add(tx)
        
        # Activity record
        act = Activity(
            user_id=user.user_id,
            action="SWAP",
            description=f"Swapped {from_amount:.4f} {from_asset.symbol} for {quote['to_amount']:.4f} {to_asset.symbol}",
            reference_id=tx_ref,
            ip_address=ip_address,
            created_at=datetime.datetime.utcnow()
        )
        db.add(act)
        
        # Notification
        notif = Notification(
            user_id=user.user_id,
            title="Instant Swap Completed",
            message=f"Converted {from_amount:.4f} {from_asset.symbol} to {quote['to_amount']:.4f} {to_asset.symbol}.",
            type="SWAP",
            is_read=False,
            created_at=datetime.datetime.utcnow()
        )
        db.add(notif)
        
        db.commit()
        db.refresh(swap_record)
        return swap_record
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Swap execution failed: {str(e)}"
        )

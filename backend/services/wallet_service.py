import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.models import User, Wallet, Asset, WalletBalance
from backend.auth import generate_wallet_address
from backend.services.price_service import get_current_usdt_inr_rate_value
from backend.services.address_service import ensure_user_token_addresses, NETWORK_SPECS

DEMO_EXCHANGE_RATE_USDT_INR = float(os.getenv("DEMO_EXCHANGE_RATE_USDT_INR", "86.50"))

def get_or_create_wallet(db: Session, user: User, auto_commit: bool = True) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.user_id == user.user_id).first()
    if not wallet:
        wallet = Wallet(
            user_id=user.user_id,
            wallet_type="MAIN",
            address=generate_wallet_address("VYR"),
            inr_balance=0.0
        )
        db.add(wallet)
        db.flush()
        
        # Ensure all existing assets have balance records
        assets = db.query(Asset).filter(Asset.status == "ACTIVE").all()
        for a in assets:
            wb = WalletBalance(
                wallet_id=wallet.wallet_id,
                asset_id=a.asset_id,
                amount=0.0,
                available_amount=0.0
            )
            db.add(wb)
        if auto_commit:
            db.commit()
            db.refresh(wallet)
        else:
            db.flush()
        
    return wallet

def get_wallet_details(db: Session, user: User) -> Dict[str, Any]:
    wallet = get_or_create_wallet(db, user)
    token_addrs_map = ensure_user_token_addresses(db, user)

    # Ensure authoritative double-entry accounts exist and are in sync
    from backend.services.payment_service import ensure_user_accounts
    from backend.models import Account
    ensure_user_accounts(db, user)

    # Batch-fetch all user currency accounts in ONE single query
    user_accounts = {
        acct.currency: acct
        for acct in db.query(Account).filter(Account.user_id == user.user_id).all()
    }

    # Sync INR balance from Account
    inr_acct = user_accounts.get("INR")
    if inr_acct and inr_acct.balance is not None:
        wallet.inr_balance_paise = inr_acct.balance_paise
        wallet.inr_balance = float(inr_acct.balance)
        db.flush()

    assets = db.query(Asset).filter(Asset.status == "ACTIVE").all()

    # Batch-fetch all balances for this wallet in ONE single query
    existing_wb_list = db.query(WalletBalance).filter(WalletBalance.wallet_id == wallet.wallet_id).all()
    wb_map = {wb.asset_id: wb for wb in existing_wb_list}

    # Fetch exchange rate ONCE for all assets
    live_usdt_inr_rate = get_current_usdt_inr_rate_value()

    balances_list = []
    total_usd = 0.0

    for asset in assets:
        wb = wb_map.get(asset.asset_id)

        if not wb:
            wb = WalletBalance(
                wallet_id=wallet.wallet_id,
                asset_id=asset.asset_id,
                amount=0.0,
                available_amount=0.0
            )
            db.add(wb)
            db.commit()
            db.refresh(wb)
            wb_map[asset.asset_id] = wb

        # Sync crypto balance with Account if present
        acct = user_accounts.get(asset.symbol)
        if acct and acct.balance is not None and wb.amount != acct.balance:
            wb.amount = acct.balance
            wb.available_amount = acct.available_balance
            db.flush()

        amt_float = float(wb.amount or 0.0)
        avail_float = float(wb.available_amount or 0.0)
        usd_val = round(amt_float * float(asset.price), 2)
        inr_val = round(usd_val * live_usdt_inr_rate, 2)
        total_usd += usd_val
        
        dep_addr = token_addrs_map.get(asset.symbol, wallet.address)
        spec = NETWORK_SPECS.get(asset.symbol, {})
        qr_uri = f"{spec.get('qr_prefix', '')}{dep_addr}"
        if asset.symbol == "USDT":
            qr_uri = f"tron:{dep_addr}?token=USDT"
        elif asset.symbol == "BTC":
            qr_uri = f"bitcoin:{dep_addr}"
        elif asset.symbol == "ETH":
            qr_uri = f"ethereum:{dep_addr}"
        elif asset.symbol == "SOL":
            qr_uri = f"solana:{dep_addr}"
        elif asset.symbol == "INR":
            qr_uri = f"upi://pay?pa={dep_addr}&pn={user.name}&cu=INR"
        
        balances_list.append({
            "balance_id": wb.balance_id,
            "asset_id": asset.asset_id,
            "symbol": asset.symbol,
            "name": asset.name,
            "network": spec.get("network", asset.network),
            "price": float(asset.price),
            "amount": amt_float,
            "available_amount": avail_float,
            "usd_value": usd_val,
            "inr_value": inr_val,
            "icon": asset.icon,
            "deposit_address": dep_addr,
            "qr_uri": qr_uri,
            "updated_at": wb.updated_at
        })
        
    # Also add the INR balance to total INR valuation
    total_inr = round(total_usd * live_usdt_inr_rate + wallet.inr_balance, 2)
    
    return {
        "wallet_id": wallet.wallet_id,
        "address": wallet.address,
        "wallet_type": wallet.wallet_type,
        "inr_balance": round(wallet.inr_balance, 2),
        "total_usd_value": round(total_usd + (wallet.inr_balance / max(live_usdt_inr_rate, 1.0)), 2),
        "total_inr_value": total_inr,
        "balances": balances_list,
        "token_addresses": token_addrs_map
    }


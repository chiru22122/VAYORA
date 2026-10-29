import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Wallet, WalletBalance, Asset, Transaction, Activity, Notification
from backend.dependencies import get_current_user
from backend.auth import generate_reference

router = APIRouter(prefix="/api/earn", tags=["Staking & Earn Vaults"])

VAULTS_CONFIG = [
    {
        "vault_id": "usdt-yield-vault",
        "asset_symbol": "USDT",
        "name": "USDT Prime Liquidity Vault",
        "apy": 8.50,
        "lockup": "Flexible / Instant",
        "tvl": "$4,850,200",
        "risk": "Low / Audited",
        "color": "#00ff9d"
    },
    {
        "vault_id": "usdc-yield-vault",
        "asset_symbol": "USDC",
        "name": "USDC Circle Institutional Vault",
        "apy": 8.00,
        "lockup": "Flexible / Instant",
        "tvl": "$3,210,000",
        "risk": "Minimal",
        "color": "#00f0ff"
    },
    {
        "vault_id": "sol-staking-pool",
        "asset_symbol": "SOL",
        "name": "Solana High-Yield Validator Pool",
        "apy": 7.80,
        "lockup": "Flexible / Instant",
        "tvl": "$1,940,500",
        "risk": "Medium",
        "color": "#c036ff"
    },
    {
        "vault_id": "eth-staking-pool",
        "asset_symbol": "ETH",
        "name": "Ethereum 2.0 Liquid Staking",
        "apy": 5.20,
        "lockup": "Flexible / Instant",
        "tvl": "$8,720,000",
        "risk": "Low",
        "color": "#2979ff"
    },
    {
        "vault_id": "btc-earn-vault",
        "asset_symbol": "BTC",
        "name": "Bitcoin Layer-2 Yield Maximizer",
        "apy": 4.10,
        "lockup": "Flexible / Instant",
        "tvl": "$14,500,000",
        "risk": "Low",
        "color": "#ffb703"
    }
]

class StakeRequest(BaseModel):
    vault_id: str
    asset_symbol: str
    amount: float = Field(gt=0)

class UnstakeRequest(BaseModel):
    vault_id: str
    asset_symbol: str
    amount: float = Field(gt=0)

class HarvestRequest(BaseModel):
    vault_id: str
    asset_symbol: str

@router.get("/vaults")
def get_vaults(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.user_id).first()
    results = []
    
    for v in VAULTS_CONFIG:
        asset = db.query(Asset).filter(Asset.symbol == v["asset_symbol"]).first()
        available_bal = 0.0
        staked_amount = 0.0

        if wallet and asset:
            wb = db.query(WalletBalance).filter(
                WalletBalance.wallet_id == wallet.wallet_id,
                WalletBalance.asset_id == asset.asset_id
            ).first()
            if wb:
                available_bal = float(wb.available_amount)

            # Calculate simulated active staked position based on transactions
            staked_txs = db.query(Transaction).filter(
                Transaction.user_id == current_user.user_id,
                Transaction.asset_id == asset.asset_id,
                Transaction.type.in_(["STAKE_DEPOSIT", "STAKE_WITHDRAWAL", "YIELD_HARVEST"])
            ).all()

            for tx in staked_txs:
                if tx.type == "STAKE_DEPOSIT":
                    staked_amount += abs(tx.amount)
                elif tx.type == "STAKE_WITHDRAWAL":
                    staked_amount -= abs(tx.amount)
            if staked_amount < 0:
                staked_amount = 0.0

        # Simulated real-time yield rate per second
        yield_per_year = staked_amount * (v["apy"] / 100.0)
        yield_per_second = yield_per_year / (365 * 24 * 3600)

        results.append({
            **v,
            "available_wallet_balance": available_bal,
            "user_staked_amount": round(staked_amount, 6),
            "yield_per_second": yield_per_second,
            "estimated_daily_yield": round(yield_per_year / 365, 6),
            "estimated_monthly_yield": round(yield_per_year / 12, 6)
        })
    return results

@router.post("/stake")
def execute_stake(
    req: StakeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.user_id).first()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    asset = db.query(Asset).filter(Asset.symbol == req.asset_symbol.upper()).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not supported")

    wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == asset.asset_id
    ).first()

    if not wb or wb.available_amount < req.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient {req.asset_symbol} balance to stake")

    # Deduct wallet balance
    from decimal import Decimal
    amt_dec = Decimal(f"{req.amount:.6f}")
    wb.amount -= amt_dec
    wb.available_amount -= amt_dec
    wb.updated_at = datetime.datetime.utcnow()

    ref = generate_reference("STK")
    tx = Transaction(
        user_id=current_user.user_id,
        asset_id=asset.asset_id,
        type="STAKE_DEPOSIT",
        amount=-req.amount,
        sender=current_user.email,
        receiver=f"VAYORA Yield Vault ({req.vault_id})",
        status="COMPLETED",
        reference_id=ref
    )
    db.add(tx)

    act = Activity(
        user_id=current_user.user_id,
        action="STAKE_DEPOSIT",
        description=f"Staked {req.amount} {req.asset_symbol} in {req.vault_id}",
        reference_id=ref
    )
    db.add(act)

    notif = Notification(
        user_id=current_user.user_id,
        title="Staking Vault Active",
        message=f"Successfully allocated {req.amount} {req.asset_symbol} to high-yield staking pool. Rewards accrue continuously.",
        type="STAKE"
    )
    db.add(notif)

    db.commit()
    return {
        "success": True,
        "message": f"Successfully staked {req.amount} {req.asset_symbol}",
        "reference": ref,
        "new_balance": wb.available_amount
    }

@router.post("/unstake")
def execute_unstake(
    req: UnstakeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.user_id).first()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    asset = db.query(Asset).filter(Asset.symbol == req.asset_symbol.upper()).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not supported")

    wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == asset.asset_id
    ).first()

    if not wb:
        wb = WalletBalance(wallet_id=wallet.wallet_id, asset_id=asset.asset_id, amount=0.0, available_amount=0.0)
        db.add(wb)

    # Return capital to available balance
    from decimal import Decimal
    amt_dec = Decimal(f"{req.amount:.6f}")
    wb.amount += amt_dec
    wb.available_amount += amt_dec
    wb.updated_at = datetime.datetime.utcnow()

    ref = generate_reference("UNSTK")
    tx = Transaction(
        user_id=current_user.user_id,
        asset_id=asset.asset_id,
        type="STAKE_WITHDRAWAL",
        amount=req.amount,
        sender=f"VAYORA Yield Vault ({req.vault_id})",
        receiver=current_user.email,
        status="COMPLETED",
        reference_id=ref
    )
    db.add(tx)

    act = Activity(
        user_id=current_user.user_id,
        action="STAKE_WITHDRAWAL",
        description=f"Unstaked {req.amount} {req.asset_symbol} from {req.vault_id}",
        reference_id=ref
    )
    db.add(act)

    db.commit()
    return {
        "success": True,
        "message": f"Successfully unstaked {req.amount} {req.asset_symbol}",
        "reference": ref,
        "new_balance": float(wb.available_amount)
    }

@router.post("/harvest")
def execute_harvest(
    req: HarvestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.user_id).first()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    asset = db.query(Asset).filter(Asset.symbol == req.asset_symbol.upper()).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not supported")

    harvest_amount = 1.25042 if req.asset_symbol == "USDT" else 0.00045

    wb = db.query(WalletBalance).filter(
        WalletBalance.wallet_id == wallet.wallet_id,
        WalletBalance.asset_id == asset.asset_id
    ).first()

    if not wb:
        wb = WalletBalance(wallet_id=wallet.wallet_id, asset_id=asset.asset_id, amount=0.0, available_amount=0.0)
        db.add(wb)

    from decimal import Decimal
    h_dec = Decimal(f"{harvest_amount:.6f}")
    wb.amount += h_dec
    wb.available_amount += h_dec
    wb.updated_at = datetime.datetime.utcnow()

    ref = generate_reference("HRV")
    tx = Transaction(
        user_id=current_user.user_id,
        asset_id=asset.asset_id,
        type="YIELD_HARVEST",
        amount=harvest_amount,
        sender="VAYORA Yield Smart Contract",
        receiver=current_user.email,
        status="COMPLETED",
        reference_id=ref
    )
    db.add(tx)

    act = Activity(
        user_id=current_user.user_id,
        action="YIELD_HARVEST",
        description=f"Harvested {harvest_amount} {req.asset_symbol} yield from {req.vault_id}",
        reference_id=ref
    )
    db.add(act)

    notif = Notification(
        user_id=current_user.user_id,
        title="Yield Harvested",
        message=f"+{harvest_amount} {req.asset_symbol} added to your available balance.",
        type="EARN"
    )
    db.add(notif)

    db.commit()
    return {
        "success": True,
        "harvested_amount": harvest_amount,
        "asset_symbol": req.asset_symbol,
        "reference": ref,
        "new_balance": wb.available_amount
    }

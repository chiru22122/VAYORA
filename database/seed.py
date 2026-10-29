import os
import sys
import datetime

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from backend.database import engine, Base, SessionLocal
from backend.models import (
    User, Wallet, Asset, WalletBalance, Card, Transaction, Activity,
    Notification, Session as UserSession, LoginHistory, RecoveryCode, Account
)
from backend.auth import hash_password, generate_wallet_address, generate_reference
from backend.services.payment_service import ensure_user_accounts
from backend.services.address_service import ensure_user_token_addresses

def seed_database():
    print("Initializing VAYORA database schema...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        existing_assets = db.query(Asset).count()
        if existing_assets > 0:
            print("Database already contains assets. Clearing tables for fresh seed...")
            db.close()
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            db = SessionLocal()

        print("Seeding supported digital assets...")
        assets_data = [
            {"symbol": "USDT", "name": "Tether USD", "network": "TRC-20 / ERC-20", "price": 1.00, "icon": "tether", "status": "ACTIVE"},
            {"symbol": "USDC", "name": "USD Coin", "network": "ERC-20", "price": 1.00, "icon": "usdc", "status": "ACTIVE"},
            {"symbol": "BTC", "name": "Bitcoin", "network": "Native SegWit", "price": 68500.00, "icon": "bitcoin", "status": "ACTIVE"},
            {"symbol": "ETH", "name": "Ethereum", "network": "ERC-20", "price": 3500.00, "icon": "ethereum", "status": "ACTIVE"},
            {"symbol": "SOL", "name": "Solana", "network": "SPL", "price": 155.00, "icon": "solana", "status": "ACTIVE"},
        ]

        assets_map = {}
        for a in assets_data:
            asset = Asset(**a)
            db.add(asset)
            db.flush()
            assets_map[asset.symbol] = asset

        print("Seeding Users...")
        # 1. User A (Demo Sender)
        user_a = User(
            name="Demo Sender",
            email="sender@vayora.demo",
            password_hash=hash_password("Password@123"),
            email_verified=True,
            role="user",
            phone="+1 (555) 234-5678",
            avatar_color="#00f59b",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=15)
        )
        db.add(user_a)
        db.flush()

        # 2. User B (Demo Receiver)
        user_b = User(
            name="Demo Receiver",
            email="receiver@vayora.demo",
            password_hash=hash_password("Password@123"),
            email_verified=True,
            role="user",
            phone="+1 (555) 876-5432",
            avatar_color="#00d2ff",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)
        )
        db.add(user_b)
        db.flush()

        # 3. Admin User
        admin_user = User(
            name="Vayora System Admin",
            email="admin@vayora.demo",
            password_hash=hash_password("Admin@123"),
            email_verified=True,
            role="admin",
            phone="+1 (555) 999-0000",
            avatar_color="#a855f7",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=30)
        )
        db.add(admin_user)
        db.flush()

        # 4. System Settlement User (Deposit Faucet / Internal Clearing)
        settlement_user = User(
            name="VAYORA Settlement Network",
            email="settlement@vayora.network",
            password_hash=hash_password("SettlementPass123!"),
            email_verified=True,
            role="system",
            phone="+1 (800) 555-0199",
            avatar_color="#00f59b",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=60)
        )
        db.add(settlement_user)
        db.flush()

        print("Creating Wallets and Balances...")
        # Wallet for User A
        wallet_a = Wallet(
            user_id=user_a.user_id,
            wallet_type="MAIN",
            address="0x71C94B2E8F19D382A0F8372651B44390C12E7B90",
            inr_balance=12500.0,
            inr_balance_paise=1250000,
            created_at=user_a.created_at
        )
        db.add(wallet_a)
        db.flush()

        # Balances for User A: Exactly 500 USDT as requested
        balances_a = {
            "USDT": 500.0,
            "USDC": 150.0,
            "BTC": 0.05,
            "ETH": 0.85,
            "SOL": 5.0
        }
        for sym, amt in balances_a.items():
            wb = WalletBalance(
                wallet_id=wallet_a.wallet_id,
                asset_id=assets_map[sym].asset_id,
                amount=amt,
                available_amount=amt
            )
            db.add(wb)

        # Wallet for User B
        wallet_b = Wallet(
            user_id=user_b.user_id,
            wallet_type="MAIN",
            address="0x34A991E47B02D338FA8291410651A827B1390A77",
            inr_balance=0.0,
            inr_balance_paise=0,
            created_at=user_b.created_at
        )
        db.add(wallet_b)
        db.flush()

        # Balances for User B: Exactly 0 USDT as requested
        balances_b = {
            "USDT": 0.0,
            "USDC": 25.0,
            "BTC": 0.0,
            "ETH": 0.1,
            "SOL": 1.0
        }
        for sym, amt in balances_b.items():
            wb = WalletBalance(
                wallet_id=wallet_b.wallet_id,
                asset_id=assets_map[sym].asset_id,
                amount=amt,
                available_amount=amt
            )
            db.add(wb)

        # Wallet for Admin
        wallet_admin = Wallet(
            user_id=admin_user.user_id,
            wallet_type="TREASURY",
            address="0x999B0F33A27118B82736C52166904B8E110F99AA",
            inr_balance=250000.0,
            inr_balance_paise=25000000,
            created_at=admin_user.created_at
        )
        db.add(wallet_admin)
        db.flush()

        for sym, amt in {"USDT": 10000.0, "USDC": 5000.0, "BTC": 1.5, "ETH": 10.0, "SOL": 50.0}.items():
            wb = WalletBalance(
                wallet_id=wallet_admin.wallet_id,
                asset_id=assets_map[sym].asset_id,
                amount=amt,
                available_amount=amt
            )
            db.add(wb)

        # Wallet for Settlement Network
        wallet_settlement = Wallet(
            user_id=settlement_user.user_id,
            wallet_type="SETTLEMENT",
            address="0x5555C0F33A27118B82736C52166904B8E110F99CC",
            inr_balance=10000000.0,
            inr_balance_paise=1000000000,
            created_at=settlement_user.created_at
        )
        db.add(wallet_settlement)
        db.flush()

        for sym, amt in {"USDT": 100000.0, "USDC": 100000.0, "BTC": 100.0, "ETH": 500.0, "SOL": 10000.0}.items():
            wb = WalletBalance(
                wallet_id=wallet_settlement.wallet_id,
                asset_id=assets_map[sym].asset_id,
                amount=amt,
                available_amount=amt
            )
            db.add(wb)
        db.flush()

        print("Ensuring authoritative double-entry Accounts & dedicated Token Addresses...")
        for u in [user_a, user_b, admin_user, settlement_user]:
            ensure_user_accounts(db, u)
            ensure_user_token_addresses(db, u)
        db.flush()

        print("Seeding Virtual Cards...")
        card_a = Card(
            user_id=user_a.user_id,
            cardholder_name="DEMO SENDER",
            masked_number="•••• •••• •••• 5518",
            full_number="4532 8812 9043 5518",
            expiry="08/29",
            cvv="782",
            status="ACTIVE",
            balance=1500.0,
            daily_limit=5000.0,
            card_tier="BLACK OBSIDIAN",
            created_at=user_a.created_at
        )
        db.add(card_a)

        card_b = Card(
            user_id=user_b.user_id,
            cardholder_name="DEMO RECEIVER",
            masked_number="•••• •••• •••• 3309",
            full_number="4532 9941 7721 3309",
            expiry="11/30",
            cvv="419",
            status="ACTIVE",
            balance=250.0,
            daily_limit=2500.0,
            card_tier="EMERALD PRIME",
            created_at=user_b.created_at
        )
        db.add(card_b)

        print("Seeding Initial Transactions, Activities, and Notifications...")
        # Past transaction for User A (International client payment)
        tx_ref_initial = generate_reference("PAY")
        tx_a1 = Transaction(
            user_id=user_a.user_id,
            type="RECEIVE",
            asset_id=assets_map["USDT"].asset_id,
            amount=500.0,
            sender="Apex Digital Media LLC (client@apexdigital.com)",
            receiver=user_a.email,
            status="COMPLETED",
            reference_id=tx_ref_initial,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        db.add(tx_a1)

        act_a1 = Activity(
            user_id=user_a.user_id,
            action="RECEIVE",
            description="Received international milestone payment: 500.00 USDT from Apex Digital Media",
            reference_id=tx_ref_initial,
            ip_address="192.168.1.42",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        db.add(act_a1)

        notif_a1 = Notification(
            user_id=user_a.user_id,
            title="International Payment Received",
            message="500.00 USDT from Apex Digital Media LLC is now available in your VAYORA Wallet.",
            type="PAYMENT",
            is_read=False,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        db.add(notif_a1)

        # Welcome notification for User B
        notif_b = Notification(
            user_id=user_b.user_id,
            title="Welcome to VAYORA",
            message="Your multi-asset digital wallet is ready. Share your email or wallet address to receive international transfers.",
            type="SYSTEM",
            is_read=False,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add(notif_b)

        # Recovery Codes for User A
        for code in ["VYR9-4K21", "VYR8-7H99", "VYR3-1X04", "VYR5-9M82"]:
            rc = RecoveryCode(
                user_id=user_a.user_id,
                code_hash=hash_password(code),
                used=False
            )
            db.add(rc)

        # Login histories
        db.add(LoginHistory(
            user_id=user_a.user_id,
            device="Windows 11 / Chrome 124",
            ip_address="127.0.0.1",
            success=True,
            reason="Primary Session Login",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        ))

        db.commit()
        print("VAYORA Database successfully seeded!")
        print("--------------------------------------------------")
        print("DEMO CREDENTIALS:")
        print("USER A (Sender):   sender@vayora.demo   / Password@123 (500 USDT)")
        print("USER B (Receiver): receiver@vayora.demo / Password@123 (0 USDT)")
        print("ADMIN:             admin@vayora.demo    / Admin@123")
        print("--------------------------------------------------")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()

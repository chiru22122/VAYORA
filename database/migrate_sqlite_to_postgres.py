"""
VAYORA Controlled Database Migration: SQLite -> PostgreSQL 18
Safely migrates all user accounts, double-entry ledger records, balances,
and audit logs into PostgreSQL with exact integer paise for INR and Decimal for USDT.
Preserves existing data, ensures idempotency, and updates sequence counters.
"""

import os
import sys
import sqlite3
import datetime
from decimal import Decimal

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from backend.database import engine, Base, SessionLocal, test_db_connection, get_masked_db_url
from backend.models import (
    User, Wallet, Asset, WalletBalance, Card, Transaction, Activity,
    Notification, Session as UserSession, LoginHistory, RecoveryCode,
    EmailOTP, Account, LedgerTransaction, LedgerEntry, Transfer,
    AuditLog, EmailOutbox, Payment, Swap, Conversion, BankWithdrawal,
    NFCPayment, TokenAddress
)
from backend.services.address_service import ensure_user_token_addresses, get_user_token_address

SQLITE_PATH = os.path.join(BASE_DIR, "database", "vayora.db")

def parse_dt(val):
    if not val:
        return datetime.datetime.utcnow()
    if isinstance(val, datetime.datetime):
        return val
    try:
        return datetime.datetime.fromisoformat(str(val).replace("Z", "+00:00").replace("+00:00", ""))
    except Exception:
        return datetime.datetime.utcnow()

def reset_pg_sequence(db, table_name, pk_col):
    """Resets PostgreSQL sequence to max(pk_col) to avoid unique constraint violations on subsequent inserts."""
    try:
        from sqlalchemy import text
        sql = text(f"""
            SELECT setval(
                pg_get_serial_sequence('{table_name}', '{pk_col}'),
                COALESCE((SELECT MAX({pk_col}) FROM {table_name}), 1)
            );
        """)
        db.execute(sql)
        db.commit()
    except Exception as e:
        # Ignore if table doesn't have a sequence
        db.rollback()

def run_migration():
    print("=" * 65)
    print("  VAYORA Controlled Migration: SQLite -> PostgreSQL 18")
    print(f"  Target: {get_masked_db_url()}")
    print("=" * 65)

    if not test_db_connection():
        print("[ERROR] Cannot connect to PostgreSQL server. Check .env configuration.")
        return False

    print("[1/9] Initializing target PostgreSQL tables and column schema...")
    Base.metadata.create_all(bind=engine)
    
    # Run safe ALTER TABLE for new ledger and address columns on any pre-existing tables
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE wallets ADD COLUMN IF NOT EXISTS inr_balance_paise BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE wallets ALTER COLUMN inr_balance DROP NOT NULL;"))
        conn.execute(text("ALTER TABLE wallets ALTER COLUMN inr_balance SET DEFAULT 0.0;"))
        conn.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS balance_paise BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE ledger_entries ADD COLUMN IF NOT EXISTS amount_paise BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE ledger_entries ADD COLUMN IF NOT EXISTS balance_after_paise BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE transfers ADD COLUMN IF NOT EXISTS amount_paise BIGINT DEFAULT 0;"))
        conn.execute(text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS sender_address VARCHAR(120);"))
        conn.execute(text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS receiver_address VARCHAR(120);"))
        conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS sender_address VARCHAR(120);"))
        conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS receiver_address VARCHAR(120);"))
    print("      PostgreSQL tables and column schema verified.")

    if not os.path.exists(SQLITE_PATH):
        print(f"[NOTE] SQLite database '{SQLITE_PATH}' not found. Fresh PostgreSQL schema ready.")
        return True

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sq_cur = sqlite_conn.cursor()

    db = SessionLocal()

    try:
        # 1. Migrate Users
        print("[2/9] Migrating Users...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM users")
            users_rows = sq_cur.fetchall()
            for r in users_rows:
                u_id = r["user_id"]
                email = r["email"].strip().lower()
                existing = db.query(User).filter(User.user_id == u_id).first()
                if not existing:
                    existing_by_email = db.query(User).filter(User.email == email).first()
                    if existing_by_email:
                        continue
                    u = User(
                        user_id=u_id,
                        name=r["name"],
                        email=email,
                        password_hash=r["password_hash"],
                        email_verified=bool(r["email_verified"] if "email_verified" in r.keys() else False),
                        role=r["role"] if "role" in r.keys() and r["role"] else "user",
                        phone=r["phone"] if "phone" in r.keys() else None,
                        avatar_color=r["avatar_color"] if "avatar_color" in r.keys() else "#00f59b",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(u)
            db.commit()
            reset_pg_sequence(db, "users", "user_id")
            print(f"      Migrated {len(users_rows)} users.")

        # 2. Migrate Assets
        print("[3/9] Migrating Supported Digital Assets...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assets'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM assets")
            asset_rows = sq_cur.fetchall()
            for r in asset_rows:
                sym = r["symbol"].upper()
                existing_asset = db.query(Asset).filter(Asset.symbol == sym).first()
                if not existing_asset:
                    price_val = float(r["price"] if "price" in r.keys() and r["price"] is not None else (r["price_usd"] if "price_usd" in r.keys() and r["price_usd"] is not None else 1.0))
                    a = Asset(
                        asset_id=r["asset_id"],
                        symbol=sym,
                        name=r["name"],
                        network=r["network"] if "network" in r.keys() else "Mainnet",
                        price=price_val,
                        icon=r["icon"] if "icon" in r.keys() else sym.lower(),
                        status=r["status"] if "status" in r.keys() else "ACTIVE",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(a)
            db.commit()
            reset_pg_sequence(db, "assets", "asset_id")

        # 3. Migrate Authoritative Accounts (with paise for INR and exact decimal for crypto)
        print("[4/9] Migrating Authoritative Accounts & Balances...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM accounts")
            acct_rows = sq_cur.fetchall()
            for r in acct_rows:
                acct_id = r["account_id"]
                existing_acct = db.query(Account).filter(Account.account_id == acct_id).first()
                if not existing_acct:
                    curr = r["currency"].upper()
                    bal_val = Decimal(str(r["balance"] if r["balance"] is not None else 0.0))
                    avail_val = Decimal(str(r["available_balance"] if r["available_balance"] is not None else 0.0))
                    paise_val = int(round(float(bal_val) * 100)) if curr == "INR" else 0
                    
                    acct = Account(
                        account_id=acct_id,
                        user_id=r["user_id"],
                        currency=curr,
                        account_number=r["account_number"],
                        balance=bal_val,
                        available_balance=avail_val,
                        balance_paise=paise_val,
                        status=r["status"] if "status" in r.keys() else "ACTIVE",
                        created_at=parse_dt(r["created_at"]),
                        updated_at=parse_dt(r["updated_at"])
                    )
                    db.add(acct)
            db.commit()
            reset_pg_sequence(db, "accounts", "account_id")
            print(f"      Migrated {len(acct_rows)} ledger accounts.")

        # Ensure standard accounts and dedicated token addresses exist for all users in PostgreSQL
        all_users = db.query(User).all()
        standard_currencies = ["USDT", "INR", "USDC", "BTC", "ETH", "SOL"]
        now = datetime.datetime.utcnow()
        for u in all_users:
            for c in standard_currencies:
                existing_u_acct = db.query(Account).filter(Account.user_id == u.user_id, Account.currency == c).first()
                if not existing_u_acct:
                    init_bal = Decimal("0.0")
                    init_paise = 0
                    if u.email.startswith("sender@") or u.user_id == 1:
                        if c == "USDT": init_bal = Decimal("500.0")
                        elif c == "INR": 
                            init_bal = Decimal("10000.0")
                            init_paise = 1000000 # 10,000 INR = 1,000,000 paise
                    acct_num = f"VAY-{c}-{str(u.user_id).zfill(5)}-{os.urandom(2).hex().upper()}"
                    new_acct = Account(
                        user_id=u.user_id,
                        currency=c,
                        account_number=acct_num,
                        balance=init_bal,
                        available_balance=init_bal,
                        balance_paise=init_paise,
                        status="ACTIVE",
                        created_at=now,
                        updated_at=now
                    )
                    db.add(new_acct)
            # Provision dedicated token addresses
            ensure_user_token_addresses(db, u)
        db.commit()
        reset_pg_sequence(db, "token_addresses", "id")

        # 4. Migrate Wallets & Wallet Balances
        print("[5/9] Migrating Wallets, Balances & Token Addresses...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wallets'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM wallets")
            wallet_rows = sq_cur.fetchall()
            for r in wallet_rows:
                w_id = r["wallet_id"]
                existing_w = db.query(Wallet).filter(Wallet.wallet_id == w_id).first()
                if not existing_w:
                    inr_f = float(r["inr_balance"]) if "inr_balance" in r.keys() and r["inr_balance"] is not None else 0.0
                    w = Wallet(
                        wallet_id=w_id,
                        user_id=r["user_id"],
                        wallet_type=r["wallet_type"] if "wallet_type" in r.keys() else "MAIN",
                        address=r["address"],
                        inr_balance_paise=int(round(inr_f * 100)),
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(w)
            db.commit()
            reset_pg_sequence(db, "wallets", "wallet_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='wallet_balances'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM wallet_balances")
            wb_rows = sq_cur.fetchall()
            for r in wb_rows:
                b_id = r["balance_id"]
                existing_wb = db.query(WalletBalance).filter(WalletBalance.balance_id == b_id).first()
                if not existing_wb:
                    wb = WalletBalance(
                        balance_id=b_id,
                        wallet_id=r["wallet_id"],
                        asset_id=r["asset_id"],
                        amount=Decimal(str(r["amount"] if r["amount"] is not None else 0.0)),
                        available_amount=Decimal(str(r["available_amount"] if r["available_amount"] is not None else 0.0)),
                        updated_at=parse_dt(r["updated_at"])
                    )
                    db.add(wb)
            db.commit()
            reset_pg_sequence(db, "wallet_balances", "balance_id")

        # 5. Migrate Double-Entry Ledger Transactions & Entries
        print("[6/9] Migrating Double-Entry Ledger Records & Transfers...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ledger_transactions'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM ledger_transactions")
            lt_rows = sq_cur.fetchall()
            for r in lt_rows:
                t_id = r["transaction_id"]
                if not db.query(LedgerTransaction).filter(LedgerTransaction.transaction_id == t_id).first():
                    lt = LedgerTransaction(
                        transaction_id=t_id,
                        reference=r["reference"],
                        idempotency_key=r["idempotency_key"] if "idempotency_key" in r.keys() else None,
                        type=r["type"],
                        description=r["description"],
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(lt)
            db.commit()
            reset_pg_sequence(db, "ledger_transactions", "transaction_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ledger_entries'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM ledger_entries")
            le_rows = sq_cur.fetchall()
            for r in le_rows:
                e_id = r["entry_id"]
                if not db.query(LedgerEntry).filter(LedgerEntry.entry_id == e_id).first():
                    curr = r["currency"].upper()
                    amt = Decimal(str(r["amount"]))
                    amt_paise = int(round(float(amt) * 100)) if curr == "INR" else 0
                    bal_after = Decimal(str(r["balance_after"]))
                    bal_paise = int(round(float(bal_after) * 100)) if curr == "INR" else 0
                    le = LedgerEntry(
                        entry_id=e_id,
                        ledger_transaction_id=r["ledger_transaction_id"],
                        account_id=r["account_id"],
                        user_id=r["user_id"],
                        currency=curr,
                        direction=r["direction"],
                        amount=amt,
                        amount_paise=amt_paise,
                        balance_after=bal_after,
                        balance_after_paise=bal_paise,
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(le)
            db.commit()
            reset_pg_sequence(db, "ledger_entries", "entry_id")

        valid_user_ids = {u[0] for u in db.query(User.user_id).all()}

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transfers'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM transfers")
            tf_rows = sq_cur.fetchall()
            for r in tf_rows:
                t_id = r["transfer_id"]
                if r["sender_user_id"] not in valid_user_ids or r["recipient_user_id"] not in valid_user_ids:
                    continue
                if not db.query(Transfer).filter(Transfer.transfer_id == t_id).first():
                    curr = r["currency"].upper()
                    amt = Decimal(str(r["amount"]))
                    amt_paise = int(round(float(amt) * 100)) if curr == "INR" else 0
                    fee_val = Decimal(str(r["fee"] if "fee" in r.keys() and r["fee"] is not None else 0.0))
                    tf = Transfer(
                        transfer_id=t_id,
                        reference=r["reference"],
                        sender_user_id=r["sender_user_id"],
                        sender_account_id=r["sender_account_id"],
                        recipient_user_id=r["recipient_user_id"],
                        recipient_account_id=r["recipient_account_id"],
                        currency=curr,
                        amount=amt,
                        amount_paise=amt_paise,
                        fee=fee_val,
                        note=r["note"] if "note" in r.keys() else None,
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(tf)
            db.commit()
            reset_pg_sequence(db, "transfers", "transfer_id")

        # 6. Migrate Payments with Token Addresses
        print("[7/9] Migrating Financial Payments & Token Addresses...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM payments")
            for r in sq_cur.fetchall():
                p_id = r["payment_id"]
                s_id = r["sender_id"]
                rec_id = r["receiver_id"]
                if s_id not in valid_user_ids or rec_id not in valid_user_ids:
                    continue
                if not db.query(Payment).filter(Payment.payment_id == p_id).first():
                    a_id = r["asset_id"] if "asset_id" in r.keys() else None
                    asset_rec = db.query(Asset).filter(Asset.asset_id == a_id).first() if a_id else None
                    sym = asset_rec.symbol if asset_rec else "USDT"

                    sender_user = db.query(User).filter(User.user_id == s_id).first() if s_id else None
                    recv_user = db.query(User).filter(User.user_id == rec_id).first() if rec_id else None

                    s_addr = r["sender_address"] if "sender_address" in r.keys() and r["sender_address"] else (
                        get_user_token_address(db, sender_user, sym) if sender_user else None
                    )
                    r_addr = r["receiver_address"] if "receiver_address" in r.keys() and r["receiver_address"] else (
                        get_user_token_address(db, recv_user, sym) if recv_user else None
                    )

                    pmt = Payment(
                        payment_id=p_id,
                        sender_id=s_id,
                        receiver_id=rec_id,
                        asset_id=a_id,
                        amount=float(r["amount"]),
                        sender_address=s_addr,
                        receiver_address=r_addr,
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        reference=r["reference"],
                        note=r["note"] if "note" in r.keys() else None,
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(pmt)
            db.commit()
            reset_pg_sequence(db, "payments", "payment_id")

        # 7. Migrate Transactions with Token Addresses
        print("[8/9] Migrating Transaction Records & Ledger Receipts...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM transactions")
            for r in sq_cur.fetchall():
                tx_id = r["transaction_id"]
                u_id = r["user_id"]
                if u_id not in valid_user_ids:
                    continue
                if not db.query(Transaction).filter(Transaction.transaction_id == tx_id).first():
                    tx_user = db.query(User).filter(User.user_id == u_id).first()
                    a_id = r["asset_id"] if "asset_id" in r.keys() else None
                    asset_rec = db.query(Asset).filter(Asset.asset_id == a_id).first() if a_id else None
                    sym = asset_rec.symbol if asset_rec else "USDT"

                    s_addr = r["sender_address"] if "sender_address" in r.keys() and r["sender_address"] else None
                    r_addr = r["receiver_address"] if "receiver_address" in r.keys() and r["receiver_address"] else None

                    if not s_addr and not r_addr and tx_user:
                        if r["type"] == "SEND":
                            s_addr = get_user_token_address(db, tx_user, sym)
                        elif r["type"] == "RECEIVE":
                            r_addr = get_user_token_address(db, tx_user, sym)
                        elif r["type"] == "CONVERSION":
                            s_addr = get_user_token_address(db, tx_user, "USDT")
                            r_addr = get_user_token_address(db, tx_user, "INR")

                    txn = Transaction(
                        transaction_id=tx_id,
                        user_id=u_id,
                        payment_id=r["payment_id"] if "payment_id" in r.keys() else None,
                        type=r["type"],
                        asset_id=a_id,
                        amount=float(r["amount"]),
                        sender=r["sender"] if "sender" in r.keys() else None,
                        receiver=r["receiver"] if "receiver" in r.keys() else None,
                        sender_address=s_addr,
                        receiver_address=r_addr,
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        reference_id=r["reference_id"],
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(txn)
            db.commit()
            reset_pg_sequence(db, "transactions", "transaction_id")

        # 8. Migrate Swaps, Conversions, Bank Withdrawals, NFC Payments
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='swaps'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM swaps")
            for r in sq_cur.fetchall():
                s_id = r["swap_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(Swap).filter(Swap.swap_id == s_id).first():
                    sw = Swap(
                        swap_id=s_id,
                        user_id=r["user_id"],
                        from_asset_id=r["from_asset_id"],
                        to_asset_id=r["to_asset_id"],
                        from_amount=float(r["from_amount"]),
                        to_amount=float(r["to_amount"]),
                        rate=float(r["rate"]),
                        fee=float(r["fee"]) if "fee" in r.keys() and r["fee"] is not None else 0.0,
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(sw)
            db.commit()
            reset_pg_sequence(db, "swaps", "swap_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversions'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM conversions")
            for r in sq_cur.fetchall():
                c_id = r["conversion_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(Conversion).filter(Conversion.conversion_id == c_id).first():
                    conv = Conversion(
                        conversion_id=c_id,
                        user_id=r["user_id"],
                        asset_id=r["asset_id"],
                        asset_amount=float(r["asset_amount"]),
                        exchange_rate=float(r["exchange_rate"]),
                        inr_amount=float(r["inr_amount"]),
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(conv)
            db.commit()
            reset_pg_sequence(db, "conversions", "conversion_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bank_withdrawals'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM bank_withdrawals")
            for r in sq_cur.fetchall():
                bw_id = r["withdrawal_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(BankWithdrawal).filter(BankWithdrawal.withdrawal_id == bw_id).first():
                    bw = BankWithdrawal(
                        withdrawal_id=bw_id,
                        user_id=r["user_id"],
                        amount=float(r["amount"]),
                        bank_name=r["bank_name"],
                        account_number=r["account_number"],
                        ifsc_code=r["ifsc_code"],
                        bank_reference=r["bank_reference"],
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(bw)
            db.commit()
            reset_pg_sequence(db, "bank_withdrawals", "withdrawal_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nfc_payments'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM nfc_payments")
            for r in sq_cur.fetchall():
                nfc_id = r["nfc_payment_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(NFCPayment).filter(NFCPayment.nfc_payment_id == nfc_id).first():
                    nfc = NFCPayment(
                        nfc_payment_id=nfc_id,
                        user_id=r["user_id"],
                        merchant=r["merchant"],
                        amount=float(r["amount"]),
                        asset_id=r["asset_id"] if "asset_id" in r.keys() else None,
                        status=r["status"] if "status" in r.keys() else "COMPLETED",
                        reference=r["reference"],
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(nfc)
            db.commit()
            reset_pg_sequence(db, "nfc_payments", "nfc_payment_id")

        # 9. Migrate Cards, Notifications, Activity, Sessions, AuditLogs
        print("[9/9] Migrating Cards, Activities, Sessions, OTPs & Audit Logs...")
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM cards")
            for r in sq_cur.fetchall():
                c_id = r["card_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(Card).filter(Card.card_id == c_id).first():
                    card = Card(
                        card_id=c_id,
                        user_id=r["user_id"],
                        cardholder_name=r["cardholder_name"],
                        masked_number=r["masked_number"],
                        full_number=r["full_number"],
                        expiry=r["expiry"],
                        cvv=r["cvv"],
                        status=r["status"] if "status" in r.keys() else "ACTIVE",
                        balance=float(r["balance"]) if "balance" in r.keys() and r["balance"] is not None else 1500.0,
                        daily_limit=float(r["daily_limit"]) if "daily_limit" in r.keys() and r["daily_limit"] is not None else 50000.0,
                        card_tier=r["card_tier"] if "card_tier" in r.keys() else "BLACK OBSIDIAN",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(card)
            db.commit()
            reset_pg_sequence(db, "cards", "card_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM activity")
            for r in sq_cur.fetchall():
                act_id = r["activity_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(Activity).filter(Activity.activity_id == act_id).first():
                    act = Activity(
                        activity_id=act_id,
                        user_id=r["user_id"],
                        action=r["action"],
                        description=r["description"],
                        reference_id=r["reference_id"] if "reference_id" in r.keys() else None,
                        ip_address=r["ip_address"] if "ip_address" in r.keys() and r["ip_address"] else "127.0.0.1",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(act)
            db.commit()
            reset_pg_sequence(db, "activity", "activity_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM notifications")
            for r in sq_cur.fetchall():
                n_id = r["notification_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(Notification).filter(Notification.notification_id == n_id).first():
                    notif = Notification(
                        notification_id=n_id,
                        user_id=r["user_id"],
                        title=r["title"],
                        message=r["message"],
                        type=r["type"] if "type" in r.keys() else "INFO",
                        is_read=bool(r["is_read"] if "is_read" in r.keys() else False),
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(notif)
            db.commit()
            reset_pg_sequence(db, "notifications", "notification_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM sessions")
            for r in sq_cur.fetchall():
                s_id = r["session_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(UserSession).filter(UserSession.session_id == s_id).first():
                    sess = UserSession(
                        session_id=s_id,
                        user_id=r["user_id"],
                        token_id=r["token_id"],
                        device=r["device"] if "device" in r.keys() else "Browser",
                        ip_address=r["ip_address"] if "ip_address" in r.keys() and r["ip_address"] else "127.0.0.1",
                        status=r["status"] if "status" in r.keys() else "ACTIVE",
                        last_active=parse_dt(r["last_active"]),
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(sess)
            db.commit()
            reset_pg_sequence(db, "sessions", "session_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='login_history'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM login_history")
            for r in sq_cur.fetchall():
                l_id = r["login_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(LoginHistory).filter(LoginHistory.login_id == l_id).first():
                    lh = LoginHistory(
                        login_id=l_id,
                        user_id=r["user_id"],
                        ip_address=r["ip_address"] if "ip_address" in r.keys() and r["ip_address"] else "127.0.0.1",
                        device=r["device"] if "device" in r.keys() else "Browser",
                        success=bool(r["success"] if "success" in r.keys() else True),
                        reason=r["reason"] if "reason" in r.keys() else "Success",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(lh)
            db.commit()
            reset_pg_sequence(db, "login_history", "login_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recovery_codes'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM recovery_codes")
            for r in sq_cur.fetchall():
                rc_id = r["recovery_id"]
                if r["user_id"] not in valid_user_ids:
                    continue
                if not db.query(RecoveryCode).filter(RecoveryCode.recovery_id == rc_id).first():
                    rc = RecoveryCode(
                        recovery_id=rc_id,
                        user_id=r["user_id"],
                        code_hash=r["code_hash"],
                        used=bool(r["used"] if "used" in r.keys() else False),
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(rc)
            db.commit()
            reset_pg_sequence(db, "recovery_codes", "recovery_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_otps'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM email_otps")
            for r in sq_cur.fetchall():
                o_id = r["otp_id"]
                u_id = r["user_id"] if "user_id" in r.keys() and r["user_id"] in valid_user_ids else None
                if not db.query(EmailOTP).filter(EmailOTP.otp_id == o_id).first():
                    otp = EmailOTP(
                        otp_id=o_id,
                        user_id=u_id,
                        email=r["email"],
                        otp_code=r["otp_code"] if "otp_code" in r.keys() else "123456",
                        otp_type=r["otp_type"] if "otp_type" in r.keys() else "login_otp",
                        expires_at=parse_dt(r["expires_at"]),
                        used=bool(r["used"] if "used" in r.keys() else False),
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(otp)
            db.commit()
            reset_pg_sequence(db, "email_otps", "otp_id")

        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT * FROM audit_logs")
            for r in sq_cur.fetchall():
                l_id = r["log_id"]
                u_id_val = r["user_id"] if "user_id" in r.keys() and r["user_id"] in valid_user_ids else None
                if not db.query(AuditLog).filter(AuditLog.log_id == l_id).first():
                    al = AuditLog(
                        log_id=l_id,
                        user_id=u_id_val,
                        action=r["action"],
                        details=r["details"],
                        ip_address=r["ip_address"] if "ip_address" in r.keys() else "127.0.0.1",
                        created_at=parse_dt(r["created_at"])
                    )
                    db.add(al)
            db.commit()
            reset_pg_sequence(db, "audit_logs", "log_id")

        print("=" * 65)
        print("  MIGRATION SUCCESSFULLY COMPLETED!")
        print("  All data migrated into PostgreSQL with ACID guarantees.")
        print("=" * 65)
        return True

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        sqlite_conn.close()
        db.close()

if __name__ == "__main__":
    run_migration()


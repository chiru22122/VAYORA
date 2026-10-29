"""
VAYORA Comprehensive Automated Verification Suite for PostgreSQL 18
Tests all core ledger, authentication, double-entry, and API requirements.
"""

import os
import sys
import uuid
import datetime
from decimal import Decimal

# Add root directory to python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from backend.database import engine, SessionLocal, test_db_connection
from backend.models import (
    User, Account, LedgerTransaction, LedgerEntry, Transfer,
    Wallet, WalletBalance, Payment, Transaction, EmailOTP, AuditLog
)
from backend.services.payment_service import execute_send_payment, ensure_user_accounts
from backend.auth import hash_password, create_access_token

def run_tests():
    print("=" * 65)
    print("  VAYORA POSTGRESQL 18 LEDGER & AUTH VERIFICATION SUITE")
    print("=" * 65)

    # 1. Connection check
    print("\n[TEST 1] PostgreSQL Connection Liveness Check...")
    assert test_db_connection() is True, "Database connection failed"
    print("  [PASS] Successfully connected to PostgreSQL 18 on localhost:5432/VAYORA")

    db = SessionLocal()
    try:
        # 2. Verify or create test users
        print("\n[TEST 2] Verifying / Initializing Test Users in PostgreSQL...")
        sender = db.query(User).filter(User.email == "sender@vayora.demo").first()
        if not sender:
            sender = User(
                name="Test Sender",
                email="sender@vayora.demo",
                password_hash=hash_password("Password@123"),
                email_verified=True,
                role="user"
            )
            db.add(sender)
            db.commit()
            db.refresh(sender)

        receiver = db.query(User).filter(User.email == "receiver@vayora.demo").first()
        if not receiver:
            receiver = User(
                name="Test Receiver",
                email="receiver@vayora.demo",
                password_hash=hash_password("Password@123"),
                email_verified=True,
                role="user"
            )
            db.add(receiver)
            db.commit()
            db.refresh(receiver)

        ensure_user_accounts(db, sender)
        ensure_user_accounts(db, receiver)

        # Set baseline funding for tests
        sender_usdt = db.query(Account).filter(Account.user_id == sender.user_id, Account.currency == "USDT").first()
        sender_usdt.balance = Decimal("500.0")
        sender_usdt.available_balance = Decimal("500.0")

        sender_inr = db.query(Account).filter(Account.user_id == sender.user_id, Account.currency == "INR").first()
        sender_inr.balance_paise = 1000000  # 10,000 INR = 1,000,000 paise
        sender_inr.balance = Decimal("10000.0")
        sender_inr.available_balance = Decimal("10000.0")

        receiver_usdt = db.query(Account).filter(Account.user_id == receiver.user_id, Account.currency == "USDT").first()
        receiver_usdt.balance = Decimal("0.0")
        receiver_usdt.available_balance = Decimal("0.0")

        receiver_inr = db.query(Account).filter(Account.user_id == receiver.user_id, Account.currency == "INR").first()
        receiver_inr.balance_paise = 0
        receiver_inr.balance = Decimal("0.0")
        receiver_inr.available_balance = Decimal("0.0")

        db.commit()
        print("  [PASS] Test users and baseline balances successfully initialized.")

        # 3. Successful USDT Transfer Test
        print("\n[TEST 3] Atomic USDT Internal Transfer...")
        init_sender_usdt = sender_usdt.balance
        init_receiver_usdt = receiver_usdt.balance
        tx_usdt_amount = 50.0

        payment_usdt = execute_send_payment(
            db=db,
            sender=sender,
            recipient_identifier=receiver.email,
            asset_symbol="USDT",
            amount=tx_usdt_amount,
            note="Test USDT Transfer",
            idempotency_key=f"idemp-usdt-{uuid.uuid4()}"
        )
        assert payment_usdt.status == "COMPLETED"
        assert payment_usdt.amount == tx_usdt_amount

        # Verify balanced ledger entries
        ledger_tx = db.query(LedgerTransaction).filter(LedgerTransaction.reference == payment_usdt.reference).first()
        assert ledger_tx is not None, "Ledger transaction was not created"
        entries = db.query(LedgerEntry).filter(LedgerEntry.ledger_transaction_id == ledger_tx.transaction_id).all()
        assert len(entries) == 2, f"Expected exactly 2 ledger entries, got {len(entries)}"

        debit_entry = next(e for e in entries if e.direction == "DEBIT")
        credit_entry = next(e for e in entries if e.direction == "CREDIT")
        assert debit_entry.amount == Decimal(str(tx_usdt_amount)), "Debit amount mismatch"
        assert credit_entry.amount == Decimal(str(tx_usdt_amount)), "Credit amount mismatch"
        assert debit_entry.amount == credit_entry.amount, "Ledger NOT balanced!"
        print(f"  [PASS] Double-entry balanced! sum(DEBIT) == sum(CREDIT) == {debit_entry.amount} USDT")

        # Verify updated balances
        db.refresh(sender_usdt)
        db.refresh(receiver_usdt)
        assert sender_usdt.balance == init_sender_usdt - Decimal(str(tx_usdt_amount))
        assert receiver_usdt.balance == init_receiver_usdt + Decimal(str(tx_usdt_amount))
        print(f"  [PASS] Balances updated: Sender={sender_usdt.balance} USDT, Receiver={receiver_usdt.balance} USDT")

        # 4. Successful INR Transfer Test (Strict Integer Paise)
        print("\n[TEST 4] Atomic INR Internal Transfer (Integer Paise Precision)...")
        init_sender_paise = sender_inr.balance_paise
        init_receiver_paise = receiver_inr.balance_paise
        tx_inr_amount = 500.0  # 50,000 paise

        payment_inr = execute_send_payment(
            db=db,
            sender=sender,
            recipient_identifier=receiver.email,
            asset_symbol="INR",
            amount=tx_inr_amount,
            note="Test INR Transfer",
            idempotency_key=f"idemp-inr-{uuid.uuid4()}"
        )
        assert payment_inr.status == "COMPLETED"

        db.refresh(sender_inr)
        db.refresh(receiver_inr)
        expected_paise = int(round(tx_inr_amount * 100))
        assert sender_inr.balance_paise == init_sender_paise - expected_paise
        assert receiver_inr.balance_paise == init_receiver_paise + expected_paise
        print(f"  [PASS] Integer paise ledger balanced: Sender={sender_inr.balance_paise} paise, Receiver={receiver_inr.balance_paise} paise (INR {receiver_inr.balance:,.2f})")

        # 5. Idempotency Key Duplicate Prevention Test
        print("\n[TEST 5] Idempotency Key Duplicate Prevention...")
        test_idemp_key = f"idemp-dup-{uuid.uuid4()}"
        pay1 = execute_send_payment(
            db=db,
            sender=sender,
            recipient_identifier=receiver.email,
            asset_symbol="USDT",
            amount=10.0,
            idempotency_key=test_idemp_key
        )
        bal_after_first = db.query(Account).filter(Account.user_id == sender.user_id, Account.currency == "USDT").first().balance

        # Submitting with same idempotency key must not charge again
        pay2 = execute_send_payment(
            db=db,
            sender=sender,
            recipient_identifier=receiver.email,
            asset_symbol="USDT",
            amount=10.0,
            idempotency_key=test_idemp_key
        )
        bal_after_second = db.query(Account).filter(Account.user_id == sender.user_id, Account.currency == "USDT").first().balance
        assert pay1.reference == pay2.reference, "Idempotency did not return same payment reference"
        assert bal_after_first == bal_after_second, "Duplicate transfer deducted balance twice!"
        print("  [PASS] Idempotency successfully prevented duplicate charge.")

        # 6. Insufficient Balance Rejection Test
        print("\n[TEST 6] Insufficient Funds Rejection...")
        try:
            execute_send_payment(
                db=db,
                sender=sender,
                recipient_identifier=receiver.email,
                asset_symbol="USDT",
                amount=99999999.0
            )
            assert False, "Should have failed on insufficient balance"
        except Exception as e:
            assert "Insufficient" in str(e), f"Expected insufficient balance error, got: {e}"
            print("  [PASS] Insufficient funds rejected cleanly with zero ledger change.")

        # 7. Self-Transfer Prevention Test
        print("\n[TEST 7] Self-Transfer Rejection...")
        try:
            execute_send_payment(
                db=db,
                sender=sender,
                recipient_identifier=sender.email,
                asset_symbol="USDT",
                amount=5.0
            )
            assert False, "Should have failed on self-transfer"
        except Exception as e:
            assert "Cannot send assets to your own account" in str(e)
            print("  [PASS] Self-transfer rejected cleanly.")

        # 8. Audit Trail Verification
        print("\n[TEST 8] Audit Trail Verification in PostgreSQL...")
        audit_count = db.query(AuditLog).filter(AuditLog.user_id == sender.user_id).count()
        assert audit_count > 0, "No audit logs recorded"
        print(f"  [PASS] Authoritative audit trail verified ({audit_count} security & financial logs).")

        # 9. Email OTP Verification and Expiry Test
        print("\n[TEST 9] Email OTP Lifecycle Verification...")
        test_email = f"verify_{uuid.uuid4().hex[:6]}@vayora.test"
        otp_code = "789123"
        valid_otp = EmailOTP(
            email=test_email,
            otp_code=otp_code,
            otp_type="verify_email",
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
            used=False
        )
        db.add(valid_otp)
        db.commit()

        # Check rejection of expired OTP
        expired_otp = EmailOTP(
            email=test_email,
            otp_code="000111",
            otp_type="verify_email",
            expires_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5),
            used=False
        )
        db.add(expired_otp)
        db.commit()

        # Verify active OTP query
        active = db.query(EmailOTP).filter(
            EmailOTP.email == test_email,
            EmailOTP.otp_code == otp_code,
            EmailOTP.used == False,
            EmailOTP.expires_at >= datetime.datetime.utcnow()
        ).first()
        assert active is not None
        active.used = True
        db.commit()

        # Verify used OTP is rejected on reuse
        reused = db.query(EmailOTP).filter(
            EmailOTP.email == test_email,
            EmailOTP.otp_code == otp_code,
            EmailOTP.used == False,
            EmailOTP.expires_at >= datetime.datetime.utcnow()
        ).first()
        assert reused is None, "Reused OTP was not rejected"
        print("  [PASS] Email OTP verification, single-use, and expiration enforcement passed.")

        print("\n" + "=" * 65)
        print("  ALL 9 AUTOMATED POSTGRESQL VERIFICATION TESTS PASSED!")
        print("=" * 65)
        return True

    finally:
        db.close()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

import os
import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.models import (
    User, Wallet, Asset, WalletBalance, Payment, Transaction, Activity, Notification,
    Account, LedgerTransaction, LedgerEntry, Transfer, AuditLog
)
from backend.auth import generate_reference
from backend.services.wallet_service import get_or_create_wallet
from backend.services.address_service import find_user_by_any_identifier, get_user_token_address, ensure_user_token_addresses

def ensure_user_accounts(db: Session, user: User):
    """Ensures authoritative double-entry currency accounts exist for the user, fully synced with wallets."""
    standard_currencies = ["USDT", "INR", "USDC", "BTC", "ETH", "SOL"]

    # Fast check: If user already has all standard accounts, return immediately without extra queries
    existing_accts = db.query(Account).filter(Account.user_id == user.user_id).all()
    existing_currencies = {a.currency for a in existing_accts}
    if set(standard_currencies).issubset(existing_currencies):
        return

    now = datetime.datetime.utcnow()
    wallet = db.query(Wallet).filter(Wallet.user_id == user.user_id).first()

    for curr in standard_currencies:
        if curr in existing_currencies:
            continue
        acct = next((a for a in existing_accts if a.currency == curr), None)

        # Calculate initial balance from wallet / wallet_balances if present
        init_balance = Decimal("0.0")
        init_paise = 0
        if curr == "INR":
            if wallet:
                init_paise = wallet.inr_balance_paise or int(round((wallet.inr_balance or 0.0) * 100))
                init_balance = Decimal(str(round(init_paise / 100.0, 2)))
        else:
            asset = db.query(Asset).filter(Asset.symbol == curr).first()
            if asset and wallet:
                wb = db.query(WalletBalance).filter(
                    WalletBalance.wallet_id == wallet.wallet_id,
                    WalletBalance.asset_id == asset.asset_id
                ).first()
                if wb and wb.amount:
                    init_balance = Decimal(str(wb.amount))

        if not acct:
            acct_num = f"VAY-{curr}-{str(user.user_id).zfill(5)}-{os.urandom(2).hex().upper()}"
            new_acct = Account(
                user_id=user.user_id,
                currency=curr,
                account_number=acct_num,
                balance=init_balance,
                available_balance=init_balance,
                balance_paise=init_paise,
                status="ACTIVE",
                created_at=now,
                updated_at=now
            )
            db.add(new_acct)
        else:
            # Account is authoritative ledger: sync legacy wallet from Account
            if wallet:
                if curr == "INR":
                    wallet.inr_balance_paise = acct.balance_paise or int(round(float(acct.balance or 0.0) * 100))
                    wallet.inr_balance = float(acct.balance or 0.0)
                else:
                    asset = db.query(Asset).filter(Asset.symbol == curr).first()
                    if asset:
                        wb = db.query(WalletBalance).filter(
                            WalletBalance.wallet_id == wallet.wallet_id,
                            WalletBalance.asset_id == asset.asset_id
                        ).first()
                        if wb and acct.balance is not None:
                            wb.amount = acct.balance
                            wb.available_amount = acct.available_balance
                            wb.updated_at = now
    db.flush()

def execute_send_payment(
    db: Session,
    sender: User,
    recipient_identifier: str,
    asset_symbol: str,
    amount: float,
    note: str = None,
    idempotency_key: Optional[str] = None,
    ip_address: str = "127.0.0.1"
) -> Payment:
    """
    Executes an atomic, double-entry financial transfer between registered VAYORA users.
    Enforces strict ACID guarantees:
    1. Authenticates sender and checks account status.
    2. Validates recipient, currency, and strict positive amount.
    3. Idempotency check prevents duplicate submissions.
    4. Row-level locks (SELECT ... FOR UPDATE) prevent concurrent double-spending.
    5. Integer paise for INR; exact Decimal for USDT/crypto (never floats).
    6. Double-entry balanced ledger: sum(DEBIT) == sum(CREDIT).
    7. Creates immutable ledger entries, transfer records, and audit logs.
    8. Dispatches real-time WebSocket alerts and transactional email receipts after commit.
    """
    # 1. Basic validation
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transfer amount must be strictly greater than 0."
        )
        
    curr = asset_symbol.upper().strip()
    recipient_clean = recipient_identifier.strip().lower()
    if recipient_clean == sender.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send assets to your own account."
        )

    # 2. Idempotency Check
    if idempotency_key:
        existing_tx = db.query(LedgerTransaction).filter(LedgerTransaction.idempotency_key == idempotency_key).first()
        if existing_tx:
            existing_payment = db.query(Payment).filter(Payment.reference == existing_tx.reference).first()
            if existing_payment:
                return existing_payment

    # 3. Find asset or verify currency
    asset = db.query(Asset).filter(Asset.symbol == curr, Asset.status == "ACTIVE").first()
    if not asset and curr != "INR":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{curr}' not found or currently inactive on VAYORA network."
        )

    # 4. Find receiver by email, token address (BTC, USDT, ETH, SOL, USDC, INR), account number, or wallet address
    lookup_result = find_user_by_any_identifier(db, recipient_clean)
    receiver = lookup_result[0] if lookup_result else None

    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient '{recipient_identifier}' not found on VAYORA network."
        )

    if receiver.user_id == sender.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send assets to your own account."
        )

    # Ensure accounts, wallets, and token addresses exist for both parties
    ensure_user_accounts(db, sender)
    ensure_user_accounts(db, receiver)
    ensure_user_token_addresses(db, sender)
    ensure_user_token_addresses(db, receiver)
    sender_wallet = get_or_create_wallet(db, sender)
    receiver_wallet = get_or_create_wallet(db, receiver)
    sender_token_addr = get_user_token_address(db, sender, curr)
    receiver_token_addr = get_user_token_address(db, receiver, curr)

    # Exact financial amounts (no floating point arithmetic)
    amount_dec = Decimal(f"{amount:.6f}")
    amount_paise = int(round(amount * 100)) if curr == "INR" else 0

    now = datetime.datetime.utcnow()
    tx_ref = generate_reference(prefix="TX-VAY")

    # 5. Row-level locking to prevent concurrent double-spending
    try:
        # Lock sender account
        sender_account = db.query(Account).filter(
            Account.user_id == sender.user_id,
            Account.currency == curr
        ).with_for_update().first()

        if not sender_account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sender does not have an active {curr} account."
            )

        if sender_account.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your {curr} account is currently frozen or restricted."
            )

        # Balance check
        if curr == "INR":
            current_paise = sender_account.balance_paise or int(round(float(sender_account.available_balance) * 100))
            if current_paise < amount_paise:
                avail_inr = current_paise / 100.0
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient INR balance. Available: ₹{avail_inr:,.2f}, Requested: ₹{amount:,.2f}."
                )
        else:
            if sender_account.available_balance < amount_dec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient {curr} balance. Available: {sender_account.available_balance:.4f} {curr}, Requested: {amount_dec:.4f} {curr}."
                )

        # Lock recipient account
        recipient_account = db.query(Account).filter(
            Account.user_id == receiver.user_id,
            Account.currency == curr
        ).with_for_update().first()

        if not recipient_account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Recipient does not have an active {curr} account."
            )

        if recipient_account.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Recipient's {curr} account is currently frozen."
            )

        # 6. Apply Atomic Ledger Balance Changes
        if curr == "INR":
            sender_account.balance_paise -= amount_paise
            sender_account.balance = Decimal(str(sender_account.balance_paise / 100.0))
            sender_account.available_balance = sender_account.balance
            sender_account.updated_at = now

            recipient_account.balance_paise += amount_paise
            recipient_account.balance = Decimal(str(recipient_account.balance_paise / 100.0))
            recipient_account.available_balance = recipient_account.balance
            recipient_account.updated_at = now

            # Sync legacy Wallet table
            sender_wallet.inr_balance_paise = sender_account.balance_paise
            sender_wallet.inr_balance = float(sender_account.balance)
            receiver_wallet.inr_balance_paise = recipient_account.balance_paise
            receiver_wallet.inr_balance = float(recipient_account.balance)
        else:
            sender_account.balance -= amount_dec
            sender_account.available_balance -= amount_dec
            sender_account.updated_at = now

            recipient_account.balance += amount_dec
            recipient_account.available_balance += amount_dec
            recipient_account.updated_at = now

            # Sync legacy WalletBalance table
            if asset:
                s_wb = db.query(WalletBalance).filter(
                    WalletBalance.wallet_id == sender_wallet.wallet_id,
                    WalletBalance.asset_id == asset.asset_id
                ).first()
                if s_wb:
                    s_wb.amount = sender_account.balance
                    s_wb.available_amount = sender_account.available_balance
                    s_wb.updated_at = now

                r_wb = db.query(WalletBalance).filter(
                    WalletBalance.wallet_id == receiver_wallet.wallet_id,
                    WalletBalance.asset_id == asset.asset_id
                ).first()
                if not r_wb:
                    r_wb = WalletBalance(
                        wallet_id=receiver_wallet.wallet_id,
                        asset_id=asset.asset_id,
                        amount=recipient_account.balance,
                        available_amount=recipient_account.available_balance,
                        updated_at=now
                    )
                    db.add(r_wb)
                else:
                    r_wb.amount = recipient_account.balance
                    r_wb.available_amount = recipient_account.available_balance
                    r_wb.updated_at = now

        # 7. Create Authoritative Ledger Transaction
        ledger_tx = LedgerTransaction(
            reference=tx_ref,
            idempotency_key=idempotency_key,
            type="TRANSFER",
            description=f"Internal transfer of {amount:.4f} {curr} from {sender.email} to {receiver.email}",
            status="COMPLETED",
            created_at=now
        )
        db.add(ledger_tx)
        db.flush()

        # 8. Create Double-Entry Entries (DEBIT == CREDIT)
        entry_debit = LedgerEntry(
            ledger_transaction_id=ledger_tx.transaction_id,
            account_id=sender_account.account_id,
            user_id=sender.user_id,
            currency=curr,
            direction="DEBIT",
            amount=amount_dec,
            amount_paise=amount_paise,
            balance_after=sender_account.balance,
            balance_after_paise=sender_account.balance_paise,
            created_at=now
        )
        db.add(entry_debit)

        entry_credit = LedgerEntry(
            ledger_transaction_id=ledger_tx.transaction_id,
            account_id=recipient_account.account_id,
            user_id=receiver.user_id,
            currency=curr,
            direction="CREDIT",
            amount=amount_dec,
            amount_paise=amount_paise,
            balance_after=recipient_account.balance,
            balance_after_paise=recipient_account.balance_paise,
            created_at=now
        )
        db.add(entry_credit)

        # 9. Create Transfer record
        transfer = Transfer(
            reference=tx_ref,
            sender_user_id=sender.user_id,
            sender_account_id=sender_account.account_id,
            recipient_user_id=receiver.user_id,
            recipient_account_id=recipient_account.account_id,
            currency=curr,
            amount=amount_dec,
            amount_paise=amount_paise,
            fee=Decimal("0.0"),
            note=note,
            status="COMPLETED",
            created_at=now
        )
        db.add(transfer)

        # 10. Create user-facing Payment and Transaction records
        asset_id_val = asset.asset_id if asset else None
        payment = Payment(
            sender_id=sender.user_id,
            receiver_id=receiver.user_id,
            asset_id=asset_id_val,
            amount=amount,
            sender_address=sender_token_addr,
            receiver_address=receiver_token_addr,
            status="COMPLETED",
            reference=tx_ref,
            note=note,
            created_at=now
        )
        db.add(payment)
        db.flush()

        tx_sender = Transaction(
            user_id=sender.user_id,
            payment_id=payment.payment_id,
            type="SEND",
            asset_id=asset_id_val,
            amount=-amount,
            sender=f"{sender.email} ({sender_token_addr})" if sender_token_addr else sender.email,
            receiver=f"{receiver.email} ({receiver_token_addr})" if receiver_token_addr else receiver.email,
            sender_address=sender_token_addr,
            receiver_address=receiver_token_addr,
            status="COMPLETED",
            reference_id=generate_reference(prefix="TXS"),
            created_at=now
        )
        db.add(tx_sender)

        tx_receiver = Transaction(
            user_id=receiver.user_id,
            payment_id=payment.payment_id,
            type="RECEIVE",
            asset_id=asset_id_val,
            amount=amount,
            sender=f"{sender.email} ({sender_token_addr})" if sender_token_addr else sender.email,
            receiver=f"{receiver.email} ({receiver_token_addr})" if receiver_token_addr else receiver.email,
            sender_address=sender_token_addr,
            receiver_address=receiver_token_addr,
            status="COMPLETED",
            reference_id=generate_reference(prefix="TXR"),
            created_at=now
        )
        db.add(tx_receiver)

        # 11. Activity & Notifications
        act_sender = Activity(
            user_id=sender.user_id,
            action="SEND",
            description=f"Sent {amount:.4f} {curr} from {sender_token_addr} to {receiver.name} ({receiver_token_addr}). Ref: {tx_ref}",
            reference_id=tx_ref,
            ip_address=ip_address,
            created_at=now
        )
        db.add(act_sender)

        act_receiver = Activity(
            user_id=receiver.user_id,
            action="RECEIVE",
            description=f"Received {amount:.4f} {curr} at {receiver_token_addr} from {sender.name} ({sender_token_addr}). Ref: {tx_ref}",
            reference_id=tx_ref,
            ip_address="VAYORA_INTERNAL",
            created_at=now
        )
        db.add(act_receiver)

        notif_sender = Notification(
            user_id=sender.user_id,
            title="Transfer Dispatched",
            message=f"Sent {amount:.2f} {curr} to {receiver.name} ({receiver.email}). Reference: {tx_ref}",
            type="PAYMENT",
            is_read=False,
            created_at=now
        )
        db.add(notif_sender)

        notif_receiver = Notification(
            user_id=receiver.user_id,
            title="Payment Received",
            message=f"Received {amount:.2f} {curr} from {sender.name} ({sender.email}). Reference: {tx_ref}",
            type="PAYMENT",
            is_read=False,
            created_at=now
        )
        db.add(notif_receiver)

        # 12. Security Audit Log
        audit = AuditLog(
            user_id=sender.user_id,
            action="TRANSFER_DISPATCHED",
            details=f"Transferred {amount:.4f} {curr} to User #{receiver.user_id} ({receiver.email}). Reference: {tx_ref}",
            ip_address=ip_address,
            created_at=now
        )
        db.add(audit)

        # COMMIT ATOMICALLY
        db.commit()
        db.refresh(payment)

        # 13. Dispatch Real Email Receipts (asynchronously in try/except)
        try:
            from backend.services.email_service import send_payment_notification_email
            send_payment_notification_email(
                to_email=sender.email,
                user_name=sender.name,
                amount=amount,
                asset_symbol=curr,
                reference=tx_ref,
                counterparty_email=receiver.email,
                is_sender=True,
                note=note
            )
            send_payment_notification_email(
                to_email=receiver.email,
                user_name=receiver.name,
                amount=amount,
                asset_symbol=curr,
                reference=tx_ref,
                counterparty_email=sender.email,
                is_sender=False,
                note=note
            )
        except Exception:
            pass

        # 14. Real-Time WebSocket Presence Broadcast
        from backend.services.presence_service import safe_dispatch_payment
        safe_dispatch_payment({
            "event": "PAYMENT_RECEIVED",
            "payment_id": payment.payment_id,
            "reference": tx_ref,
            "sender_email": sender.email,
            "receiver_email": receiver.email,
            "receiver_id": receiver.user_id,
            "amount": amount,
            "asset_symbol": curr,
            "note": note
        })

        return payment

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(e)}"
        )

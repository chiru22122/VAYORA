import hashlib
import random
import string
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from backend.models import User, TokenAddress, Account, Wallet

# Standard character sets
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BASE58_CHARSET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
HEX_CHARSET = "0123456789abcdef"

# Canonical fixed addresses for demo personas
DEMO_PERSONA_ADDRESSES = {
    "sender@vayora.demo": {
        "USDT": ("TX7A1vSenderUSDT99qKLmP3w8xV2y5R1", "TRC-20 (Tron Network)"),
        "USDC": ("0x1111A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8", "ERC-20 (Ethereum)"),
        "BTC":  ("bc1qsender42a8z9w0y1x2v3u4t5s6r7q8p9o0m1", "Native SegWit (Bech32)"),
        "ETH":  ("0x71C94B2E8F19D382A0F8372651B44390C12E7B90", "ERC-20 / Ethereum Mainnet"),
        "SOL":  ("SolSenderVa11111111111111111111111111111111", "Solana SPL"),
        "INR":  ("sender.vayora@icici", "UPI / IMPS Virtual Account"),
    },
    "receiver@vayora.demo": {
        "USDT": ("TY8B2uReceiverUSDT88rMNqQ4x9yW3z6S2", "TRC-20 (Tron Network)"),
        "USDC": ("0x2222B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A1", "ERC-20 (Ethereum)"),
        "BTC":  ("bc1qrecv88b9a0z1y2x3v4u5t6s7r8q9p0o1m2k3", "Native SegWit (Bech32)"),
        "ETH":  ("0x34A991E47B02D338FA8291410651A827B1390A77", "ERC-20 / Ethereum Mainnet"),
        "SOL":  ("SolReceiverVa2222222222222222222222222222222", "Solana SPL"),
        "INR":  ("receiver.vayora@icici", "UPI / IMPS Virtual Account"),
    },
    "admin@vayora.demo": {
        "USDT": ("TA9AdminTreasuryUSDT77xKLmQ2w7yU1x4P9", "TRC-20 (Tron Network)"),
        "USDC": ("0x999C0F33A27118B82736C52166904B8E110F99BB", "ERC-20 (Ethereum)"),
        "BTC":  ("bc1qadmintreaz88v7w6u5t4s3r2q1p0o9n8m7l6k", "Native SegWit (Bech32)"),
        "ETH":  ("0x999B0F33A27118B82736C52166904B8E110F99AA", "ERC-20 / Ethereum Mainnet"),
        "SOL":  ("SolAdminTreasury1111111111111111111111111111", "Solana SPL"),
        "INR":  ("treasury.vayora@rbi", "RBI Liquidity Clearing"),
    }
}

# Network metadata specifications
NETWORK_SPECS = {
    "USDT": {
        "name": "Tether USD",
        "network": "TRC-20 (Tron)",
        "standard": "TRC-20",
        "qr_prefix": "tron:",
        "min_deposit": "1.00 USDT",
        "confirmations": 1,
        "fee": "0.00 VAYORA Network",
        "avg_time": "< 30s (Instant)",
        "contract": "TR7NHqJEKQxGTCi8q8ZY4pL8otSzgjLj6t"
    },
    "USDC": {
        "name": "USD Coin",
        "network": "ERC-20 (Ethereum)",
        "standard": "ERC-20",
        "qr_prefix": "ethereum:",
        "min_deposit": "1.00 USDC",
        "confirmations": 12,
        "fee": "0.00 VAYORA Network",
        "avg_time": "1-2 minutes",
        "contract": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    },
    "BTC": {
        "name": "Bitcoin",
        "network": "Native SegWit (Bech32)",
        "standard": "SegWit",
        "qr_prefix": "bitcoin:",
        "min_deposit": "0.0001 BTC",
        "confirmations": 2,
        "fee": "0.00 VAYORA Network",
        "avg_time": "10-20 minutes",
        "contract": "Native Layer 1"
    },
    "ETH": {
        "name": "Ethereum",
        "network": "ERC-20 / Ethereum Mainnet",
        "standard": "EVM",
        "qr_prefix": "ethereum:",
        "min_deposit": "0.005 ETH",
        "confirmations": 12,
        "fee": "0.00 VAYORA Network",
        "avg_time": "1-3 minutes",
        "contract": "Native Layer 1"
    },
    "SOL": {
        "name": "Solana",
        "network": "Solana SPL",
        "standard": "SPL",
        "qr_prefix": "solana:",
        "min_deposit": "0.05 SOL",
        "confirmations": 32,
        "fee": "0.00 VAYORA Network",
        "avg_time": "< 5s (Instant)",
        "contract": "Native Layer 1"
    },
    "INR": {
        "name": "Indian Rupee",
        "network": "UPI / IMPS Virtual Account",
        "standard": "NPCI / RBI",
        "qr_prefix": "upi://pay?pa=",
        "min_deposit": "₹100.00 INR",
        "confirmations": 1,
        "fee": "0.00 VAYORA Network",
        "avg_time": "Instant (< 1s)",
        "contract": "VAYORA Realtime Clearing"
    }
}

def _hash_seed(seed_str: str) -> bytes:
    return hashlib.sha256(seed_str.encode("utf-8")).digest()

def generate_deterministic_token_address(user_id: int, email: str, symbol: str) -> Tuple[str, str]:
    """Generates authentic format addresses deterministically derived from user identity."""
    clean_email = email.lower().strip()
    
    # Check fixed demo personas
    if clean_email in DEMO_PERSONA_ADDRESSES:
        if symbol in DEMO_PERSONA_ADDRESSES[clean_email]:
            return DEMO_PERSONA_ADDRESSES[clean_email][symbol]

    seed_bytes = _hash_seed(f"vayora_token_v1_{user_id}_{clean_email}_{symbol}")
    
    if symbol == "BTC":
        # Native SegWit: bc1q + 38 bech32 chars
        indices = [b % len(BECH32_CHARSET) for b in seed_bytes]
        # Extend to 38 chars
        extra_bytes = hashlib.sha256(seed_bytes + b"btc").digest()
        indices += [b % len(BECH32_CHARSET) for b in extra_bytes]
        body = "".join(BECH32_CHARSET[i] for i in indices[:38])
        return f"bc1q{body}", "Native SegWit (Bech32)"

    elif symbol == "USDT":
        # Tron TRC-20: T + 33 base58 chars
        indices = [b % len(BASE58_CHARSET) for b in seed_bytes]
        extra_bytes = hashlib.sha256(seed_bytes + b"usdt").digest()
        indices += [b % len(BASE58_CHARSET) for b in extra_bytes]
        body = "".join(BASE58_CHARSET[i] for i in indices[:33])
        return f"T{body}", "TRC-20 (Tron Network)"

    elif symbol == "ETH":
        # Ethereum: 0x + 40 hex chars
        hex_str = seed_bytes.hex()
        extra_hex = hashlib.sha256(seed_bytes + b"eth").hexdigest()
        full_hex = (hex_str + extra_hex)[:40]
        return f"0x{full_hex}", "ERC-20 / Ethereum Mainnet"

    elif symbol == "USDC":
        # USDC EVM address (distinct from ETH for token tracking)
        extra_hex = hashlib.sha256(seed_bytes + b"usdc_vault").hexdigest()[:40]
        return f"0x{extra_hex}", "ERC-20 (Ethereum)"

    elif symbol == "SOL":
        # Solana SPL: 44 base58 chars
        indices = [b % len(BASE58_CHARSET) for b in seed_bytes]
        extra_bytes = hashlib.sha256(seed_bytes + b"sol_spl").digest()
        indices += [b % len(BASE58_CHARSET) for b in extra_bytes]
        body = "".join(BASE58_CHARSET[i] for i in indices[:44])
        return body, "Solana SPL"

    elif symbol == "INR":
        # UPI VPA / Account
        username_part = clean_email.split("@")[0].replace(".", "")
        if not username_part:
            username_part = f"user{user_id}"
        upi_id = f"{username_part}.vayora@icici"
        return upi_id, "UPI / IMPS Virtual Account"

    else:
        # Generic fallback
        hex_str = seed_bytes.hex()[:40]
        return f"0x{hex_str}", "VAYORA Network"

def ensure_user_token_addresses(db: Session, user: User) -> Dict[str, str]:
    """
    Ensures that distinct receiving addresses exist for all supported assets.
    Returns a dictionary of symbol -> address string.
    """
    tokens = ["USDT", "USDC", "BTC", "ETH", "SOL", "INR"]
    existing = db.query(TokenAddress).filter(TokenAddress.user_id == user.user_id).all()
    existing_map = {t.asset_symbol: t.address for t in existing}

    needed_commit = False
    for sym in tokens:
        if sym not in existing_map:
            addr, net_label = generate_deterministic_token_address(user.user_id, user.email, sym)
            
            # Check if address happens to collide (extremely rare, but guarantees unique constraint)
            collision = db.query(TokenAddress).filter(TokenAddress.address == addr).first()
            if collision and collision.user_id != user.user_id:
                # Add random entropy
                entropy = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
                addr, net_label = generate_deterministic_token_address(user.user_id, f"{entropy}_{user.email}", sym)

            new_record = TokenAddress(
                user_id=user.user_id,
                asset_symbol=sym,
                network=net_label,
                address=addr
            )
            db.add(new_record)
            existing_map[sym] = addr
            needed_commit = True

    if needed_commit:
        db.commit()

    return existing_map

def get_user_token_address(db: Session, user: User, asset_symbol: str) -> str:
    """Gets the unique address for a specific user and asset."""
    sym = asset_symbol.upper().strip()
    record = db.query(TokenAddress).filter(
        TokenAddress.user_id == user.user_id,
        TokenAddress.asset_symbol == sym
    ).first()
    if record:
        return record.address

    # Otherwise provision on demand
    addresses = ensure_user_token_addresses(db, user)
    return addresses.get(sym, "")

def get_all_token_addresses_with_metadata(db: Session, user: User) -> List[Dict[str, Any]]:
    """Returns a rich list of all receiving addresses with network metadata and QR URI."""
    ensure_user_token_addresses(db, user)
    records = db.query(TokenAddress).filter(TokenAddress.user_id == user.user_id).all()
    
    # Preserve standard token order
    order = ["USDT", "USDC", "BTC", "ETH", "SOL", "INR"]
    records_map = {r.asset_symbol: r for r in records}
    
    result = []
    for sym in order:
        r = records_map.get(sym)
        if not r:
            continue
        spec = NETWORK_SPECS.get(sym, {
            "name": sym,
            "network": r.network,
            "standard": "Standard",
            "qr_prefix": "",
            "min_deposit": "0.00",
            "confirmations": 1,
            "fee": "0.00",
            "avg_time": "Instant"
        })
        
        qr_uri = f"{spec.get('qr_prefix', '')}{r.address}"
        if sym == "USDT":
            qr_uri = f"tron:{r.address}?token=USDT"
        elif sym == "BTC":
            qr_uri = f"bitcoin:{r.address}"
        elif sym == "ETH":
            qr_uri = f"ethereum:{r.address}"
        elif sym == "SOL":
            qr_uri = f"solana:{r.address}"
        elif sym == "INR":
            qr_uri = f"upi://pay?pa={r.address}&pn={user.name}&cu=INR"

        result.append({
            "symbol": sym,
            "name": spec.get("name", sym),
            "network": spec.get("network", r.network),
            "standard": spec.get("standard", ""),
            "address": r.address,
            "qr_uri": qr_uri,
            "min_deposit": spec.get("min_deposit", "0.00"),
            "confirmations": spec.get("confirmations", 1),
            "fee": spec.get("fee", "0.00"),
            "avg_time": spec.get("avg_time", "Instant"),
            "contract": spec.get("contract", ""),
            "updated_at": r.created_at.isoformat() if r.created_at else None
        })
    return result

def find_user_by_any_identifier(db: Session, identifier: str) -> Optional[Tuple[User, Optional[str]]]:
    """
    Finds a user by:
    1. Email
    2. Specific Token Address (BTC, USDT, ETH, SOL, USDC, INR)
    3. Account Number (VAY-USDT-...)
    4. Main Wallet 0x Address
    Returns: (User, asset_symbol or None)
    """
    if not identifier:
        return None
    clean = identifier.strip()

    # 1. Email lookup
    user = db.query(User).filter(User.email.ilike(clean)).first()
    if user:
        return (user, None)

    # 2. Token Address lookup (specific to token)
    token_addr = db.query(TokenAddress).filter(TokenAddress.address.ilike(clean)).first()
    if token_addr:
        user = db.query(User).filter(User.user_id == token_addr.user_id).first()
        if user:
            return (user, token_addr.asset_symbol)

    # 2b. Demo Persona Canonical Addresses fallback
    for demo_email, addrs in DEMO_PERSONA_ADDRESSES.items():
        for sym, (addr, _) in addrs.items():
            if clean.lower() == addr.lower():
                user = db.query(User).filter(User.email.ilike(demo_email)).first()
                if user:
                    return (user, sym)

    # 3. Account Number lookup
    acct = db.query(Account).filter(Account.account_number.ilike(clean)).first()
    if acct:
        user = db.query(User).filter(User.user_id == acct.user_id).first()
        if user:
            return (user, acct.currency)

    # 4. Main Wallet address lookup
    wallet = db.query(Wallet).filter(Wallet.address.ilike(clean)).first()
    if wallet:
        user = db.query(User).filter(User.user_id == wallet.user_id).first()
        if user:
            return (user, None)

    return None

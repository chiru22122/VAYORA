import os
import random
import string
import uuid
import datetime
from typing import Optional, Dict, Any
import jwt
import bcrypt
import backend.config

SECRET_KEY = os.getenv("SECRET_KEY", "vayora_super_secret_fintech_jwt_signing_key_2026_demo_secure!")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Create signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.datetime.utcnow()})
    if "jti" not in to_encode:
        to_encode["jti"] = str(uuid.uuid4())
        
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def generate_otp(length: int = 6) -> str:
    """Generate numeric OTP."""
    return "".join(random.choices(string.digits, k=length))

def generate_reference(prefix: str = "TX") -> str:
    """Generate human-readable unique reference."""
    part1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part3 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{part1}-{part2}-{part3}"

def generate_wallet_address(symbol: str = "VYR") -> str:
    """Generate demo crypto wallet address."""
    hex_part = "".join(random.choices("0123456789abcdef", k=40))
    return f"0x{hex_part}"

def generate_virtual_card_number() -> str:
    """Generate 16-digit card number formatted."""
    prefix = "4532"  # Demo Visa BIN
    nums = [prefix]
    for _ in range(3):
        nums.append("".join(random.choices(string.digits, k=4)))
    return " ".join(nums)

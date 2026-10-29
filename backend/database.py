import os
import re
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import backend.config

def normalize_database_url(url: str) -> str:
    """
    Normalizes PostgreSQL connection strings:
    - Replaces postgresql:// or postgres:// with postgresql+psycopg:// (for psycopg v3)
    - Strips documentation brackets around passwords: [PASSWORD] -> PASSWORD
    - URL-encodes special characters in passwords (e.g., @ -> %40)
    """
    if not url:
        return "sqlite:///./database/vayora.db"
    
    url = url.strip()
    
    # 1. Standardize scheme for SQLAlchemy + psycopg 3
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
        
    # 2. Extract and sanitize credentials
    if "://" in url and "@" in url:
        scheme_part, rest = url.split("://", 1)
        last_at_index = rest.rfind("@")
        creds_part = rest[:last_at_index]
        host_part = rest[last_at_index + 1:]
        
        if ":" in creds_part:
            user_part, pwd_part = creds_part.split(":", 1)
            # Remove brackets if user entered [PASSWORD]
            if pwd_part.startswith("[") and pwd_part.endswith("]"):
                pwd_part = pwd_part[1:-1]
            # URL-encode if unencoded @ present
            if "@" in pwd_part and "%40" not in pwd_part:
                pwd_part = urllib.parse.quote(pwd_part, safe="")
            url = f"{scheme_part}://{user_part}:{pwd_part}@{host_part}"
            
    return url

RAW_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database/vayora.db")
DATABASE_URL = normalize_database_url(RAW_DATABASE_URL)

connect_args = {}
# For SQLite, ensure directory exists
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    connect_args = {"check_same_thread": False}
    engine_kwargs = {"connect_args": connect_args}
else:
    # PostgreSQL engine with timeout, disabled prepared statements for pooler compatibility, and health pre-pinging
    is_serverless = os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV"))
    engine_kwargs = {
        "connect_args": {
            "connect_timeout": 10,
            "prepare_threshold": None,
        },
        "pool_pre_ping": True,
        "pool_size": 5 if is_serverless else 10,
        "max_overflow": 5 if is_serverless else 20,
        "pool_recycle": 300 if is_serverless else 1800,
    }

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_masked_db_url() -> str:
    """Returns DATABASE_URL with credentials safely masked for logging."""
    if "@" in DATABASE_URL:
        proto_and_creds, host_and_db = DATABASE_URL.split("@", 1)
        proto = proto_and_creds.split("://")[0]
        return f"{proto}://*****:*****@{host_and_db}"
    return DATABASE_URL

def test_db_connection() -> bool:
    """Tests the database connection without exposing secrets."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        # Avoid printing password if exception string contains the URL
        sanitized_err = str(e)
        if "@" in sanitized_err:
            sanitized_err = sanitized_err.split("@")[-1]
        print(f"[DB Connection Warning] Database connectivity issue: {sanitized_err}")
        return False

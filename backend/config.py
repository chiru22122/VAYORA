"""
VAYORA Backend Configuration & Environment Loader
Loads backend-specific environment settings from backend/.env (with fallback to root .env).
"""

import os
from dotenv import load_dotenv

# Path resolution
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)

BACKEND_ENV = os.path.join(BACKEND_DIR, ".env")
ROOT_ENV = os.path.join(ROOT_DIR, ".env")

# Priority: backend/.env -> root .env
if os.path.exists(BACKEND_ENV):
    load_dotenv(BACKEND_ENV, override=True)
elif os.path.exists(ROOT_ENV):
    load_dotenv(ROOT_ENV, override=True)
else:
    load_dotenv(override=True)

# Service URLs
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")

def get_cors_origins():
    """Generates allowed CORS origins including FRONTEND_URL, BACKEND_URL, and dev ports."""
    origins = [
        FRONTEND_URL,
        BACKEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # Filter empty and remove duplicates preserving order
    return list(dict.fromkeys([o for o in origins if o]))

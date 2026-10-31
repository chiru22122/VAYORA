"""
VAYORA Backend Configuration & Environment Loader
Loads environment settings from hosting platform (Render/production) or local .env fallback.
"""

import os
from dotenv import load_dotenv

# Path resolution
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)

BACKEND_ENV = os.path.join(BACKEND_DIR, ".env")
ROOT_ENV = os.path.join(ROOT_DIR, ".env")

# In production hosting (Render, Railway, Fly.io), environment variables are injected directly.
# load_dotenv with override=False ensures hosting platform environment variables always take precedence.
if os.path.exists(BACKEND_ENV):
    load_dotenv(BACKEND_ENV, override=False)
if os.path.exists(ROOT_ENV):
    load_dotenv(ROOT_ENV, override=False)

# Service URLs
_DEFAULT_BACKEND = f"https://{os.getenv('VERCEL_URL')}" if os.getenv("VERCEL_URL") else "http://127.0.0.1:8000"
BACKEND_URL = os.getenv("BACKEND_URL", _DEFAULT_BACKEND).rstrip("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")

# Environment mode
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

def get_cors_origins():
    """
    Generates allowed CORS origins:
    - In development: includes standard localhost and 127.0.0.1 development ports.
    - In production: strictly uses explicit FRONTEND_URL origins (comma-separated list supported)
      and BACKEND_URL.
    """
    origins = []

    # Preserve localhost for local development
    if ENVIRONMENT != "production":
        origins.extend([
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "null",
        ])

    if BACKEND_URL:
        origins.append(BACKEND_URL)

    # Support explicit production frontend origins (supports multiple comma-separated URLs)
    if FRONTEND_URL:
        for u in FRONTEND_URL.split(","):
            cleaned = u.strip().rstrip("/")
            if cleaned:
                origins.append(cleaned)

    # Auto-allow Vercel system-injected deployment URL
    vercel_url = os.getenv("VERCEL_URL")
    if vercel_url:
        origins.append(f"https://{vercel_url.strip().rstrip('/')}")

    # Filter empty and remove duplicates preserving order
    return list(dict.fromkeys([o for o in origins if o]))

def get_cors_origin_regex():
    """
    Returns an allowed CORS origin regex based on environment and Vercel hosting:
    - Custom regex: If ALLOWED_ORIGIN_REGEX is explicitly set in env, use that.
    - Development (non-Vercel): Matches any localhost or 127.0.0.1 port.
    - Production / Vercel: Scopes to all VAYORA Vercel frontend deployments and previews.
    """
    custom_regex = os.getenv("ALLOWED_ORIGIN_REGEX")
    if custom_regex:
        return custom_regex

    if ENVIRONMENT != "production" and not os.getenv("VERCEL"):
        return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # Allow all VAYORA Vercel frontend deployments, production and preview URLs
    return r"^https://vayora[a-z0-9\-]*\.vercel\.app$"

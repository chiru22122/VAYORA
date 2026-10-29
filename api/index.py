"""
VAYORA Serverless ASGI Entrypoint for Vercel
Loads and exposes the FastAPI 'app' instance for Vercel Serverless Functions.
"""

import sys
import os

# Add project root directory to sys.path so 'backend' package and modules resolve cleanly
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.main import app

# Vercel Serverless looks for 'app'
__all__ = ["app"]

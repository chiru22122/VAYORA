"""
VAYORA Serverless ASGI Entrypoint for Vercel
Loads and exposes the FastAPI 'app' instance for Vercel Serverless Functions.
"""

import sys
import os

# Ensure the root directory and backend directory are in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_current_dir)

for _path in [_root_dir, _current_dir, "/var/task", os.getcwd()]:
    if _path and _path not in sys.path:
        sys.path.insert(0, _path)

# Direct import from backend.main
from backend.main import app

# Explicit top-level assignment for Vercel AST framework detection
app = app

__all__ = ["app"]


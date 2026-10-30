"""
VAYORA Serverless ASGI Entrypoint for Vercel
Loads and exposes the FastAPI 'app' instance for Vercel Serverless Functions.
"""

import sys
import os

# Ensure the directory containing the 'backend' package is in sys.path.
# In Vercel serverless environments (/var/task), the handler may execute as
# /var/task/api/index.py or /var/task/index.py. Checking cwd and candidate paths
# guarantees 'backend' is discoverable in all serverless packaging layouts.
_candidates = [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__)),
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
]

for _dir in _candidates:
    if _dir and os.path.isdir(os.path.join(_dir, "backend")):
        if _dir not in sys.path:
            sys.path.insert(0, _dir)
        break
else:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from backend.main import app

# Vercel Serverless looks for 'app'
__all__ = ["app"]

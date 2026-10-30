import sys
import os

# Ensure repository root is on sys.path if this module is loaded directly
_CANDIDATE_ROOTS = [
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    os.getcwd(),
]
for _c in _CANDIDATE_ROOTS:
    if _c and os.path.isdir(os.path.join(_c, "backend")):
        if _c not in sys.path:
            sys.path.insert(0, _c)
        break

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.database import engine, Base
from backend.routes import (
    auth, user, wallet, payments, transactions, swap,
    conversion, bank, card, nfc, security, admin, real_payments,
    earn, subscriptions
)
from backend.services.presence_service import (
    register_ws, unregister_ws, get_online_count, get_online_users_list
)

from backend.config import get_cors_origins, get_cors_origin_regex, BACKEND_URL, FRONTEND_URL

# Initialize database schema
try:
    Base.metadata.create_all(bind=engine)
except Exception as _db_init_err:
    _err_str = str(_db_init_err)
    if "@" in _err_str:
        _err_str = _err_str.split("@")[-1]
    print(f"[Database Notice] Database connection info: {_err_str}")

app = FastAPI(
    title="VAYORA - Your Digital Value, One Journey",
    description="Unified Digital Asset and Payment Management Platform (Fintech Prototype)",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS dynamically using backend.config
_cors_kwargs = {
    "allow_origins": get_cors_origins(),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
_origin_regex = get_cors_origin_regex()
if _origin_regex:
    _cors_kwargs["allow_origin_regex"] = _origin_regex

app.add_middleware(CORSMiddleware, **_cors_kwargs)

# Include API Routers
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(wallet.router)
app.include_router(earn.router)
app.include_router(subscriptions.router)
app.include_router(payments.router)
app.include_router(real_payments.router)
app.include_router(transactions.router)
app.include_router(swap.router)
app.include_router(conversion.router)
app.include_router(bank.router)
app.include_router(card.router)
app.include_router(nfc.router)
app.include_router(security.router)
app.include_router(admin.router)

@app.websocket("/api/ws/presence")
async def websocket_presence(websocket: WebSocket):
    await websocket.accept()
    register_ws(websocket)
    try:
        # Send immediate online users snapshot
        await websocket.send_json({
            "type": "PRESENCE_UPDATE",
            "online_count": get_online_count(),
            "online_users": get_online_users_list()
        })
        while True:
            data = await websocket.receive_text()
            if "ping" in data.lower():
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        unregister_ws(websocket)
    except Exception:
        unregister_ws(websocket)

@app.get("/api/health", tags=["System"])
@app.get("/health", tags=["System"], include_in_schema=False)
def health_check():
    return {
        "status": "healthy",
        "system": "VAYORA Core Engine",
        "version": "1.0.0",
        "real_time_users_online": get_online_count(),
        "backend_url": BACKEND_URL,
        "frontend_url": FRONTEND_URL,
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.get("/api/config", tags=["System"])
def get_public_config():
    return {
        "backend_url": BACKEND_URL,
        "frontend_url": FRONTEND_URL,
        "environment": os.getenv("ENVIRONMENT", "development")
    }

from fastapi.responses import FileResponse, RedirectResponse

@app.get("/api", tags=["System"])
def api_root_service_info():
    """Service status and API documentation entry point for /api."""
    return {
        "system": "VAYORA Core Engine API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/health"
    }

@app.get("/docs", include_in_schema=False)
def redirect_docs():
    return RedirectResponse(url="/api/docs")

@app.get("/app")
async def redirect_app_root():
    return RedirectResponse(url="/dashboard.html")

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

@app.get("/", include_in_schema=False)
def serve_root():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "system": "VAYORA Core Engine API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/health"
    }

# Mount classic static frontend for assets and HTML pages
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)

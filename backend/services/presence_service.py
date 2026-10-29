import asyncio
import datetime
from typing import Dict, Any, List, Set
from fastapi import WebSocket

# In-memory presence store
# user_id -> user metadata dict
_online_users: Dict[int, Dict[str, Any]] = {}
_active_websockets: Set[WebSocket] = set()

# Cleanup threshold in seconds
INACTIVE_TIMEOUT_SECONDS = 60

def _clean_stale_users():
    now = datetime.datetime.utcnow()
    stale_ids = []
    for uid, data in _online_users.items():
        diff = (now - data["last_seen"]).total_seconds()
        if diff > INACTIVE_TIMEOUT_SECONDS:
            stale_ids.append(uid)
    for uid in stale_ids:
        _online_users.pop(uid, None)

def update_user_presence(
    user_id: int,
    name: str,
    email: str,
    role: str = "user",
    avatar_color: str = "#00f59b",
    current_page: str = "dashboard",
    ip_address: str = "127.0.0.1",
    device: str = "Web"
) -> Dict[str, Any]:
    """Records or refreshes an active user heartbeat."""
    _clean_stale_users()
    now = datetime.datetime.utcnow()

    entry = _online_users.get(user_id)
    if not entry:
        entry = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "role": role,
            "avatar_color": avatar_color,
            "current_page": current_page,
            "ip_address": ip_address,
            "device": device,
            "connected_at": now.isoformat(),
            "last_seen": now
        }
    else:
        entry["last_seen"] = now
        entry["current_page"] = current_page
        entry["device"] = device
        entry["ip_address"] = ip_address

    _online_users[user_id] = entry
    return entry

def remove_user_presence(user_id: int):
    """Explicitly marks a user as offline upon logout."""
    _online_users.pop(user_id, None)

def get_online_users_list() -> List[Dict[str, Any]]:
    """Returns list of currently online users formatted for frontend display."""
    _clean_stale_users()
    result = []
    now = datetime.datetime.utcnow()
    for u in _online_users.values():
        diff = (now - u["last_seen"]).total_seconds()
        status = "ONLINE" if diff < 20 else "IDLE"
        result.append({
            "user_id": u["user_id"],
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "avatar_color": u["avatar_color"],
            "current_page": u["current_page"],
            "ip_address": u["ip_address"],
            "device": u["device"],
            "status": status,
            "last_active_seconds_ago": int(diff),
            "connected_at": u["connected_at"]
        })
    return sorted(result, key=lambda x: x["last_active_seconds_ago"])

def get_online_count() -> int:
    _clean_stale_users()
    return len(_online_users)

def register_ws(ws: WebSocket):
    _active_websockets.add(ws)

def unregister_ws(ws: WebSocket):
    _active_websockets.discard(ws)

async def broadcast_ws(payload: Dict[str, Any]):
    """Broadcasts a JSON message to all active WebSocket clients."""
    if not _active_websockets:
        return
    disconnected = set()
    for ws in list(_active_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        _active_websockets.discard(ws)

async def broadcast_presence():
    """Broadcasts current presence snapshot to all connected clients."""
    users = get_online_users_list()
    await broadcast_ws({
        "type": "PRESENCE_UPDATE",
        "online_count": len(users),
        "online_users": users,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

async def broadcast_payment_event(event_data: Dict[str, Any]):
    """Broadcasts instant payment alert to connected users."""
    await broadcast_ws({
        "type": "PAYMENT_EVENT",
        "data": event_data,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

def safe_dispatch_presence():
    """Safely schedules presence broadcast across async/sync execution contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broadcast_presence())
    except Exception:
        pass

def safe_dispatch_payment(event_data: Dict[str, Any]):
    """Safely schedules payment broadcast across async/sync execution contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broadcast_payment_event(event_data))
    except Exception:
        pass


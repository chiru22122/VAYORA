from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Activity, Notification
from backend.schemas import (
    UserResponse, ProfileUpdateRequest, ActivityResponse, NotificationResponse
)
from backend.dependencies import get_current_user

router = APIRouter(prefix="/api/user", tags=["User Profile & System"])

@router.get("", response_model=UserResponse)
def get_user_profile(current_user: User = Depends(get_current_user)):
    return UserResponse.from_orm(current_user)

@router.put("/profile", response_model=UserResponse)
def update_profile(
    req: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.name:
        current_user.name = req.name.strip()
    if req.phone is not None:
        current_user.phone = req.phone.strip()
        
    db.commit()
    db.refresh(current_user)
    return UserResponse.from_orm(current_user)

@router.get("/activity", response_model=List[ActivityResponse])
def get_user_activity(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    acts = db.query(Activity).filter(
        Activity.user_id == current_user.user_id
    ).order_by(Activity.created_at.desc()).limit(limit).all()
    return [ActivityResponse.from_orm(a) for a in acts]

@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notifs = db.query(Notification).filter(
        Notification.user_id == current_user.user_id
    ).order_by(Notification.created_at.desc()).limit(limit).all()
    return [NotificationResponse.from_orm(n) for n in notifs]

@router.post("/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    n = db.query(Notification).filter(
        Notification.notification_id == notif_id,
        Notification.user_id == current_user.user_id
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    n.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}

@router.post("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}

@router.post("/heartbeat")
def user_heartbeat(
    request: Request,
    page: str = "dashboard",
    device: str = "Web",
    current_user: User = Depends(get_current_user)
):
    """Pings backend to keep user alive in the Real-Time Active Users list."""
    from backend.services.presence_service import update_user_presence, get_online_count, get_online_users_list
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "127.0.0.1")
    
    update_user_presence(
        user_id=current_user.user_id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        avatar_color=current_user.avatar_color or "#00f59b",
        current_page=page,
        ip_address=ip,
        device=device
    )
    
    return {
        "status": "active",
        "online_count": get_online_count(),
        "online_users": get_online_users_list()
    }

@router.get("/presence/online")
def get_live_presence():
    """Returns list and count of all currently active users across the platform."""
    from backend.services.presence_service import get_online_count, get_online_users_list
    return {
        "online_count": get_online_count(),
        "online_users": get_online_users_list()
    }

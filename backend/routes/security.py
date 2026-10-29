from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Session as UserSession, LoginHistory, RecoveryCode, Activity
from backend.schemas import (
    SecurityOverviewResponse, SessionResponse, LoginHistoryResponse,
    PasswordChangeRequest
)
from backend.dependencies import get_current_user
from backend.auth import hash_password, verify_password
from backend.services.security_service import (
    calculate_security_score, revoke_all_sessions, generate_user_recovery_codes
)

router = APIRouter(prefix="/api/security", tags=["Security Center"])

@router.get("", response_model=SecurityOverviewResponse)
def get_security_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    score = calculate_security_score(current_user, db)
    sessions_count = db.query(UserSession).filter(
        UserSession.user_id == current_user.user_id,
        UserSession.status == "ACTIVE"
    ).count()
    
    recent_logins = db.query(LoginHistory).filter(
        LoginHistory.user_id == current_user.user_id
    ).order_by(LoginHistory.created_at.desc()).limit(10).all()
    
    recovery_count = db.query(RecoveryCode).filter(
        RecoveryCode.user_id == current_user.user_id,
        RecoveryCode.used == False
    ).count()
    
    return SecurityOverviewResponse(
        email_verified=current_user.email_verified,
        security_score=score,
        active_sessions_count=sessions_count,
        recent_logins=[LoginHistoryResponse.from_orm(l) for l in recent_logins],
        recovery_codes_count=recovery_count
    )

@router.get("/sessions", response_model=List[SessionResponse])
def get_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.user_id,
        UserSession.status == "ACTIVE"
    ).order_by(UserSession.last_active.desc()).all()
    return [SessionResponse.from_orm(s) for s in sessions]

@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sess = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.user_id == current_user.user_id
    ).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    sess.status = "REVOKED"
    db.commit()
    return {"message": "Session successfully terminated"}

@router.get("/login-history", response_model=List[LoginHistoryResponse])
def get_login_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    history = db.query(LoginHistory).filter(
        LoginHistory.user_id == current_user.user_id
    ).order_by(LoginHistory.created_at.desc()).limit(50).all()
    return [LoginHistoryResponse.from_orm(h) for h in history]

@router.post("/logout-all")
def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    revoked = revoke_all_sessions(db, current_user)
    return {"message": f"Successfully revoked {revoked} active device sessions"}

@router.post("/change-password")
def change_password(
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
        
    current_user.password_hash = hash_password(req.new_password)
    act = Activity(
        user_id=current_user.user_id,
        action="SECURITY",
        description="Password updated by user",
        ip_address="127.0.0.1"
    )
    db.add(act)
    db.commit()
    return {"message": "Password changed successfully"}

@router.post("/recovery-codes")
def generate_recovery_codes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    codes = generate_user_recovery_codes(db, current_user, count=8)
    return {
        "message": "Generated new backup recovery codes. Store them in a secure place.",
        "codes": codes
    }

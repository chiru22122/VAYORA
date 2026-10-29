import datetime
import random
import string
from sqlalchemy.orm import Session
from backend.models import User, Session as UserSession, LoginHistory, RecoveryCode, Activity
from backend.auth import hash_password, verify_password

def record_login_attempt(
    db: Session,
    user_id: int,
    device: str,
    ip_address: str,
    success: bool,
    reason: str = "Success"
):
    if not user_id or user_id <= 0:
        return None
    try:
        history = LoginHistory(
            user_id=user_id,
            device=device,
            ip_address=ip_address,
            success=success,
            reason=reason,
            created_at=datetime.datetime.utcnow()
        )
        db.add(history)
        db.commit()
        return history
    except Exception:
        db.rollback()
        return None

def register_session(
    db: Session,
    user: User,
    token_id: str,
    device: str,
    ip_address: str
) -> UserSession:
    sess = UserSession(
        user_id=user.user_id,
        token_id=token_id,
        device=device,
        ip_address=ip_address,
        status="ACTIVE",
        last_active=datetime.datetime.utcnow(),
        created_at=datetime.datetime.utcnow()
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess

def revoke_all_sessions(db: Session, user: User, current_token_id: str = None) -> int:
    query = db.query(UserSession).filter(
        UserSession.user_id == user.user_id,
        UserSession.status == "ACTIVE"
    )
    if current_token_id:
        query = query.filter(UserSession.token_id != current_token_id)
        
    count = 0
    for s in query.all():
        s.status = "REVOKED"
        count += 1
        
    act = Activity(
        user_id=user.user_id,
        action="SECURITY",
        description="Terminated active sessions across other devices",
        ip_address="127.0.0.1",
        created_at=datetime.datetime.utcnow()
    )
    db.add(act)
    db.commit()
    return count

def generate_user_recovery_codes(db: Session, user: User, count: int = 8) -> list:
    # Clear existing unused codes
    db.query(RecoveryCode).filter(
        RecoveryCode.user_id == user.user_id,
        RecoveryCode.used == False
    ).delete()
    
    plain_codes = []
    for _ in range(count):
        part1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        part2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"{part1}-{part2}"
        plain_codes.append(code)
        
        rc = RecoveryCode(
            user_id=user.user_id,
            code_hash=hash_password(code),
            used=False,
            created_at=datetime.datetime.utcnow()
        )
        db.add(rc)
        
    db.commit()
    return plain_codes

def calculate_security_score(user: User, db: Session) -> int:
    score = 40  # base
    if user.email_verified:
        score += 30
    
    # check if recovery codes exist
    codes_count = db.query(RecoveryCode).filter(
        RecoveryCode.user_id == user.user_id,
        RecoveryCode.used == False
    ).count()
    if codes_count > 0:
        score += 20
        
    # check recent failed logins
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    failed = db.query(LoginHistory).filter(
        LoginHistory.user_id == user.user_id,
        LoginHistory.success == False,
        LoginHistory.created_at >= cutoff
    ).count()
    if failed == 0:
        score += 10
    else:
        score -= min(15, failed * 5)
        
    return min(100, max(20, score))

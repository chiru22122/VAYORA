import os
import datetime
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, EmailOTP, Card, Activity, AuditLog
from backend.schemas import (
    UserRegisterRequest, UserLoginRequest, ResendOTPRequest, VerifyEmailRequest, VerifyLoginOTPRequest,
    ForgotPasswordRequest, ResetPasswordRequest, TokenResponse, UserResponse
)
from backend.auth import (
    hash_password, verify_password, create_access_token, generate_otp,
    generate_virtual_card_number
)
from backend.dependencies import get_current_user
from backend.services.wallet_service import get_or_create_wallet
from backend.services.payment_service import ensure_user_accounts
from backend.services.address_service import ensure_user_token_addresses
from backend.services.security_service import record_login_attempt, register_session, revoke_all_sessions
from backend.services.email_service import (
    send_login_otp_email, send_registration_otp_email, send_password_reset_email,
    get_recent_emails, is_smtp_configured
)
from backend.services.presence_service import (
    update_user_presence, remove_user_presence, safe_dispatch_presence
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.get("/email-status")
def get_email_status():
    """Returns whether live SMTP is configured or running in development sandbox."""
    return {
        "smtp_configured": is_smtp_configured(),
        "mode": "LIVE_SMTP" if is_smtp_configured() else "SANDBOX_SIMULATION",
        "description": "Real emails are delivered to user inboxes when SMTP is configured in .env."
    }

@router.get("/recent-emails")
def get_dispatched_emails(limit: int = 15):
    """Returns recent dispatched emails for debugging/inspection in sandbox or demo mode."""
    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production" or bool(os.getenv("VERCEL_ENV"))
    if is_prod:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recent emails inspection is disabled in production."
        )
    return get_recent_emails(limit)

@router.post("/register", response_model=TokenResponse)
def register(req: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists"
        )
        
    user = User(
        name=req.name.strip(),
        email=clean_email,
        password_hash=hash_password(req.password),
        email_verified=False,
        role="user",
        phone=req.phone,
        avatar_color="#00f59b",
        created_at=datetime.datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Initialize wallet, token addresses & authoritative double-entry accounts
    get_or_create_wallet(db, user)
    ensure_user_accounts(db, user)
    ensure_user_token_addresses(db, user)
    
    # Create Default Virtual Card
    card_num = generate_virtual_card_number()
    card = Card(
        user_id=user.user_id,
        cardholder_name=user.name.upper(),
        masked_number=f"•••• •••• •••• {card_num[-4:]}",
        full_number=card_num,
        expiry="12/29",
        cvv=str(datetime.datetime.now().microsecond)[:3].zfill(3),
        status="ACTIVE",
        balance=1000.0,
        daily_limit=5000.0,
        card_tier="BLACK OBSIDIAN"
    )
    db.add(card)
    
    # Generate verification OTP
    otp_code = generate_otp(6)
    otp = EmailOTP(
        user_id=user.user_id,
        email=clean_email,
        otp_code=otp_code,
        otp_type="verify_email",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
        used=False
    )
    db.add(otp)
    
    # Activity
    ip = get_client_ip(request)
    act = Activity(
        user_id=user.user_id,
        action="LOGIN",
        description="Account registered successfully. Verification code generated.",
        ip_address=ip
    )
    db.add(act)
    db.commit()
    
    # Dispatch Real Email to user
    try:
        send_registration_otp_email(clean_email, otp_code, user.name)
    except Exception:
        pass
    
    token_id = str(uuid.uuid4())
    access_token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role, "jti": token_id})
    register_session(db, user, token_id, "Web / Registration", ip)
    record_login_attempt(db, user.user_id, "Web / Registration", ip, True, "Registration Success")

    # Update real-time presence
    update_user_presence(user.user_id, user.name, user.email, user.role, user.avatar_color, "registration", ip, "Web / Registration")
    safe_dispatch_presence()
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user),
        requires_otp=False,
        email=clean_email,
        message=f"Registration successful. A verification code has been dispatched to {clean_email}."
    )

@router.post("/verify-email")
def verify_email(req: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    ip = get_client_ip(request)
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.email_verified:
        token_id = str(uuid.uuid4())
        access_token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role, "jti": token_id})
        register_session(db, user, token_id, "Web / Verify Email", ip)
        return {
            "message": "Email address is already verified",
            "email_verified": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.from_orm(user)
        }
        
    otp = db.query(EmailOTP).filter(
        EmailOTP.email == clean_email,
        EmailOTP.otp_code == req.otp_code.strip(),
        EmailOTP.otp_type == "verify_email",
        EmailOTP.used == False,
        EmailOTP.expires_at >= datetime.datetime.utcnow()
    ).order_by(EmailOTP.otp_id.desc()).first()
    
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification OTP code"
        )
        
    otp.used = True
    user.email_verified = True

    # Audit Log
    audit = AuditLog(
        user_id=user.user_id,
        action="EMAIL_VERIFIED",
        details=f"Email address {clean_email} successfully verified via OTP.",
        ip_address=ip,
        created_at=datetime.datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    token_id = str(uuid.uuid4())
    access_token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role, "jti": token_id})
    register_session(db, user, token_id, "Web / Verify Email", ip)

    return {
        "message": "Email address verified successfully",
        "email_verified": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(user)
    }

@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    ip = get_client_ip(request)
    device = req.device_info or "Web Browser"
    
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        record_login_attempt(db, 0, device, ip, False, "User not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    if not verify_password(req.password, user.password_hash):
        record_login_attempt(db, user.user_id, device, ip, False, "Invalid password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # If otp_code was supplied directly with login
    if req.otp_code:
        otp = db.query(EmailOTP).filter(
            EmailOTP.email == clean_email,
            EmailOTP.otp_code == req.otp_code.strip(),
            EmailOTP.otp_type == "login_otp",
            EmailOTP.used == False,
            EmailOTP.expires_at >= datetime.datetime.utcnow()
        ).order_by(EmailOTP.otp_id.desc()).first()

        if not otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired login verification code"
            )
        otp.used = True

    # Generate fresh login OTP and dispatch REAL email
    otp_code = generate_otp(6)
    login_otp = EmailOTP(
        user_id=user.user_id,
        email=clean_email,
        otp_code=otp_code,
        otp_type="login_otp",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
        used=False
    )
    db.add(login_otp)
    db.commit()

    # Dispatch REAL email to user's real email address
    try:
        send_login_otp_email(clean_email, otp_code, user.name, ip, device)
    except Exception:
        pass

    # Check if 2-Step Verification should be presented to the user
    # Real emails (not ending with .demo) or explicit require_otp requests will require the code
    is_demo_account = clean_email.endswith(".demo")
    should_require_otp = (req.require_otp is True) or (not is_demo_account and not req.otp_code)

    if should_require_otp:
        return TokenResponse(
            access_token=None,
            token_type="bearer",
            user=None,
            requires_otp=True,
            email=clean_email,
            message=f"A 6-digit security code has been sent to {clean_email}. Please enter it to complete sign in."
        )

    # Complete Login (Issued directly for demo accounts or after OTP verification)
    token_id = str(uuid.uuid4())
    access_token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role, "jti": token_id})
    register_session(db, user, token_id, device, ip)
    record_login_attempt(db, user.user_id, device, ip, True, "Login Successful")
    db.commit()

    # Track real-time presence
    update_user_presence(user.user_id, user.name, user.email, user.role, user.avatar_color, "dashboard", ip, device)
    safe_dispatch_presence()
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user),
        requires_otp=False,
        email=clean_email,
        message=f"Login successful. Security Code sent to email: {otp_code}"
    )

@router.post("/verify-login-otp", response_model=TokenResponse)
def verify_login_otp(req: VerifyLoginOTPRequest, request: Request, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    otp = db.query(EmailOTP).filter(
        EmailOTP.email == clean_email,
        EmailOTP.otp_code == req.otp_code.strip(),
        EmailOTP.otp_type == "login_otp",
        EmailOTP.used == False,
        EmailOTP.expires_at >= datetime.datetime.utcnow()
    ).order_by(EmailOTP.otp_id.desc()).first()
    
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired login code. Please check your email or click resend."
        )
        
    otp.used = True
    ip = get_client_ip(request)
    device = req.device_info or "Web Browser / 2FA Verified"
    
    token_id = str(uuid.uuid4())
    access_token = create_access_token({"sub": str(user.user_id), "email": user.email, "role": user.role, "jti": token_id})
    register_session(db, user, token_id, device, ip)
    record_login_attempt(db, user.user_id, device, ip, True, "OTP Login Success")
    db.commit()

    # Update real-time presence
    update_user_presence(user.user_id, user.name, user.email, user.role, user.avatar_color, "dashboard", ip, device)
    safe_dispatch_presence()
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user),
        requires_otp=False,
        email=clean_email,
        message="Two-step authentication passed. Welcome to VAYORA!"
    )

@router.post("/resend-login-otp")
def resend_login_otp(req: ResendOTPRequest, request: Request, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp_code = generate_otp(6)
    login_otp = EmailOTP(
        user_id=user.user_id,
        email=clean_email,
        otp_code=otp_code,
        otp_type=req.otp_type,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
        used=False
    )
    db.add(login_otp)
    db.commit()

    ip = get_client_ip(request)
    if req.otp_type == "verify_email":
        send_registration_otp_email(clean_email, otp_code, user.name)
    else:
        send_login_otp_email(clean_email, otp_code, user.name, ip, "Web Browser")

    return {
        "success": True,
        "message": f"A fresh verification code has been dispatched to {clean_email}.",
        "otp_hint": otp_code if not is_smtp_configured() else None
    }

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        return {"message": "If the account exists, a reset code has been generated", "otp_hint": None}
        
    otp_code = generate_otp(6)
    otp = EmailOTP(
        user_id=user.user_id,
        email=clean_email,
        otp_code=otp_code,
        otp_type="reset_password",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
        used=False
    )
    db.add(otp)
    db.commit()

    try:
        send_password_reset_email(clean_email, otp_code, user.name)
    except Exception:
        pass

    return {
        "message": f"Password reset code dispatched to {clean_email}.",
        "otp_hint": otp_code if not is_smtp_configured() else None
    }

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    otp = db.query(EmailOTP).filter(
        EmailOTP.email == clean_email,
        EmailOTP.otp_code == req.otp_code.strip(),
        EmailOTP.otp_type == "reset_password",
        EmailOTP.used == False,
        EmailOTP.expires_at >= datetime.datetime.utcnow()
    ).order_by(EmailOTP.otp_id.desc()).first()
    
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset code")
        
    otp.used = True
    user.password_hash = hash_password(req.new_password)
    
    # Revoke all old sessions
    revoke_all_sessions(db, user)
    db.commit()
    return {"message": "Password has been successfully updated. Please login with your new password."}

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    remove_user_presence(current_user.user_id)
    safe_dispatch_presence()
    return {"message": "Logged out successfully"}

@router.post("/logout-all")
def logout_all(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    remove_user_presence(current_user.user_id)
    count = revoke_all_sessions(db, current_user)
    safe_dispatch_presence()
    return {"message": f"Successfully revoked {count} active sessions across all devices"}

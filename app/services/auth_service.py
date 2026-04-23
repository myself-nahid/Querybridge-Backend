from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User, UserStatus
from app.models.otp import OTPCode
from app.core.security import verify_password, get_password_hash, create_access_token
from jose import jwt
from app.core.config import settings
from app.services.email_service import send_otp_email
from datetime import datetime, timedelta
import random

def create_refresh_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # Default 7 days
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_refresh_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError()
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if user.status == UserStatus.PENDING:
        raise HTTPException(status_code=403, detail="Account pending admin approval")
    if user.status == UserStatus.REJECTED:
        raise HTTPException(status_code=403, detail="Account rejected")
        
    return user

def generate_tokens(user):
    access_token = create_access_token(data={"sub": user.email, "role": user.role.value})
    refresh_token = create_refresh_token(data={"sub": user.email, "role": user.role.value})
    return access_token, refresh_token

def generate_forgot_password_otp(db: Session, email: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Prevent email enumeration by returning a generic success message
        return True

    otp = str(random.randint(100000, 999999))
    expiration = datetime.utcnow() + timedelta(minutes=10)

    db_otp = OTPCode(email=email, code=otp, expires_at=expiration)
    db.add(db_otp)
    db.commit()
    
    send_otp_email(email, otp)
    return True

def verify_otp_and_get_token(db: Session, email: str, otp_code: str):
    record = db.query(OTPCode).filter(
        OTPCode.email == email, 
        OTPCode.code == otp_code
    ).order_by(OTPCode.id.desc()).first()

    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # Clean up OTP
    db.delete(record)
    db.commit()

    # Generate temp token valid for 15 mins
    reset_token = create_access_token(data={"sub": email, "type": "reset"}, expires_delta=timedelta(minutes=15))
    return reset_token

def reset_user_password(db: Session, email: str, new_password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.password_hash = get_password_hash(new_password)
    db.commit()
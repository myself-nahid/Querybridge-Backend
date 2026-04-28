from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User, UserStatus
from app.models.otp import OTPCode
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from jose import JWTError, jwt
from app.core.config import settings
from app.services.email_service import send_otp_email
from datetime import datetime, timedelta
import random

async def authenticate_user(db: AsyncSession, email: str, password: str):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if user.status == UserStatus.PENDING:
        raise HTTPException(status_code=403, detail="Account pending admin approval")
    if user.status == UserStatus.REJECTED:
        raise HTTPException(status_code=403, detail="Account rejected")
        
    return user

def generate_tokens(user: User):
    access_token = create_access_token(data={"sub": user.email, "role": user.role.value})
    refresh_token = create_refresh_token(data={"sub": user.email, "role": user.role.value})
    return access_token, refresh_token

def verify_refresh_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError()
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

async def generate_forgot_password_otp(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        return True

    otp = str(random.randint(100000, 999999))
    expiration = datetime.utcnow() + timedelta(minutes=10)

    db_otp = OTPCode(email=email, code=otp, expires_at=expiration)
    db.add(db_otp)
    await db.commit()
    
    send_otp_email(email, otp)
    return True

async def verify_otp_and_get_token(db: AsyncSession, email: str, otp_code: str):
    query = select(OTPCode).where(OTPCode.email == email, OTPCode.code == otp_code).order_by(OTPCode.id.desc())
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    await db.delete(record)
    await db.commit()

    reset_token = create_access_token(data={"sub": email, "type": "reset"}, expires_delta=timedelta(minutes=15))
    return reset_token

async def reset_user_password(db: AsyncSession, email: str, new_password: str):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.password_hash = get_password_hash(new_password)
    await db.commit()
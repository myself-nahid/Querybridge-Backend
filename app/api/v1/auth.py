from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.auth import UserSignUp, UserLogin, ForgotPassword, VerifyOTP, ResetPassword, UserLoginData, VerifyOTPData
from app.schemas.response import StandardResponse
from app.services import auth_service
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.core.config import settings
from jose import jwt

router = APIRouter()

@router.post("/signup", response_model=StandardResponse[None])
def signup(data: UserSignUp, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    new_user = User(
        name=data.name,
        email=data.email,
        password_hash=get_password_hash(data.password),
        role=data.role
    )
    db.add(new_user)
    db.commit()
    return StandardResponse(success=True, message="Signup successful. Please wait for Admin approval.")

@router.post("/login", response_model=StandardResponse[UserLoginData])
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, data.email, data.password)
    access_token = create_access_token(data={"sub": user.email, "role": user.role.value})
    
    response_data = UserLoginData(
        access_token=access_token,
        user={"name": user.name, "email": user.email, "role": user.role.value}
    )
    return StandardResponse(success=True, message="Login successful.", data=response_data)

@router.post("/forgot-password", response_model=StandardResponse[None])
def forgot_password(data: ForgotPassword, db: Session = Depends(get_db)):
    auth_service.generate_forgot_password_otp(db, data.email)
    return StandardResponse(success=True, message="If the email is registered, an OTP has been sent.")

@router.post("/verify-otp", response_model=StandardResponse[VerifyOTPData])
def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    reset_token = auth_service.verify_otp_and_get_token(db, data.email, data.otp_code)
    return StandardResponse(success=True, message="OTP verified successfully.", data=VerifyOTPData(reset_token=reset_token))

@router.post("/reset-password", response_model=StandardResponse[None])
def reset_password(data: ResetPassword, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.reset_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        token_type = payload.get("type")
        if token_type != "reset":
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    auth_service.reset_user_password(db, email, data.new_password)
    return StandardResponse(success=True, message="Password updated successfully.")
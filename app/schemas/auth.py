from pydantic import BaseModel, EmailStr
from app.models.user import UserRole
from typing import Optional

class UserSignUp(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPassword(BaseModel):
    email: EmailStr

class VerifyOTP(BaseModel):
    email: EmailStr
    otp_code: str

class ResetPassword(BaseModel):
    reset_token: str
    new_password: str

class UserLoginData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class VerifyOTPData(BaseModel):
    reset_token: str
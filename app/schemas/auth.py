from pydantic import BaseModel, EmailStr, field_validator
from app.models.user import UserRole
from typing import Optional

class UserSignUp(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole

    @field_validator("role", mode="before")
    def parse_role(cls, role):
        if isinstance(role, UserRole):
            return role
        if isinstance(role, str):
            try:
                return UserRole[role]
            except KeyError:
                for item in UserRole:
                    if item.value.lower() == role.lower():
                        return item
        raise ValueError(f"Invalid role: {role}")

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

class UserSignUpResponse(BaseModel):
    # id: int
    name: str
    email: EmailStr
    role: UserRole
    status: str

    class Config:
        from_attributes = True

class UserLoginData(BaseModel):
    access_token: str
    refresh_token: str
    # token_type: str = "bearer"
    user: dict

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class VerifyOTPData(BaseModel):
    reset_token: str
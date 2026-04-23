from pydantic import BaseModel, EmailStr

class UserSignUp(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str

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
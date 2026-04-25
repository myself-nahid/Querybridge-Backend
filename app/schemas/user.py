from pydantic import BaseModel, EmailStr, Field, model_validator, computed_field
from typing import Optional
from app.models.user import UserRole, UserStatus
from app.core.config import settings  

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    role: UserRole
    status: UserStatus
    
    avatar_url: Optional[str] = None 

    class Config:
        from_attributes = True

# WEB USER SETTINGS SCHEMA 
class WebUserUpdateProfile(BaseModel):
    name: str
    # email: EmailStr

# ADMIN SETTINGS SCHEMA 
class AdminUpdateProfile(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None

# SHARED PASSWORD SCHEMA 
class UpdatePassword(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @model_validator(mode='after')
    def verify_passwords_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password and confirm password do not match")
        return self
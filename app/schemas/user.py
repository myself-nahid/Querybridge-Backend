from pydantic import BaseModel, EmailStr
from app.models.user import UserRole, UserStatus

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    status: UserStatus

    class Config:
        from_attributes = True
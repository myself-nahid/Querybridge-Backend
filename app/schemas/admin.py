from pydantic import BaseModel, EmailStr
from typing import List
from app.models.user import UserRole, UserStatus
from app.schemas.user import UserOut

# Dashboard Stats Schemas 
class YearlyGrowth(BaseModel):
    year: str
    count: int

class DashboardStatsData(BaseModel):
    total_users: int
    approved_users: int
    pending_users: int
    yearly_growth: List[YearlyGrowth]

# User Management Schemas 
class UserCreateByAdmin(BaseModel):
    name: str
    email: EmailStr
    role: UserRole
    # In the Figma UI, "Add User" doesn't ask for a password. 
    # We will generate a default one or leave it to a "Welcome Email" flow.
    password: str = "changeme123" 

class UserUpdate(BaseModel):
    name: str
    email: EmailStr
    role: UserRole
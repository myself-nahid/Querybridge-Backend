from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional
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
    total_users_growth: float
    approved_users_growth: float
    pending_users_growth: float
    yearly_growth: List[YearlyGrowth]

# User Management Schemas 
class UserCreateByAdmin(BaseModel):
    name: str
    email: EmailStr
    role: UserRole
    # In the Figma UI, "Add User" doesn't ask for a password. 
    # We will generate a default one or leave it to a "Welcome Email" flow.
    password: str = "changeme123" 

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

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None

    @field_validator("role", mode="before")
    def parse_role(cls, role):
        if role is None:  
            return role
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

class PaginatedNotifications(BaseModel):
    total_requests: int
    current_page: int
    total_pages: int
    limit: int
    requests: List[UserOut]

class PaginatedUsers(BaseModel):
    total_users: int
    current_page: int
    total_pages: int
    limit: int
    users: List[UserOut]
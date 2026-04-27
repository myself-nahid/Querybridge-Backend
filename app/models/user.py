from sqlalchemy import Column, DateTime, Integer, String, Enum
from datetime import datetime
from app.db.database import Base
import enum

class UserStatus(str, enum.Enum):
    PENDING = "Pending"
    ACTIVE = "Active"
    REJECTED = "Rejected"

class UserRole(str, enum.Enum):
    ADMIN = "Admin"
    SALES_MANAGER = "Sales Manager"
    SALESPEOPLE = "Salespeople"
    CEO = "CEO"
    CFO = "CFO"
    PRODUCTION_MANAGER = "Production Manager"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True) 
    role = Column(Enum(UserRole), default=UserRole.SALES_MANAGER)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
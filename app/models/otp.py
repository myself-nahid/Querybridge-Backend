from sqlalchemy import Column, Integer, String, DateTime
from app.db.database import Base
from datetime import datetime

class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    code = Column(String(6), index=True) # 6-digit code
    expires_at = Column(DateTime)
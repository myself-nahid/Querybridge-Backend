from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User, UserStatus
from app.schemas.user import UserOut
from app.schemas.response import StandardResponse
from app.core.dependencies import get_current_user, get_current_admin
from typing import List

router = APIRouter()

# User Profile
@router.get("/me", response_model=StandardResponse[UserOut])
def read_current_user(current_user: User = Depends(get_current_user)):
    return StandardResponse(success=True, message="Profile fetched successfully.", data=current_user)

# Admin Only - List Pending Users
@router.get("/pending", response_model=StandardResponse[List[UserOut]])
def get_pending_users(db: Session = Depends(get_db), current_admin: User = Depends(get_current_admin)):
    users = db.query(User).filter(User.status == UserStatus.PENDING).all()
    return StandardResponse(success=True, message="Pending users fetched.", data=users)

# Admin Only - Approve User
@router.post("/{user_id}/approve", response_model=StandardResponse[None])
def approve_user(user_id: int, db: Session = Depends(get_db), current_admin: User = Depends(get_current_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = UserStatus.ACTIVE
    db.commit()
    return StandardResponse(success=True, message=f"User {user.email} approved successfully.")
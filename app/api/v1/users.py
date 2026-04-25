from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from app.core.security import get_password_hash, verify_password
from app.db.database import get_db
from app.models.user import User, UserStatus
from app.schemas.user import UserOut, WebUserUpdateProfile, UpdatePassword
from app.schemas.response import StandardResponse
from app.core.dependencies import get_current_user, get_current_admin
import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.response import StandardResponse
from app.schemas.user import UserOut, WebUserUpdateProfile, UpdatePassword
from app.core.dependencies import get_current_user
from app.core.security import verify_password, get_password_hash
from app.core.config import settings

router = APIRouter()

UPLOAD_DIR = "uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/me", response_model=StandardResponse[UserOut])
def get_my_profile(current_user: User = Depends(get_current_user)):
    """Fetch current user profile (Works for both Admins and Web Users)"""
    return StandardResponse(success=True, message="Profile fetched.", data=current_user)

@router.put("/me", response_model=StandardResponse[UserOut])
def update_web_user_profile(
    data: WebUserUpdateProfile, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """WEB USER: Updates Name and Email only."""
    # if data.email != current_user.email:
    #     if db.query(User).filter(User.email == data.email).first():
    #         raise HTTPException(status_code=400, detail="Email already in use.")

    current_user.name = data.name
    # current_user.email = data.email
    db.commit()
    db.refresh(current_user)

    return StandardResponse(success=True, message="Profile updated.", data=current_user)

@router.put("/me/password", response_model=StandardResponse[None])
def update_web_user_password(
    data: UpdatePassword, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """WEB USER: Updates Password."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return StandardResponse(success=True, message="Password updated successfully.")

@router.post("/me/avatar", response_model=StandardResponse[UserOut])
async def upload_avatar(
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """WEB USER: Upload Profile Picture."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    file_extension = file.filename.split(".")[-1]
    new_filename = f"{current_user.id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    # 1. Delete old avatar (we extract the filename from the old URL)
    if current_user.avatar_url:
        old_filename = current_user.avatar_url.split("/")[-1]
        old_file_path = os.path.join(UPLOAD_DIR, old_filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

    # 2. Save the new image file to the disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Create the exact Full URL
    base_url = settings.BACKEND_URL.rstrip("/")
    full_url = f"{base_url}/api/v1/avatars/{new_filename}"

    # 4. Save the exact Full URL into the database column!
    current_user.avatar_url = full_url
    
    db.commit()
    db.refresh(current_user)

    return StandardResponse(success=True, message="Profile picture updated.", data=current_user)

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
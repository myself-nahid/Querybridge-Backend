import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.database import get_db
from app.models.user import User, UserStatus
from app.schemas.response import StandardResponse
from app.schemas.user import UserOut, WebUserUpdateProfile, UpdatePassword
from app.core.dependencies import get_current_user, get_current_admin
from app.core.security import verify_password, get_password_hash
from app.core.config import settings

router = APIRouter()

UPLOAD_DIR = "uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/me", response_model=StandardResponse[UserOut])
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return StandardResponse(success=True, message="Profile fetched.", data=current_user)

@router.put("/me", response_model=StandardResponse[UserOut])
async def update_web_user_profile(data: WebUserUpdateProfile, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.name = data.name
    await db.commit()
    await db.refresh(current_user)
    return StandardResponse(success=True, message="Profile updated.", data=current_user)

@router.put("/me/password", response_model=StandardResponse[None])
async def update_web_user_password(data: UpdatePassword, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    current_user.password_hash = get_password_hash(data.new_password)
    await db.commit()
    return StandardResponse(success=True, message="Password updated successfully.")

@router.post("/me/avatar", response_model=StandardResponse[UserOut])
async def upload_avatar(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    file_extension = file.filename.split(".")[-1]
    new_filename = f"{current_user.id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)

    if current_user.avatar_url:
        old_filename = current_user.avatar_url.split("/")[-1]
        old_file_path = os.path.join(UPLOAD_DIR, old_filename)
        if os.path.exists(old_file_path):
            os.remove(old_file_path)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    base_url = settings.BACKEND_URL.rstrip("/")
    current_user.avatar_url = f"{base_url}/api/v1/avatars/{new_filename}"
    
    await db.commit()
    await db.refresh(current_user)

    return StandardResponse(success=True, message="Profile picture updated.", data=current_user)

# Admin Only - List Pending Users
@router.get("/pending", response_model=StandardResponse[List[UserOut]])
async def get_pending_users(db: AsyncSession = Depends(get_db), current_admin: User = Depends(get_current_admin)):
    result = await db.execute(select(User).where(User.status == UserStatus.PENDING))
    users = result.scalars().all()
    return StandardResponse(success=True, message="Pending users fetched.", data=users)

# Admin Only - Approve User
@router.post("/{user_id}/approve", response_model=StandardResponse[None])
async def approve_user(user_id: int, db: AsyncSession = Depends(get_db), current_admin: User = Depends(get_current_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = UserStatus.ACTIVE
    await db.commit()
    return StandardResponse(success=True, message=f"User {user.email} approved successfully.")
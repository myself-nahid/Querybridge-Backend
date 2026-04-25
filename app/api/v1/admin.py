from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.core.dependencies import get_current_admin
from app.core.dependencies import get_current_admin
from app.db.database import get_db
from app.models.user import User, UserStatus
from app.schemas.response import StandardResponse
from app.schemas.user import UserOut
from app.schemas.admin import DashboardStatsData, PaginatedNotifications, YearlyGrowth, UserCreateByAdmin, UserUpdate
from app.schemas.user import AdminUpdateProfile, UpdatePassword
from app.core.security import verify_password, get_password_hash
from datetime import datetime
import math

# Enforce Admin access on ALL routes in this router
router = APIRouter(dependencies=[Depends(get_current_admin)])

# 1. DASHBOARD STATS
@router.get("/dashboard-stats", response_model=StandardResponse[DashboardStatsData])
def get_dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(User).count()
    approved = db.query(User).filter(User.status == UserStatus.ACTIVE).count()
    pending = db.query(User).filter(User.status == UserStatus.PENDING).count()

    # Calculate actual yearly growth from DB
    yearly_counts = db.query(
        func.extract('year', User.created_at).label('year'),
        func.count(User.id).label('count')
    ).group_by('year').order_by('year').all()

    # Format for the frontend chart (handling empty DB edge cases)
    growth_data =[YearlyGrowth(year=str(int(yc.year)), count=yc.count) for yc in yearly_counts]
    
    # Optional: If DB is empty/new, mock some data for the chart to match Figma
    if not growth_data:
        current_year = datetime.utcnow().year
        growth_data =[
            YearlyGrowth(year=str(y), count=0) for y in range(current_year - 4, current_year + 1)
        ]

    data = DashboardStatsData(
        total_users=total,
        approved_users=approved,
        pending_users=pending,
        yearly_growth=growth_data
    )
    return StandardResponse(success=True, message="Stats fetched successfully", data=data)

# 2. USER MANAGEMENT (CRUD)
@router.get("/users", response_model=StandardResponse[List[UserOut]])
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.role != "Admin").order_by(User.id.desc()).all()
    return StandardResponse(success=True, message="Users fetched successfully", data=users)

@router.post("/users", response_model=StandardResponse[UserOut])
def add_user(data: UserCreateByAdmin, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Users created by admin are instantly ACTIVE
    new_user = User(
        name=data.name,
        email=data.email,
        role=data.role,
        password_hash=get_password_hash(data.password),
        status=UserStatus.ACTIVE 
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return StandardResponse(success=True, message="User created successfully", data=new_user)

@router.put("/users/{user_id}", response_model=StandardResponse[UserOut])
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if changing email to one that already exists
    if data.email != user.email and db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already in use")

    user.name = data.name
    user.email = data.email
    user.role = data.role
    db.commit()
    db.refresh(user)
    return StandardResponse(success=True, message="User updated successfully", data=user)

@router.delete("/users/{user_id}", response_model=StandardResponse[None])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return StandardResponse(success=True, message="User deleted successfully")

# 3. NOTIFICATIONS 
@router.get("/notifications", response_model=StandardResponse[PaginatedNotifications])
def get_notifications(page: int = 1, limit: int = 5, db: Session = Depends(get_db)):
    """
    Fetches all PENDING users for the Notifications page, with pagination.
    """
    # 1. Calculate offset
    skip = (page - 1) * limit

    # 2. Get total count for pagination math
    total_pending = db.query(User).filter(User.status == UserStatus.PENDING).count()

    # 3. Fetch the pending users ordered by newest first
    pending_users = (
        db.query(User)
        .filter(User.status == UserStatus.PENDING)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 4. Format the paginated response
    total_pages = math.ceil(total_pending / limit) if total_pending > 0 else 1

    data = PaginatedNotifications(
        total_requests=total_pending,
        current_page=page,
        total_pages=total_pages,
        limit=limit,
        requests=pending_users
    )

    return StandardResponse(
        success=True, 
        message="Notifications fetched successfully.", 
        data=data
    )

# NOTIFICATIONS (APPROVAL/REJECTION)
@router.post("/users/{user_id}/approve", response_model=StandardResponse[None])
def approve_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = UserStatus.ACTIVE
    db.commit()
    return StandardResponse(success=True, message=f"User {user.email} approved.")

@router.post("/users/{user_id}/reject", response_model=StandardResponse[None])
def reject_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = UserStatus.REJECTED
    db.commit()
    return StandardResponse(success=True, message=f"User {user.email} rejected.")

# 4. ADMIN PROFILE SETTINGS
@router.put("/me", response_model=StandardResponse[UserOut])
def update_admin_profile(
    data: AdminUpdateProfile, 
    db: Session = Depends(get_db), 
    current_admin: User = Depends(get_current_admin)
):
    """ADMIN ONLY: Updates Name, Email, Phone, and Address."""
    if data.email != current_admin.email:
        if db.query(User).filter(User.email == data.email).first():
            raise HTTPException(status_code=400, detail="Email already in use.")

    current_admin.name = data.name
    current_admin.email = data.email
    current_admin.phone = data.phone
    current_admin.address = data.address

    db.commit()
    db.refresh(current_admin)

    return StandardResponse(success=True, message="Admin profile updated.", data=current_admin)

@router.put("/me/password", response_model=StandardResponse[None])
def update_admin_password(
    data: UpdatePassword, 
    db: Session = Depends(get_db), 
    current_admin: User = Depends(get_current_admin)
):
    """ADMIN ONLY: Updates Password."""
    if not verify_password(data.current_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    current_admin.password_hash = get_password_hash(data.new_password)
    db.commit()

    return StandardResponse(success=True, message="Admin password updated successfully.")
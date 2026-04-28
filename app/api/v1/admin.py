from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, or_
from typing import List
import math
import asyncio
from datetime import datetime

from app.core.dependencies import get_current_admin
from app.db.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.schemas.response import StandardResponse
from app.schemas.user import UserOut, AdminUpdateProfile, UpdatePassword
from app.schemas.admin import DashboardStatsData, PaginatedNotifications, YearlyGrowth, UserCreateByAdmin, UserUpdate, PaginatedUsers
from app.core.security import verify_password, get_password_hash

router = APIRouter(dependencies=[Depends(get_current_admin)])

def normalize_user_role(role_input):
    if isinstance(role_input, UserRole): return role_input
    if isinstance(role_input, str):
        try: return UserRole[role_input]
        except KeyError: pass
        for role in UserRole:
            if role.value.lower() == role_input.lower(): return role
    raise HTTPException(status_code=400, detail=f"Invalid role: {role_input}")

# ==========================================
# 1. DASHBOARD STATS (Optimized with Async Gather)
# ==========================================
@router.get("/dashboard-stats", response_model=StandardResponse[DashboardStatsData])
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    current_year = datetime.utcnow().year
    prev_year = current_year - 1

    # Define all queries
    total_q = select(func.count()).select_from(User)
    approved_q = select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE)
    pending_q = select(func.count()).select_from(User).where(User.status == UserStatus.PENDING)

    yearly_counts_q = select(extract('year', User.created_at).label('year'), func.count(User.id).label('count')).group_by('year').order_by('year')

    cur_yr_q = select(func.count()).select_from(User).where(extract('year', User.created_at) == current_year)
    prev_yr_q = select(func.count()).select_from(User).where(extract('year', User.created_at) == prev_year)

    # Execute ALL 10 queries CONCURRENTLY
    results = await asyncio.gather(
        db.execute(total_q),
        db.execute(approved_q),
        db.execute(pending_q),
        db.execute(yearly_counts_q),
        db.execute(cur_yr_q),
        db.execute(prev_yr_q),
        db.execute(cur_yr_q.where(User.status == UserStatus.ACTIVE)),
        db.execute(prev_yr_q.where(User.status == UserStatus.ACTIVE)),
        db.execute(cur_yr_q.where(User.status == UserStatus.PENDING)),
        db.execute(prev_yr_q.where(User.status == UserStatus.PENDING))
    )

    total = results[0].scalar()
    approved = results[1].scalar()
    pending = results[2].scalar()
    yearly_counts = results[3].all()
    
    total_this_year = results[4].scalar()
    total_last_year = results[5].scalar()
    approved_this_year = results[6].scalar()
    approved_last_year = results[7].scalar()
    pending_this_year = results[8].scalar()
    pending_last_year = results[9].scalar()

    # Calculations
    growth_data =[YearlyGrowth(year=str(int(yc.year)), count=yc.count) for yc in yearly_counts]
    if not growth_data:
        growth_data =[YearlyGrowth(year=str(y), count=0) for y in range(current_year - 4, current_year + 1)]

    def calc_growth(current, previous):
        if not previous or previous == 0: return 0.0 if not current else 100.0
        return round(((current - previous) / previous) * 100, 2)

    data = DashboardStatsData(
        total_users=total, approved_users=approved, pending_users=pending,
        total_users_growth=calc_growth(total_this_year, total_last_year),
        approved_users_growth=calc_growth(approved_this_year, approved_last_year),
        pending_users_growth=calc_growth(pending_this_year, pending_last_year),
        yearly_growth=growth_data
    )
    return StandardResponse(success=True, message="Stats fetched successfully", data=data)

# ==========================================
# 2. USER MANAGEMENT
# ==========================================
@router.get("/users", response_model=StandardResponse[PaginatedUsers])
async def get_all_users(page: int = 1, limit: int = 10, search: str | None = None, status: str = "all", db: AsyncSession = Depends(get_db)):
    skip = (page - 1) * limit
    
    base_query = select(User).where(User.role != UserRole.ADMIN)
    if status.lower() == "active": base_query = base_query.where(User.status == UserStatus.ACTIVE)
    elif status.lower() == "pending": base_query = base_query.where(User.status == UserStatus.PENDING)
    if search:
        search_filter = f"%{search}%"
        base_query = base_query.where(or_(User.name.ilike(search_filter), User.email.ilike(search_filter), User.phone.ilike(search_filter)))

    # Fetch total and paginated data concurrently
    count_res, users_res = await asyncio.gather(
        db.execute(select(func.count()).select_from(base_query.subquery())),
        db.execute(base_query.order_by(User.id.desc()).offset(skip).limit(limit))
    )
    
    total_users = count_res.scalar()
    users = users_res.scalars().all()
    total_pages = math.ceil(total_users / limit) if total_users > 0 else 1

    return StandardResponse(success=True, message="Users fetched", data=PaginatedUsers(total_users=total_users, current_page=page, total_pages=total_pages, limit=limit, users=users))

@router.post("/users", response_model=StandardResponse[UserOut])
async def add_user(data: UserCreateByAdmin, db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    new_user = User(name=data.name, email=data.email, role=normalize_user_role(data.role), password_hash=get_password_hash(data.password), status=UserStatus.ACTIVE)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return StandardResponse(success=True, message="User created", data=new_user)

@router.put("/users/{user_id}", response_model=StandardResponse[UserOut])
async def update_user(user_id: int, data: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user: 
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. Update Email (if provided and different)
    if data.email is not None and data.email != user.email:
        if (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email

    # 2. Update Name (if provided)
    if data.name is not None:
        user.name = data.name
        
    # 3. Update Role (if provided)
    if data.role is not None:
        user.role = normalize_user_role(data.role)

    await db.commit()
    await db.refresh(user)
    
    return StandardResponse(success=True, message="User updated successfully", data=user)

@router.delete("/users/{user_id}", response_model=StandardResponse[None])
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return StandardResponse(success=True, message="User deleted successfully")

# ==========================================
# 3. NOTIFICATIONS
# ==========================================
@router.get("/notifications", response_model=StandardResponse[PaginatedNotifications])
async def get_notifications(page: int = 1, limit: int = 5, db: AsyncSession = Depends(get_db)):
    skip = (page - 1) * limit
    base_q = select(User).where(User.status == UserStatus.PENDING)

    count_res, users_res = await asyncio.gather(
        db.execute(select(func.count()).select_from(base_q.subquery())),
        db.execute(base_q.order_by(User.created_at.desc()).offset(skip).limit(limit))
    )
    
    total_pending = count_res.scalar()
    pending_users = users_res.scalars().all()
    total_pages = math.ceil(total_pending / limit) if total_pending > 0 else 1

    return StandardResponse(success=True, message="Notifications fetched.", data=PaginatedNotifications(total_requests=total_pending, current_page=page, total_pages=total_pages, limit=limit, requests=pending_users))

@router.post("/users/{user_id}/approve", response_model=StandardResponse[None])
async def approve_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user.status = UserStatus.ACTIVE
    await db.commit()
    return StandardResponse(success=True, message="User approved.")

@router.post("/users/{user_id}/reject", response_model=StandardResponse[None])
async def reject_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user.status = UserStatus.REJECTED
    await db.commit()
    return StandardResponse(success=True, message="User rejected.")

# ==========================================
# 4. ADMIN PROFILE SETTINGS
# ==========================================
@router.put("/me", response_model=StandardResponse[UserOut])
async def update_admin_profile(data: AdminUpdateProfile, db: AsyncSession = Depends(get_db), current_admin: User = Depends(get_current_admin)):
    if data.email != current_admin.email and (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already in use.")

    current_admin.name, current_admin.email, current_admin.phone, current_admin.address = data.name, data.email, data.phone, data.address
    await db.commit()
    await db.refresh(current_admin)
    return StandardResponse(success=True, message="Admin profile updated.", data=current_admin)

@router.put("/me/password", response_model=StandardResponse[None])
async def update_admin_password(data: UpdatePassword, db: AsyncSession = Depends(get_db), current_admin: User = Depends(get_current_admin)):
    if not verify_password(data.current_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_admin.password_hash = get_password_hash(data.new_password)
    await db.commit()
    return StandardResponse(success=True, message="Admin password updated successfully.")
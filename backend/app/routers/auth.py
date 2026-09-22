from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.database import get_db
from app.models import Agent
from app.schemas import LoginRequest, LoginResponse, UserCreate, UserUpdate, UserResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.config import settings
from app.core.deps import get_current_user, get_current_admin

router = APIRouter(prefix="/auth", tags=["Authentication & Team Members"])

@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(Agent).where(Agent.username == payload.username.strip())
    user = (await db.execute(stmt)).scalars().first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا کلمه عبور اشتباه است."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما غیرفعال شده است."
        )

    user.last_login = datetime.now(timezone.utc)
    user.is_online = True
    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role},
        secret_key=settings.SECRET_KEY
    )

    return LoginResponse(
        success=True,
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role
        }
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Agent = Depends(get_current_user)):
    return current_user

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: Agent = Depends(get_current_admin)
):
    stmt = select(Agent).order_by(desc(Agent.created_at))
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/users", response_model=UserResponse)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: Agent = Depends(get_current_admin)
):
    # Check duplicate username
    stmt = select(Agent).where(Agent.username == payload.username.strip())
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="این نام کاربری قبلاً ثبت شده است.")

    new_user = Agent(
        username=payload.username.strip(),
        display_name=payload.display_name.strip(),
        email=payload.email or "",
        password_hash=hash_password(payload.password),
        role=payload.role if payload.role in ["admin", "agent"] else "agent",
        is_active=True,
        is_online=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Agent = Depends(get_current_admin)
):
    stmt = select(Agent).where(Agent.id == user_id)
    user = (await db.execute(stmt)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)

    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: Agent = Depends(get_current_admin)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="امکان حذف حساب کاربری خودتان وجود ندارد.")

    stmt = select(Agent).where(Agent.id == user_id)
    user = (await db.execute(stmt)).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")

    await db.delete(user)
    await db.commit()
    return {"message": "کاربر با موفقیت حذف شد."}

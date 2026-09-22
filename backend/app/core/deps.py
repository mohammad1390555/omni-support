from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models import Agent
from app.config import settings
from app.core.security import decode_access_token

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Agent:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="احراز هویت الزامی است. لطفاً وارد سیستم شوید."
        )

    token = authorization.split(" ")[1]
    payload = decode_access_token(token, settings.SECRET_KEY)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نشست کاربری نامعتبر یا منقضی شده است."
        )

    user_id = payload["sub"]
    stmt = select(Agent).where(Agent.id == user_id)
    user = (await db.execute(stmt)).scalars().first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="حساب کاربری غیرفعال شده است."
        )

    return user

async def get_current_admin(
    current_user: Agent = Depends(get_current_user)
) -> Agent:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما دسترسی مدیریتی (Admin) برای انجام این عملیات را ندارید."
        )
    return current_user

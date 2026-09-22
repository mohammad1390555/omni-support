from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.database import get_db
from app.models import Site
from app.schemas import SiteCreate, SiteResponse

router = APIRouter(prefix="/sites", tags=["Websites & Integrations"])

@router.get("", response_model=List[SiteResponse])
async def list_sites(db: AsyncSession = Depends(get_db)):
    stmt = select(Site).order_by(desc(Site.created_at))
    res = await db.execute(stmt)
    sites = res.scalars().all()
    return sites

@router.post("", response_model=SiteResponse)
async def create_site(payload: SiteCreate, db: AsyncSession = Depends(get_db)):
    site = Site(
        name=payload.name,
        domain=payload.domain,
        welcome_message=payload.welcome_message or "سلام! چطور می‌توانیم امروز به شما کمک کنیم؟",
        primary_color=payload.primary_color or "#4f46e5",
        widget_title=payload.widget_title or "پشتیبانی آنلاین",
        widget_position=payload.widget_position or "right"
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site

@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(site_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Site).where(Site.id == site_id)
    site = (await db.execute(stmt)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="سایت مورد نظر یافت نشد.")
    return site

@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(site_id: str, payload: SiteCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(Site).where(Site.id == site_id)
    site = (await db.execute(stmt)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="سایت مورد نظر یافت نشد.")
    
    site.name = payload.name
    site.domain = payload.domain
    site.welcome_message = payload.welcome_message
    site.primary_color = payload.primary_color
    site.widget_title = payload.widget_title
    site.widget_position = payload.widget_position

    await db.commit()
    await db.refresh(site)
    return site

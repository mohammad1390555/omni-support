from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.database import get_db
from app.models import CannedResponse
from app.schemas import CannedResponseCreate, CannedResponseOut

router = APIRouter(prefix="/canned-responses", tags=["Canned Responses & Shortcuts"])

@router.get("", response_model=List[CannedResponseOut])
async def list_canned_responses(db: AsyncSession = Depends(get_db)):
    stmt = select(CannedResponse).order_by(desc(CannedResponse.created_at))
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=CannedResponseOut)
async def create_canned_response(payload: CannedResponseCreate, db: AsyncSession = Depends(get_db)):
    resp = CannedResponse(
        title=payload.title,
        shortcut=payload.shortcut or "",
        content=payload.content,
        category=payload.category or "general"
    )
    db.add(resp)
    await db.commit()
    await db.refresh(resp)
    return resp

@router.delete("/{response_id}")
async def delete_canned_response(response_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(CannedResponse).where(CannedResponse.id == response_id)
    item = (await db.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="پاسخ آماده یافت نشد.")
    await db.delete(item)
    await db.commit()
    return {"message": "حذف شد."}

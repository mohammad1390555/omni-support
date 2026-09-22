from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.database import get_db
from app.models import KnowledgeItem
from app.schemas import KnowledgeItemCreate, KnowledgeItemUpdate, KnowledgeItemResponse
from app.services.learning_service import LearningService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base & AI Memory"])

@router.get("", response_model=List[KnowledgeItemResponse])
async def list_knowledge_items(
    category: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    site_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(KnowledgeItem).order_by(desc(KnowledgeItem.created_at))
    
    if category:
        stmt = stmt.where(KnowledgeItem.category == category)
    if source:
        stmt = stmt.where(KnowledgeItem.source == source)
    if site_id:
        stmt = stmt.where(KnowledgeItem.site_id == site_id)

    res = await db.execute(stmt)
    items = res.scalars().all()

    if search and search.strip():
        q = search.strip().lower()
        items = [i for i in items if q in i.title.lower() or q in i.content.lower() or q in (i.tags or "").lower()]

    return items

@router.post("", response_model=KnowledgeItemResponse)
async def create_knowledge_item(payload: KnowledgeItemCreate, db: AsyncSession = Depends(get_db)):
    item = KnowledgeItem(
        title=payload.title,
        content=payload.content,
        category=payload.category,
        source=payload.source,
        site_id=payload.site_id,
        tags=payload.tags or "",
        is_approved=payload.is_approved
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

@router.put("/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(item_id: str, payload: KnowledgeItemUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
    item = (await db.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="آیتم دانش مورد نظر یافت نشد.")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)

    await db.commit()
    await db.refresh(item)
    return item

@router.delete("/{item_id}")
async def delete_knowledge_item(item_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
    item = (await db.execute(stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="آیتم دانش مورد نظر یافت نشد.")
    
    await db.delete(item)
    await db.commit()
    return {"message": "آیتم با موفقیت حذف گردید."}

@router.post("/test-retrieval")
async def test_retrieval(query: str = Query(..., description="سوال یا عبارت آزمایشی"), db: AsyncSession = Depends(get_db)):
    """Simulates knowledge retrieval to see what AI extracts for this question."""
    results = await LearningService.retrieve_relevant_knowledge(db, query=query, limit=5)
    output = []
    for doc, score in results:
        output.append({
            "id": doc.id,
            "title": doc.title,
            "content": doc.content,
            "category": doc.category,
            "source": doc.source,
            "relevance_score": score,
            "relevance_percent": f"{int(score * 100)}%"
        })
    return {
        "query": query,
        "matched_count": len(output),
        "results": output
    }

from fastapi import APIRouter, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models import Site, Conversation, Message
from app.schemas import ExternalMessageRequest, ConversationResponse, MessageResponse
from app.routers.chat import send_message
from app.schemas import MessageCreate

router = APIRouter(prefix="/external", tags=["External REST API"])

async def get_site_by_api_key(api_key: str, db: AsyncSession) -> Site:
    stmt = select(Site).where(Site.api_key == api_key)
    site = (await db.execute(stmt)).scalars().first()
    if not site:
        raise HTTPException(status_code=401, detail="کلید دسترسی (Site API Key) نامعتبر است.")
    if not site.is_active:
        raise HTTPException(status_code=403, detail="این وب‌سایت در پنل غیرفعال شده است.")
    return site

@router.post("/tickets", response_model=dict)
async def create_external_ticket(
    payload: ExternalMessageRequest,
    x_site_key: Optional[str] = Header(None, alias="X-Site-Key"),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates or updates a ticket from external backend systems (WordPress, Laravel, Node.js, etc.).
    """
    if not x_site_key:
        raise HTTPException(status_code=401, detail="هدر 'X-Site-Key' الزامی است.")
    
    site = await get_site_by_api_key(x_site_key, db)

    # Check for active conversation
    stmt = (
        select(Conversation)
        .where(
            Conversation.site_id == site.id,
            Conversation.customer_id == payload.customer_id,
            Conversation.status.in_(["active", "pending_human"])
        )
    )
    conv = (await db.execute(stmt)).scalars().first()

    if not conv:
        conv = Conversation(
            site_id=site.id,
            customer_id=payload.customer_id,
            customer_name=payload.customer_name or "کاربر بیرونی",
            customer_email=payload.customer_email,
            current_page=payload.current_page,
            status="active",
            ai_mode="auto"
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

    # Post the message
    msg_create = MessageCreate(
        content=payload.message,
        sender_type="customer",
        sender_name=payload.customer_name or "کاربر"
    )
    await send_message(conversation_id=conv.id, payload=msg_create, db=db)

    return {
        "success": True,
        "conversation_id": conv.id,
        "site_id": site.id,
        "status": conv.status,
        "message": "پیام با موفقیت ثبت شد و موتور هوش مصنوعی/پشتیبانی در حال بررسی آن است."
    }

@router.get("/tickets/{ticket_id}")
async def get_external_ticket(
    ticket_id: str,
    x_site_key: Optional[str] = Header(None, alias="X-Site-Key"),
    db: AsyncSession = Depends(get_db)
):
    if not x_site_key:
        raise HTTPException(status_code=401, detail="هدر 'X-Site-Key' الزامی است.")
    
    site = await get_site_by_api_key(x_site_key, db)
    
    stmt = select(Conversation).where(Conversation.id == ticket_id, Conversation.site_id == site.id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    messages_stmt = select(Message).where(Message.conversation_id == conv.id, Message.is_internal == False).order_by(Message.created_at)
    msgs = (await db.execute(messages_stmt)).scalars().all()

    return {
        "id": conv.id,
        "customer_name": conv.customer_name,
        "customer_email": conv.customer_email,
        "status": conv.status,
        "created_at": conv.created_at,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_name": m.sender_name,
                "content": m.content,
                "created_at": m.created_at
            } for m in msgs
        ]
    }

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Conversation, Message
from app.schemas import MessageCreate
from app.routers.chat import send_message

router = APIRouter(prefix="/portal", tags=["Customer Helpdesk Portal"])

@router.get("/tickets/{ticket_identifier}")
async def get_portal_ticket(
    ticket_identifier: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public ticket status page for customers by ticket number (e.g. HD-1001) or UUID.
    Hides internal notes for security and privacy.
    """
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            or_(
                Conversation.ticket_number == ticket_identifier.strip(),
                Conversation.id == ticket_identifier.strip()
            )
        )
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکتی با این مشخصات یافت نشد.")

    # Filter out internal notes
    public_messages = [
        {
            "id": m.id,
            "sender_type": m.sender_type,
            "sender_name": m.sender_name,
            "content": m.content,
            "created_at": str(m.created_at)
        }
        for m in conv.messages if not m.is_internal
    ]

    return {
        "id": conv.id,
        "ticket_number": conv.ticket_number,
        "subject": conv.subject,
        "customer_name": conv.customer_name,
        "status": conv.status,
        "priority": conv.priority,
        "assigned_agent": conv.assigned_agent_name or "تیم پشتیبانی",
        "created_at": str(conv.created_at),
        "last_message_at": str(conv.last_message_at),
        "messages": public_messages
    }

@router.post("/tickets/{ticket_identifier}/reply")
async def customer_reply_from_portal(
    ticket_identifier: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db)
):
    """Allows customer to reply directly from the web portal."""
    stmt = select(Conversation).where(
        or_(
            Conversation.ticket_number == ticket_identifier.strip(),
            Conversation.id == ticket_identifier.strip()
        )
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    payload.sender_type = "customer"
    payload.sender_name = conv.customer_name
    payload.is_internal = False

    return await send_message(conversation_id=conv.id, payload=payload, db=db)

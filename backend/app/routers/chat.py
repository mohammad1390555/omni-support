import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Conversation, Message, Site, AISettings, TypeSafeDecisionLog
from app.schemas import (
    ConversationCreate, ConversationResponse, ConversationUpdateStatus,
    MessageCreate, MessageResponse, LearnFromAgentRequest, KnowledgeItemResponse
)
from app.services.websocket_manager import ws_manager
from app.services.typesafe_ai import TypeSafeAIEngine
from app.services.learning_service import LearningService

router = APIRouter(prefix="/chat", tags=["Live Chat & Conversations"])

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    status: Optional[str] = None,
    site_id: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Conversation).options(selectinload(Conversation.messages)).order_by(desc(Conversation.last_message_at))
    
    if status and status != "all":
        stmt = stmt.where(Conversation.status == status)
    if site_id:
        stmt = stmt.where(Conversation.site_id == site_id)

    res = await db.execute(stmt)
    convs = res.scalars().all()

    if search and search.strip():
        q = search.strip().lower()
        convs = [c for c in convs if q in c.customer_name.lower() or (c.customer_email and q in c.customer_email.lower()) or q in c.id.lower()]

    return convs

@router.post("/conversations", response_model=ConversationResponse)
async def get_or_create_conversation(payload: ConversationCreate, db: AsyncSession = Depends(get_db)):
    """
    Called by widget or customer to initiate/resume a conversation.
    """
    # Check if existing active conversation exists for this customer_id
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.site_id == payload.site_id,
            Conversation.customer_id == payload.customer_id,
            Conversation.status.in_(["active", "pending_human"])
        )
        .order_by(desc(Conversation.last_message_at))
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        return existing

    # Verify site exists
    site_stmt = select(Site).where(Site.id == payload.site_id)
    site = (await db.execute(site_stmt)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="شناسه وب‌سایت نامعتبر است.")

    conv = Conversation(
        site_id=payload.site_id,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name or "کاربر مهمان",
        customer_email=payload.customer_email,
        customer_device=payload.customer_device,
        current_page=payload.current_page,
        status="active",
        ai_mode="auto"
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    # Add welcome message from site if configured
    if site.welcome_message:
        welcome_msg = Message(
            conversation_id=conv.id,
            sender_type="ai",
            sender_name="دستیار هوشمند",
            content=site.welcome_message,
            is_internal=False
        )
        db.add(welcome_msg)
        await db.commit()

    # Re-fetch with messages
    stmt = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conv.id)
    conv = (await db.execute(stmt)).scalars().first()

    # Broadcast new conversation to agents
    await ws_manager.broadcast_to_agents("new_conversation", {
        "id": conv.id,
        "site_id": conv.site_id,
        "customer_name": conv.customer_name,
        "status": conv.status,
        "created_at": str(conv.created_at)
    })

    return conv

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد.")
    return conv

@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdateStatus,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد.")

    if payload.status is not None:
        conv.status = payload.status
    if payload.ai_mode is not None:
        conv.ai_mode = payload.ai_mode
    if payload.assigned_agent is not None:
        conv.assigned_agent = payload.assigned_agent

    await db.commit()
    await db.refresh(conv)

    # Broadcast conversation status change
    await ws_manager.broadcast_to_agents("conversation_updated", {
        "id": conv.id,
        "status": conv.status,
        "ai_mode": conv.ai_mode,
        "assigned_agent": conv.assigned_agent
    })

    return conv

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد.")

    # 1. Create and save message
    sender_name = payload.sender_name or ("کاربر" if payload.sender_type == "customer" else "پشتیبان")
    msg = Message(
        conversation_id=conv.id,
        sender_type=payload.sender_type,
        sender_name=sender_name,
        content=payload.content.strip(),
        is_internal=payload.is_internal
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)

    # 2. Broadcast this message
    msg_dict = {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_type": msg.sender_type,
        "sender_name": msg.sender_name,
        "content": msg.content,
        "is_internal": msg.is_internal,
        "created_at": str(msg.created_at)
    }

    if payload.is_internal:
        # Only broadcast internal notes/drafts to agents
        await ws_manager.broadcast_to_agents("new_message", msg_dict)
    else:
        # Broadcast to both customer socket and agent workspace
        await ws_manager.send_to_conversation(conv.id, "new_message", msg_dict)

    # 3. If message is from customer and AI is active, run TypeSafe AI decision engine!
    if payload.sender_type == "customer" and conv.ai_mode != "human_only" and not payload.is_internal:
        # Fetch AI settings
        ai_stmt = select(AISettings).where(AISettings.id == 1)
        ai_settings = (await db.execute(ai_stmt)).scalars().first()
        if not ai_settings:
            ai_settings = AISettings(id=1)

        # Execute TypeSafe AI Decision
        decision = await TypeSafeAIEngine.evaluate_and_decide(
            db=db,
            conversation=conv,
            customer_message_text=payload.content,
            settings=ai_settings
        )

        decision_data = {
            "conversation_id": conv.id,
            "intent": decision.intent.value,
            "confidence": decision.confidence,
            "action": decision.selected_action.value,
            "reason": decision.reason,
            "suggested_reply": decision.suggested_reply,
            "evaluated_options": [opt.model_dump() for opt in decision.evaluated_options],
            "cited_knowledge_ids": decision.cited_knowledge_ids
        }
        await ws_manager.broadcast_to_agents("ai_decision", decision_data)

        # Handle Action
        if decision.selected_action.value == "AUTO_ANSWER" and conv.ai_mode == "auto":
            # Auto answer to customer
            ai_reply = Message(
                conversation_id=conv.id,
                sender_type="ai",
                sender_name=f"هوش مصنوعی ({ai_settings.provider_name})",
                content=decision.suggested_reply or "در حال بررسی پاسخ شما...",
                is_internal=False
            )
            db.add(ai_reply)
            conv.last_message_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(ai_reply)

            ai_reply_dict = {
                "id": ai_reply.id,
                "conversation_id": ai_reply.conversation_id,
                "sender_type": ai_reply.sender_type,
                "sender_name": ai_reply.sender_name,
                "content": ai_reply.content,
                "is_internal": False,
                "created_at": str(ai_reply.created_at)
            }
            await ws_manager.send_to_conversation(conv.id, "new_message", ai_reply_dict)

        elif decision.selected_action.value in ["SUGGEST_TO_AGENT"] or conv.ai_mode == "copilot":
            # Post internal AI suggestion for the agent
            if decision.suggested_reply:
                draft_msg = Message(
                    conversation_id=conv.id,
                    sender_type="ai",
                    sender_name="پیشنهاد هوش مصنوعی به پشتیبان (Co-pilot)",
                    content=decision.suggested_reply,
                    is_internal=True
                )
                db.add(draft_msg)
                conv.status = "pending_human"
                await db.commit()
                await db.refresh(draft_msg)

                await ws_manager.broadcast_to_agents("new_message", {
                    "id": draft_msg.id,
                    "conversation_id": draft_msg.conversation_id,
                    "sender_type": draft_msg.sender_type,
                    "sender_name": draft_msg.sender_name,
                    "content": draft_msg.content,
                    "is_internal": True,
                    "created_at": str(draft_msg.created_at)
                })

        elif decision.selected_action.value == "TRANSFER_TO_HUMAN":
            conv.status = "pending_human"
            await db.commit()

            # Send brief notice to customer
            transfer_notice = Message(
                conversation_id=conv.id,
                sender_type="system",
                sender_name="سیستم ارجاع",
                content=decision.suggested_reply or "مکالمه شما با اولویت بالا به پشتیبان انسانی ارجاع شد. لطفاً چند لحظه شکیبا باشید.",
                is_internal=False
            )
            db.add(transfer_notice)
            await db.commit()
            await db.refresh(transfer_notice)

            await ws_manager.send_to_conversation(conv.id, "new_message", {
                "id": transfer_notice.id,
                "conversation_id": transfer_notice.conversation_id,
                "sender_type": "system",
                "sender_name": "سیستم",
                "content": transfer_notice.content,
                "is_internal": False,
                "created_at": str(transfer_notice.created_at)
            })

    return msg

@router.post("/conversations/{conversation_id}/learn", response_model=KnowledgeItemResponse)
async def learn_from_agent(
    conversation_id: str,
    payload: LearnFromAgentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Explicitly saves an agent-crafted answer to AI memory/knowledge base.
    """
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد.")

    item = await LearningService.learn_from_agent_response(
        db=db,
        conversation_id=conversation_id,
        customer_question=payload.customer_question,
        agent_answer=payload.agent_answer,
        title=payload.title,
        category=payload.category,
        tags=payload.tags or "agent_learned",
        site_id=conv.site_id
    )

    # Broadcast notification to agents
    await ws_manager.broadcast_to_agents("ai_memory_updated", {
        "id": item.id,
        "title": item.title,
        "category": item.category,
        "message": "پاسخ جدید با موفقیت به حافظه هوش مصنوعی اضافه شد!"
    })

    return item

# --- WebSockets ---
@router.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    await ws_manager.connect_agent(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Can handle agent ping/typing events here
    except WebSocketDisconnect:
        ws_manager.disconnect_agent(websocket)

@router.websocket("/ws/chat/{conversation_id}")
async def websocket_customer_endpoint(websocket: WebSocket, conversation_id: str):
    await ws_manager.connect_customer(conversation_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Customer typing or ping
    except WebSocketDisconnect:
        ws_manager.disconnect_customer(conversation_id, websocket)

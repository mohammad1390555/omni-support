import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Conversation, Message, Site, AISettings, TypeSafeDecisionLog,
    TicketActivity, Attachment, Agent, SystemConfig
)
from app.schemas import (
    ConversationCreate, ConversationResponse,
    MessageCreate, MessageResponse, LearnFromAgentRequest, KnowledgeItemResponse,
    TicketAssignRequest, TicketStatusUpdateRequest, TicketPriorityUpdateRequest,
    TicketTagsUpdateRequest, InternalNoteCreate
)
from app.services.websocket_manager import ws_manager
from app.services.typesafe_ai import TypeSafeAIEngine
from app.services.learning_service import LearningService
from app.services.ai_service import AIService

router = APIRouter(prefix="/chat", tags=["Helpdesk Tickets & Live Chat"])

async def generate_ticket_number(db: AsyncSession) -> str:
    """Generates sequential ticket codes like HD-1001, HD-1002..."""
    cfg_stmt = select(SystemConfig).where(SystemConfig.id == 1)
    cfg = (await db.execute(cfg_stmt)).scalars().first()
    prefix = cfg.ticket_prefix if cfg and cfg.ticket_prefix else "HD"

    count_stmt = select(func.count(Conversation.id))
    count = (await db.execute(count_stmt)).scalar() or 0
    return f"{prefix}-{1001 + count}"

def detect_sentiment_and_priority(text: str) -> tuple[str, str]:
    """Analyzes customer tone to classify sentiment and auto-suggest priority."""
    t = text.lower()
    angry_keywords = ["شکایت", "ناراضی", "افتضاح", "پولم", "کلاهبرداری", "وکیل", "دادگاه", "پس بدید", "فوری"]
    positive_keywords = ["ممنون", "تشکر", "عالی", "دستتون درد نکنه", "فوق‌العاده", "مرسی", "خدا خیرتون بده"]

    if any(k in t for k in angry_keywords):
        return "frustrated", "urgent"
    elif any(k in t for k in positive_keywords):
        return "positive", "low"
    return "neutral", "medium"

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None, # 'unassigned', 'me', or agent_id
    tag: Optional[str] = None,
    site_id: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .order_by(desc(Conversation.last_message_at))
    )
    
    if status and status != "all":
        stmt = stmt.where(Conversation.status == status)
    if priority and priority != "all":
        stmt = stmt.where(Conversation.priority == priority)
    if assigned_to == "unassigned":
        stmt = stmt.where(Conversation.assigned_agent_id == None)
    elif assigned_to and assigned_to != "all":
        stmt = stmt.where(Conversation.assigned_agent_id == assigned_to)
    if site_id:
        stmt = stmt.where(Conversation.site_id == site_id)

    res = await db.execute(stmt)
    convs = res.scalars().all()

    if tag and tag.strip():
        q_tag = tag.strip().lower()
        convs = [c for c in convs if q_tag in (c.tags or "").lower()]

    if search and search.strip():
        q = search.strip().lower()
        convs = [
            c for c in convs if 
            q in c.ticket_number.lower() or 
            q in (c.subject or "").lower() or 
            q in c.customer_name.lower() or 
            (c.customer_email and q in c.customer_email.lower()) or
            (c.tags and q in c.tags.lower())
        ]

    return convs

@router.post("/conversations", response_model=ConversationResponse)
async def get_or_create_conversation(payload: ConversationCreate, db: AsyncSession = Depends(get_db)):
    """
    Called by widget or customer to initiate/resume a ticket or chat session.
    """
    # Check if existing open ticket exists for this customer_id on this site
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(
            Conversation.site_id == payload.site_id,
            Conversation.customer_id == payload.customer_id,
            Conversation.status.in_(["open", "in_progress", "pending_customer"])
        )
        .order_by(desc(Conversation.last_message_at))
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        return existing

    # Verify site
    site_stmt = select(Site).where(Site.id == payload.site_id)
    site = (await db.execute(site_stmt)).scalars().first()
    if not site:
        raise HTTPException(status_code=404, detail="شناسه وب‌سایت نامعتبر است.")

    # Generate sequential ticket number
    ticket_num = await generate_ticket_number(db)
    
    # Analyze sentiment & initial priority
    sentiment = "neutral"
    priority = payload.priority or "medium"
    if payload.initial_message:
        detected_sentiment, suggested_prio = detect_sentiment_and_priority(payload.initial_message)
        sentiment = detected_sentiment
        if suggested_prio == "urgent":
            priority = "urgent"

    conv = Conversation(
        ticket_number=ticket_num,
        subject=payload.subject or f"درخواست پشتیبانی #{ticket_num}",
        site_id=payload.site_id,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name or "کاربر مهمان",
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        customer_device=payload.customer_device,
        current_page=payload.current_page,
        status="open",
        priority=priority,
        sentiment=sentiment,
        tags="عمومی",
        ai_mode="auto",
        sla_due_at=datetime.now(timezone.utc) + timedelta(hours=8 if priority != "urgent" else 2)
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    # Activity Log
    activity = TicketActivity(
        conversation_id=conv.id,
        actor_type="customer",
        actor_name=conv.customer_name,
        action="created",
        details=f"تیکت با شماره {ticket_num} و اولویت '{priority}' توسط کاربر ایجاد شد."
    )
    db.add(activity)

    # Welcome message from widget if site has one
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

    # Re-fetch with relationships
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(Conversation.id == conv.id)
    )
    conv = (await db.execute(stmt)).scalars().first()

    # Broadcast new ticket
    await ws_manager.broadcast_to_agents("new_conversation", {
        "id": conv.id,
        "ticket_number": conv.ticket_number,
        "subject": conv.subject,
        "customer_name": conv.customer_name,
        "status": conv.status,
        "priority": conv.priority,
        "sentiment": conv.sentiment,
        "created_at": str(conv.created_at)
    })

    return conv

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(or_(Conversation.id == conversation_id, Conversation.ticket_number == conversation_id))
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")
    return conv

# --- Helpdesk Ticket Action Endpoints ---

@router.post("/conversations/{conversation_id}/assign", response_model=ConversationResponse)
async def assign_ticket_to_agent(
    conversation_id: str,
    payload: TicketAssignRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(Conversation.id == conversation_id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    # Find agent
    agent_stmt = select(Agent).where(Agent.id == payload.agent_id)
    agent = (await db.execute(agent_stmt)).scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="کارشناس یافت نشد.")

    conv.assigned_agent_id = agent.id
    conv.assigned_agent_name = agent.display_name
    if conv.status == "open":
        conv.status = "in_progress"

    # Activity log
    activity = TicketActivity(
        conversation_id=conv.id,
        actor_type="agent",
        actor_name="مدیر سیستم",
        action="assigned",
        details=f"تیکت به کارشناس '{agent.display_name}' واگذار شد."
    )
    db.add(activity)

    await db.commit()
    await db.refresh(conv)

    await ws_manager.broadcast_to_agents("ticket_updated", {
        "id": conv.id,
        "assigned_agent_id": conv.assigned_agent_id,
        "assigned_agent_name": conv.assigned_agent_name,
        "status": conv.status
    })

    return conv

@router.post("/conversations/{conversation_id}/status", response_model=ConversationResponse)
async def update_ticket_status(
    conversation_id: str,
    payload: TicketStatusUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(Conversation.id == conversation_id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    old_status = conv.status
    conv.status = payload.status

    activity = TicketActivity(
        conversation_id=conv.id,
        actor_type="agent",
        actor_name="پشتیبان",
        action="status_change",
        details=f"وضعیت تیکت از '{old_status}' به '{payload.status}' تغییر یافت."
    )
    db.add(activity)

    await db.commit()
    await db.refresh(conv)

    await ws_manager.broadcast_to_agents("ticket_updated", {
        "id": conv.id,
        "status": conv.status
    })

    return conv

@router.post("/conversations/{conversation_id}/priority", response_model=ConversationResponse)
async def update_ticket_priority(
    conversation_id: str,
    payload: TicketPriorityUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(Conversation.id == conversation_id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    old_prio = conv.priority
    conv.priority = payload.priority

    activity = TicketActivity(
        conversation_id=conv.id,
        actor_type="agent",
        actor_name="پشتیبان",
        action="priority_change",
        details=f"اولویت تیکت از '{old_prio}' به '{payload.priority}' تغییر کرد."
    )
    db.add(activity)

    await db.commit()
    await db.refresh(conv)

    return conv

@router.post("/conversations/{conversation_id}/tags", response_model=ConversationResponse)
async def update_ticket_tags(
    conversation_id: str,
    payload: TicketTagsUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(Conversation.id == conversation_id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    conv.tags = payload.tags
    await db.commit()
    await db.refresh(conv)
    return conv

@router.post("/conversations/{conversation_id}/notes", response_model=MessageResponse)
async def add_internal_note(
    conversation_id: str,
    payload: InternalNoteCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Adds a private internal note (Frappe-style) visible only to agents/admins.
    """
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    msg = Message(
        conversation_id=conv.id,
        sender_type="agent",
        sender_name="یادداشت خصوصی کارشناس",
        content=payload.content.strip(),
        is_internal=True
    )
    db.add(msg)

    activity = TicketActivity(
        conversation_id=conv.id,
        actor_type="agent",
        actor_name="کارشناس",
        action="note_added",
        details="یک یادداشت خصوصی داخلی روی تیکت ثبت شد."
    )
    db.add(activity)

    conv.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)

    # Broadcast only to agents!
    await ws_manager.broadcast_to_agents("new_message", {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_type": msg.sender_type,
        "sender_name": msg.sender_name,
        "content": msg.content,
        "is_internal": True,
        "created_at": str(msg.created_at)
    })

    return msg

@router.post("/conversations/{conversation_id}/ai-summarize")
async def ai_summarize_ticket(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    One-click AI executive summary of conversation thread (Frappe AI Helpdesk feature).
    """
    stmt = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    # Assemble messages
    thread_text = "\n".join([
        f"{'مشتری' if m.sender_type == 'customer' else 'پشتیبان/سیستم'}: {m.content}"
        for m in conv.messages if not m.is_internal
    ])

    ai_stmt = select(AISettings).where(AISettings.id == 1)
    ai_settings = (await db.execute(ai_stmt)).scalars().first()

    summary_text = ""
    if ai_settings and ai_settings.api_key and ai_settings.base_url:
        try:
            res = await AIService.chat_completion(
                base_url=ai_settings.base_url,
                api_key=ai_settings.api_key,
                model_name=ai_settings.model_name,
                messages=[
                    {"role": "system", "content": "شما خلاصه گر تیکت‌های پشتیبانی هستید. به صورت بسیار فشرده در ۲ الی ۳ جمله، مشکل اصلی مشتری و آخرین وضعیت گفتگو را به فارسی بنویسید."},
                    {"role": "user", "content": f"مکالمه:\n{thread_text}"}
                ],
                max_tokens=200
            )
            summary_text = res["content"].strip()
        except Exception:
            summary_text = f"مشتری '{conv.customer_name}' تیکتی با موضوع '{conv.subject}' ثبت کرده است. آخرین پیام: {conv.messages[-1].content if conv.messages else 'بدون پیام'}"
    else:
        # Heuristic summarizer
        last_m = conv.messages[-1].content if conv.messages else "درخواست ثبت شد"
        summary_text = f"خلاصه خودکار: کاربر '{conv.customer_name}' در خصوص '{conv.subject}' ارتباط برقرار کرده است. وضعیت فعلی: {conv.status} | پیام کلیدی: {last_m[:120]}"

    conv.ai_summary = summary_text
    await db.commit()

    return {"success": True, "summary": summary_text}

# --- Standard Chat & Live Messages ---

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.activities),
            selectinload(Conversation.attachments)
        )
        .where(Conversation.id == conversation_id)
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

    # Update first response time if agent responds
    if payload.sender_type == "agent" and not conv.first_response_at:
        conv.first_response_at = datetime.now(timezone.utc)

    # Auto detect sentiment on customer message
    if payload.sender_type == "customer":
        detected_sentiment, suggested_prio = detect_sentiment_and_priority(payload.content)
        conv.sentiment = detected_sentiment
        if suggested_prio == "urgent" and conv.priority != "urgent":
            conv.priority = "urgent"
            db.add(TicketActivity(
                conversation_id=conv.id,
                actor_type="ai",
                actor_name="موتور هوش مصنوعی",
                action="priority_change",
                details="اولویت تیکت بر اساس تحلیل احساس منفی/خشم مشتری به 'بحرانی' افزایش یافت."
            ))

    sender_name = payload.sender_name or ("کاربر" if payload.sender_type == "customer" else "کارشناس پشتیبانی")
    msg = Message(
        conversation_id=conv.id,
        sender_type=payload.sender_type,
        sender_name=sender_name,
        content=payload.content.strip(),
        is_internal=payload.is_internal
    )
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    
    if payload.sender_type == "agent" and not payload.is_internal:
        if conv.status in ["open", "pending_customer"]:
            conv.status = "in_progress"

    await db.commit()
    await db.refresh(msg)

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
        await ws_manager.broadcast_to_agents("new_message", msg_dict)
    else:
        await ws_manager.send_to_conversation(conv.id, "new_message", msg_dict)

    # Run TypeSafe AI Decision if message is from customer
    if payload.sender_type == "customer" and conv.ai_mode != "human_only" and not payload.is_internal:
        ai_stmt = select(AISettings).where(AISettings.id == 1)
        ai_settings = (await db.execute(ai_stmt)).scalars().first()
        if not ai_settings:
            ai_settings = AISettings(id=1)

        decision = await TypeSafeAIEngine.evaluate_and_decide(
            db=db,
            conversation=conv,
            customer_message_text=payload.content,
            settings=ai_settings
        )

        decision_data = {
            "conversation_id": conv.id,
            "ticket_number": conv.ticket_number,
            "intent": decision.intent.value,
            "confidence": decision.confidence,
            "action": decision.selected_action.value,
            "reason": decision.reason,
            "suggested_reply": decision.suggested_reply,
            "evaluated_options": [opt.model_dump() for opt in decision.evaluated_options],
            "cited_knowledge_ids": decision.cited_knowledge_ids
        }
        await ws_manager.broadcast_to_agents("ai_decision", decision_data)

        if decision.selected_action.value == "AUTO_ANSWER" and conv.ai_mode == "auto":
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

            await ws_manager.send_to_conversation(conv.id, "new_message", {
                "id": ai_reply.id,
                "conversation_id": ai_reply.conversation_id,
                "sender_type": ai_reply.sender_type,
                "sender_name": ai_reply.sender_name,
                "content": ai_reply.content,
                "is_internal": False,
                "created_at": str(ai_reply.created_at)
            })

        elif decision.selected_action.value == "SUGGEST_TO_AGENT" or conv.ai_mode == "copilot":
            if decision.suggested_reply:
                draft_msg = Message(
                    conversation_id=conv.id,
                    sender_type="ai",
                    sender_name="پیشنهاد هوش مصنوعی به پشتیبان (Co-pilot)",
                    content=decision.suggested_reply,
                    is_internal=True
                )
                db.add(draft_msg)
                conv.status = "open"
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
            conv.status = "open"
            conv.priority = "urgent"
            await db.commit()

            transfer_notice = Message(
                conversation_id=conv.id,
                sender_type="system",
                sender_name="سیستم ارجاع تیکت",
                content=decision.suggested_reply or "مکالمه شما با اولویت بالا به کارشناس پشتیبانی ارجاع گردید.",
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
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")

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

    db.add(TicketActivity(
        conversation_id=conv.id,
        actor_type="agent",
        actor_name="کارشناس",
        action="ai_learned",
        details="پاسخ این تیکت جهت استفاده در موارد مشابه به حافظه هوش مصنوعی اضافه شد."
    ))
    await db.commit()

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
    except WebSocketDisconnect:
        ws_manager.disconnect_agent(websocket)

@router.websocket("/ws/chat/{conversation_id}")
async def websocket_customer_endpoint(websocket: WebSocket, conversation_id: str):
    await ws_manager.connect_customer(conversation_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_customer(conversation_id, websocket)

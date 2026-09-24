from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Conversation, Message, TypeSafeDecisionLog, Agent, KnowledgeItem
from app.schemas import AnalyticsOverviewResponse

router = APIRouter(prefix="/analytics", tags=["Analytics & Reporting"])

@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(db: AsyncSession = Depends(get_db)):
    total_convs = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
    open_tickets = (await db.execute(select(func.count(Conversation.id)).where(Conversation.status == "open"))).scalar() or 0
    in_progress = (await db.execute(select(func.count(Conversation.id)).where(Conversation.status == "in_progress"))).scalar() or 0
    pending_cust = (await db.execute(select(func.count(Conversation.id)).where(Conversation.status == "pending_customer"))).scalar() or 0
    resolved_tickets = (await db.execute(select(func.count(Conversation.id)).where(Conversation.status == "resolved"))).scalar() or 0
    urgent_tickets = (await db.execute(select(func.count(Conversation.id)).where(Conversation.priority == "urgent"))).scalar() or 0
    
    total_msgs = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    total_agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
    total_kb = (await db.execute(select(func.count(KnowledgeItem.id)))).scalar() or 0

    decisions = (await db.execute(select(TypeSafeDecisionLog.action))).scalars().all()
    breakdown = {
        "AUTO_ANSWER": 0,
        "SUGGEST_TO_AGENT": 0,
        "TRANSFER_TO_HUMAN": 0,
        "CLARIFY": 0
    }
    for act in decisions:
        if act in breakdown:
            breakdown[act] += 1

    auto_count = breakdown["AUTO_ANSWER"]
    suggest_count = breakdown["SUGGEST_TO_AGENT"]
    transfer_count = breakdown["TRANSFER_TO_HUMAN"]
    clarify_count = breakdown["CLARIFY"]

    display_breakdown = {
        "AUTO_ANSWER": auto_count,
        "SUGGEST_TO_AGENT": suggest_count,
        "TRANSFER_TO_HUMAN": transfer_count,
        "CLARIFY": clarify_count
    }

    avg_latency = (await db.execute(select(func.avg(TypeSafeDecisionLog.latency_ms)))).scalar() or 0
    total_d = sum(display_breakdown.values())
    ai_resolved_pct = round((auto_count / total_d) * 100, 1) if total_d else 0.0

    return AnalyticsOverviewResponse(
        total_conversations=total_convs,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress,
        pending_customer_tickets=pending_cust,
        resolved_tickets=resolved_tickets,
        urgent_tickets=urgent_tickets,
        total_messages=total_msgs,
        ai_resolved_percent=ai_resolved_pct,
        avg_latency_ms=int(avg_latency),
        total_agents=total_agents,
        total_knowledge_items=total_kb,
        sla_compliance_percent=0.0,
        recent_decisions_breakdown=display_breakdown
    )

import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, Text, Boolean, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def default_sla_due() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=8)

class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, default=1)
    is_installed = Column(Boolean, default=False)
    company_name = Column(String(128), default="شرکت من")
    company_industry = Column(String(64), default="ecommerce") # ecommerce, saas, services, general
    ai_tone = Column(String(32), default="friendly") # formal, friendly, technical
    ticket_prefix = Column(String(16), default="HD") # e.g. HD-1001
    installed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Site(Base):
    __tablename__ = "sites"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    name = Column(String(128), nullable=False)
    domain = Column(String(256), default="*")
    api_key = Column(String(128), unique=True, nullable=False, default=gen_uuid)
    is_active = Column(Boolean, default=True)
    welcome_message = Column(Text, default="سلام! چطور می‌توانیم امروز به شما کمک کنیم؟")
    primary_color = Column(String(32), default="#4f46e5")
    widget_title = Column(String(128), default="پشتیبانی آنلاین")
    widget_position = Column(String(16), default="right")
    created_at = Column(DateTime, default=utc_now)

    conversations = relationship("Conversation", back_populates="site", cascade="all, delete-orphan")
    knowledge_items = relationship("KnowledgeItem", back_populates="site", cascade="all, delete-orphan")


class Conversation(Base):
    """
    Core Helpdesk Ticket & Live Chat entity (Frappe / Linear style)
    """
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    ticket_number = Column(String(32), unique=True, nullable=False, index=True) # e.g. HD-1001
    subject = Column(String(256), default="تیکت پشتیبانی جدید")
    site_id = Column(String(64), ForeignKey("sites.id"), nullable=False)
    
    # Customer Details
    customer_id = Column(String(128), nullable=False)
    customer_name = Column(String(128), default="کاربر مهمان")
    customer_email = Column(String(128), nullable=True)
    customer_phone = Column(String(64), nullable=True)
    customer_ip = Column(String(64), nullable=True)
    customer_device = Column(String(256), nullable=True)
    current_page = Column(String(512), nullable=True)
    
    # Status: 'open', 'in_progress', 'pending_customer', 'resolved', 'closed'
    status = Column(String(32), default="open", index=True)
    # Priority: 'low', 'medium', 'high', 'urgent'
    priority = Column(String(32), default="medium", index=True)
    
    # Assignment
    assigned_agent_id = Column(String(64), ForeignKey("agents.id"), nullable=True)
    assigned_agent_name = Column(String(128), nullable=True)
    
    # AI Mode: 'auto', 'copilot', 'human_only'
    ai_mode = Column(String(32), default="auto")
    
    # SLA Tracking
    sla_due_at = Column(DateTime, default=default_sla_due)
    first_response_at = Column(DateTime, nullable=True)
    
    # AI Intelligence Metadata
    tags = Column(String(256), default="عمومی") # e.g. billing, bug, urgent, refund
    sentiment = Column(String(32), default="neutral") # positive, neutral, frustrated, angry
    ai_summary = Column(Text, nullable=True)
    
    last_message_at = Column(DateTime, default=utc_now, index=True)
    created_at = Column(DateTime, default=utc_now)

    site = relationship("Site", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    decisions = relationship("TypeSafeDecisionLog", back_populates="conversation", cascade="all, delete-orphan", order_by="TypeSafeDecisionLog.created_at.desc()")
    activities = relationship("TicketActivity", back_populates="conversation", cascade="all, delete-orphan", order_by="TicketActivity.created_at.desc()")
    attachments = relationship("Attachment", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    # sender_type: 'customer', 'ai', 'agent', 'system'
    sender_type = Column(String(32), nullable=False)
    sender_name = Column(String(128), default="سیستم")
    content = Column(Text, nullable=False)
    # is_internal: True for private agent notes (Frappe internal notes)
    is_internal = Column(Boolean, default=False)
    decision_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")


class TicketActivity(Base):
    """
    Timeline audit trail of ticket events (who changed status, assigned, added internal note)
    """
    __tablename__ = "ticket_activities"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    actor_type = Column(String(32), default="system") # agent, ai, customer, system
    actor_name = Column(String(128), default="سیستم")
    action = Column(String(64), nullable=False) # status_change, priority_change, assigned, note_added, ai_summarized
    details = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("Conversation", back_populates="activities")


class Attachment(Base):
    """
    File attachments on tickets (images, screenshots, logs, documents)
    """
    __tablename__ = "ticket_attachments"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    message_id = Column(String(64), nullable=True)
    file_name = Column(String(256), nullable=False)
    file_size_kb = Column(Integer, default=0)
    file_url = Column(String(512), nullable=False)
    content_type = Column(String(64), default="application/octet-stream")
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("Conversation", back_populates="attachments")


class TypeSafeDecisionLog(Base):
    __tablename__ = "typesafe_decisions"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    customer_message = Column(Text, nullable=False)
    
    intent = Column(String(64), default="unknown")
    confidence = Column(Float, default=0.0)
    action = Column(String(64), nullable=False)
    reason = Column(Text, nullable=True)
    options_evaluated_json = Column(Text, default="[]")
    suggested_reply = Column(Text, nullable=True)
    retrieved_knowledge_json = Column(Text, default="[]")
    
    model_used = Column(String(128), default="")
    provider = Column(String(64), default="")
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("Conversation", back_populates="decisions")


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    site_id = Column(String(64), ForeignKey("sites.id"), nullable=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(64), default="agent_learned")
    source = Column(String(64), default="agent_learned")
    source_conversation_id = Column(String(64), nullable=True)
    is_approved = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    tags = Column(String(256), default="")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    site = relationship("Site", back_populates="knowledge_items")


class AISettings(Base):
    __tablename__ = "ai_settings"

    id = Column(Integer, primary_key=True, default=1)
    provider_name = Column(String(64), default="OpenAI Compatible")
    base_url = Column(String(512), default="https://api.openai.com/v1")
    api_key = Column(String(512), default="")
    model_name = Column(String(128), default="gpt-4o-mini")
    temperature = Column(Float, default=0.2)
    max_tokens = Column(Integer, default=1000)
    
    auto_answer_threshold = Column(Float, default=0.75)
    enable_typesafe_decision = Column(Boolean, default=True)
    enable_agent_learning = Column(Boolean, default=True)
    auto_handoff_on_complaint = Column(Boolean, default=True)
    
    system_prompt = Column(Text, default=(
        "شما پشتیبان هوشمند و بسیار مودب و حرفه‌ای پلتفرم هستید. "
        "وظیفه شما راهنمایی دقیق کاربران بر اساس دانش موجود و تاریخچه پاسخ‌های تیم پشتیبانی است. "
        "همواره با لحنی محترمانه، شیوا و به زبان فارسی پاسخ دهید. "
        "اگر اطلاعات کافی برای پاسخ قطعی ندارید، صادقانه اعلام کنید و بگویید که مکالمه را به همکاران پشتیبان انسانی ارجاع می‌دهید."
    ))
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(128), default="")
    display_name = Column(String(128), nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="agent") # 'admin' or 'agent'
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=True)
    avatar = Column(String(256), default="")
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class CannedResponse(Base):
    __tablename__ = "canned_responses"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    title = Column(String(128), nullable=False)
    shortcut = Column(String(64), nullable=True) # e.g. /hello, /hours
    content = Column(Text, nullable=False)
    category = Column(String(64), default="general")
    created_at = Column(DateTime, default=utc_now)


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    name = Column(String(128), nullable=False)
    trigger_event = Column(String(64), default="ticket_created") # ticket_created, sentiment_angry, sla_breached
    condition_key = Column(String(64), default="priority")
    condition_value = Column(String(128), default="urgent")
    action_type = Column(String(64), default="assign_agent") # assign_agent, set_priority, send_canned
    action_value = Column(String(128), default="admin")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

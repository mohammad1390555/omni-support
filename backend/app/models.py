import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, default=1)
    is_installed = Column(Boolean, default=False)
    company_name = Column(String(128), default="شرکت من")
    company_industry = Column(String(64), default="ecommerce") # ecommerce, saas, services, general
    ai_tone = Column(String(32), default="friendly") # formal, friendly, technical
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
    widget_position = Column(String(16), default="right") # right or left
    created_at = Column(DateTime, default=utc_now)

    conversations = relationship("Conversation", back_populates="site", cascade="all, delete-orphan")
    knowledge_items = relationship("KnowledgeItem", back_populates="site", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    site_id = Column(String(64), ForeignKey("sites.id"), nullable=False)
    customer_id = Column(String(128), nullable=False)
    customer_name = Column(String(128), default="کاربر مهمان")
    customer_email = Column(String(128), nullable=True)
    customer_ip = Column(String(64), nullable=True)
    customer_device = Column(String(256), nullable=True)
    current_page = Column(String(512), nullable=True)
    
    # Status: 'active', 'pending_human', 'resolved', 'closed'
    status = Column(String(32), default="active")
    # AI Mode: 'auto', 'copilot', 'human_only'
    ai_mode = Column(String(32), default="auto")
    assigned_agent = Column(String(128), nullable=True)
    
    last_message_at = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)

    site = relationship("Site", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    decisions = relationship("TypeSafeDecisionLog", back_populates="conversation", cascade="all, delete-orphan", order_by="TypeSafeDecisionLog.created_at.desc()")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False)
    # sender_type: 'customer', 'ai', 'agent', 'system'
    sender_type = Column(String(32), nullable=False)
    sender_name = Column(String(128), default="سیستم")
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)
    decision_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    conversation = relationship("Conversation", back_populates="messages")


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

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ActionType(str, Enum):
    AUTO_ANSWER = "AUTO_ANSWER"
    SUGGEST_TO_AGENT = "SUGGEST_TO_AGENT"
    TRANSFER_TO_HUMAN = "TRANSFER_TO_HUMAN"
    CLARIFY = "CLARIFY"

class IntentType(str, Enum):
    FAQ = "faq"
    TECHNICAL_SUPPORT = "technical_support"
    BILLING_SALES = "billing_sales"
    COMPLAINT = "complaint"
    HUMAN_REQUEST = "human_request"
    GREETING = "greeting"
    OTHER = "other"

class OptionEvaluation(BaseModel):
    action: ActionType
    score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str

class TypeSafeDecisionResult(BaseModel):
    intent: IntentType = IntentType.OTHER
    confidence: float = Field(..., ge=0.0, le=1.0)
    selected_action: ActionType = ActionType.AUTO_ANSWER
    reason: str
    evaluated_options: List[OptionEvaluation] = []
    suggested_reply: Optional[str] = None
    cited_knowledge_ids: List[str] = []

# --- System & Installer Schemas ---
class SystemStatusResponse(BaseModel):
    is_installed: bool
    company_name: str
    company_industry: str
    ai_tone: str
    ticket_prefix: str
    installed_at: Optional[datetime] = None
    agents_count: int = 0

class InstallerRequest(BaseModel):
    company_name: str
    company_industry: str = "ecommerce"
    ai_tone: str = "friendly"
    ticket_prefix: Optional[str] = "HD"
    
    # Admin Credentials
    admin_username: str
    admin_email: str
    admin_display_name: str
    admin_password: str
    
    # AI Settings
    ai_provider: Optional[str] = "OpenAI Compatible"
    ai_base_url: Optional[str] = "https://api.openai.com/v1"
    ai_api_key: Optional[str] = ""
    ai_model_name: Optional[str] = "gpt-4o-mini"
    
    # Widget Branding
    widget_title: Optional[str] = "پشتیبانی آنلاین"
    primary_color: Optional[str] = "#4f46e5"
    welcome_message: Optional[str] = "سلام! چطور می‌توانیم امروز به شما کمک کنیم؟"
    
    # Knowledge Seed
    seed_kb_preset: Optional[str] = "ecommerce"

# --- Auth & User Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class UserCreate(BaseModel):
    username: str
    display_name: str
    email: Optional[str] = ""
    password: str
    role: str = "agent"

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    role: str
    is_active: bool
    is_online: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- AI Settings Schemas ---
class AISettingsBase(BaseModel):
    provider_name: str = "OpenAI Compatible"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 1000
    auto_answer_threshold: float = 0.75
    enable_typesafe_decision: bool = True
    enable_agent_learning: bool = True
    auto_handoff_on_complaint: bool = True
    system_prompt: str

class AISettingsUpdate(BaseModel):
    provider_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    auto_answer_threshold: Optional[float] = None
    enable_typesafe_decision: Optional[bool] = None
    enable_agent_learning: Optional[bool] = None
    auto_handoff_on_complaint: Optional[bool] = None
    system_prompt: Optional[str] = None

class AISettingsResponse(AISettingsBase):
    id: int
    updated_at: datetime
    masked_api_key: Optional[str] = None

    class Config:
        from_attributes = True

class ProviderTestRequest(BaseModel):
    base_url: str
    api_key: str
    model_name: str
    provider_name: Optional[str] = "Custom"

class ProviderTestResponse(BaseModel):
    success: bool
    latency_ms: int
    message: str
    sample_response: Optional[str] = None

# --- Message & Attachment Schemas ---
class MessageCreate(BaseModel):
    content: str
    sender_type: str = "customer"
    sender_name: Optional[str] = None
    is_internal: bool = False

class AttachmentResponse(BaseModel):
    id: str
    conversation_id: str
    message_id: Optional[str]
    file_name: str
    file_size_kb: int
    file_url: str
    created_at: datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_type: str
    sender_name: str
    content: str
    is_internal: bool
    decision_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TicketActivityResponse(BaseModel):
    id: str
    conversation_id: str
    actor_type: str
    actor_name: str
    action: str
    details: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Helpdesk Ticket Schemas ---
class ConversationCreate(BaseModel):
    site_id: str
    customer_id: str
    customer_name: Optional[str] = "کاربر مهمان"
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_device: Optional[str] = None
    current_page: Optional[str] = None
    subject: Optional[str] = "درخواست پشتیبانی جدید"
    priority: Optional[str] = "medium" # low, medium, high, urgent
    initial_message: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    ticket_number: str
    subject: str
    site_id: str
    customer_id: str
    customer_name: str
    customer_email: Optional[str]
    customer_phone: Optional[str]
    customer_ip: Optional[str]
    customer_device: Optional[str]
    current_page: Optional[str]
    status: str # open, in_progress, pending_customer, resolved, closed
    priority: str # low, medium, high, urgent
    assigned_agent_id: Optional[str]
    assigned_agent_name: Optional[str]
    ai_mode: str
    tags: str
    sentiment: str
    ai_summary: Optional[str]
    sla_due_at: Optional[datetime]
    first_response_at: Optional[datetime]
    last_message_at: datetime
    created_at: datetime
    messages: List[MessageResponse] = []
    activities: List[TicketActivityResponse] = []
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True

class TicketAssignRequest(BaseModel):
    agent_id: str

class TicketStatusUpdateRequest(BaseModel):
    status: str

class TicketPriorityUpdateRequest(BaseModel):
    priority: str

class TicketTagsUpdateRequest(BaseModel):
    tags: str

class InternalNoteCreate(BaseModel):
    content: str

# --- Knowledge & Learning Schemas ---
class KnowledgeItemCreate(BaseModel):
    title: str
    content: str
    category: str = "faq"
    source: str = "manual"
    site_id: Optional[str] = None
    tags: Optional[str] = ""
    is_approved: bool = True

class KnowledgeItemUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    is_approved: Optional[bool] = None
    tags: Optional[str] = None

class KnowledgeItemResponse(BaseModel):
    id: str
    site_id: Optional[str]
    title: str
    content: str
    category: str
    source: str
    source_conversation_id: Optional[str]
    is_approved: bool
    usage_count: int
    tags: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class LearnFromAgentRequest(BaseModel):
    conversation_id: str
    customer_question: str
    agent_answer: str
    title: Optional[str] = None
    category: str = "agent_learned"
    tags: Optional[str] = "agent_response"

# --- Site Schemas ---
class SiteCreate(BaseModel):
    name: str
    domain: str = "*"
    welcome_message: Optional[str] = "سلام! چطور می‌توانیم امروز به شما کمک کنیم؟"
    primary_color: Optional[str] = "#4f46e5"
    widget_title: Optional[str] = "پشتیبانی آنلاین"
    widget_position: Optional[str] = "right"

class SiteResponse(BaseModel):
    id: str
    name: str
    domain: str
    api_key: str
    is_active: bool
    welcome_message: str
    primary_color: str
    widget_title: str
    widget_position: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- External API Schemas ---
class ExternalMessageRequest(BaseModel):
    site_id: str
    customer_id: str
    customer_name: Optional[str] = "کاربر وب‌سایت"
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    subject: Optional[str] = "درخواست پشتیبانی وب‌سایت"
    priority: Optional[str] = "medium"
    message: str
    current_page: Optional[str] = None

# --- Canned Responses ---
class CannedResponseCreate(BaseModel):
    title: str
    shortcut: Optional[str] = ""
    content: str
    category: Optional[str] = "general"

class CannedResponseOut(BaseModel):
    id: str
    title: str
    shortcut: Optional[str]
    content: str
    category: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Analytics Overview ---
class AnalyticsOverviewResponse(BaseModel):
    total_conversations: int
    open_tickets: int
    in_progress_tickets: int
    pending_customer_tickets: int
    resolved_tickets: int
    urgent_tickets: int
    total_messages: int
    ai_resolved_percent: float
    avg_latency_ms: int
    total_agents: int
    total_knowledge_items: int
    sla_compliance_percent: float
    recent_decisions_breakdown: Dict[str, int]

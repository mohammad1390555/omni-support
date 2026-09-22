from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.database import get_db
from app.models import AISettings, TypeSafeDecisionLog
from app.schemas import (
    AISettingsResponse, AISettingsUpdate,
    ProviderTestRequest, ProviderTestResponse
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI & Decision Engine"])

# Popular pre-configured providers for 1-click setup
PROVIDER_PRESETS = [
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "popular_models": ["gpt-4o", "gpt-4o-mini", "o3-mini", "gpt-4-turbo"],
        "description": "سریع‌ترین و پایدارترین مدل‌های تجاری OpenAI"
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "popular_models": ["deepseek-chat", "deepseek-reasoner"],
        "description": "مدل قدرتمند و بسیار مقرون‌به‌صرفه با درک فوق‌العاده فارسی"
    },
    {
        "id": "groq",
        "name": "Groq (Ultra-Fast)",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "popular_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        "description": "سریع‌ترین پردازش هوش مصنوعی با سخت‌افزار LPU و تاخیر زیر ۵۰۰ میلی‌ثانیه"
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (All-in-One)",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "popular_models": [
            "meta-llama/llama-3.3-70b-instruct",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
            "deepseek/deepseek-chat"
        ],
        "description": "دسترسی به تمامی مدل‌های جهان (Claude, Gemini, LLaMA, DeepSeek) با یک کلید"
    },
    {
        "id": "ollama",
        "name": "Ollama / Local LLM",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "popular_models": ["llama3.2", "qwen2.5:7b", "mistral", "deepseek-r1:7b"],
        "description": "اجرای مدل‌های هوش مصنوعی کاملاً آفلاین و محلی بر روی سرور خودتان بدون نیاز به اینترنت"
    },
    {
        "id": "custom",
        "name": "Custom / vLLM / LiteLLM",
        "base_url": "https://your-custom-ai-proxy.com/v1",
        "default_model": "custom-model",
        "popular_models": ["custom-model"],
        "description": "هر سرور شخصی یا پروکسی سازگار با پروتکل استاندارد OpenAI"
    }
]

async def get_or_create_ai_settings(db: AsyncSession) -> AISettings:
    stmt = select(AISettings).where(AISettings.id == 1)
    res = await db.execute(stmt)
    settings = res.scalars().first()
    if not settings:
        settings = AISettings(id=1)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings

@router.get("/presets")
async def get_provider_presets():
    """Returns list of popular AI provider presets."""
    return PROVIDER_PRESETS

@router.get("/settings", response_model=AISettingsResponse)
async def get_ai_settings(db: AsyncSession = Depends(get_db)):
    """Fetches the active AI and TypeSafe configuration."""
    settings = await get_or_create_ai_settings(db)
    
    # Mask API key for response
    masked_key = ""
    if settings.api_key:
        if len(settings.api_key) > 8:
            masked_key = settings.api_key[:4] + "••••••••" + settings.api_key[-4:]
        else:
            masked_key = "••••••••"

    resp = AISettingsResponse.model_validate(settings)
    resp.masked_api_key = masked_key
    return resp

@router.put("/settings", response_model=AISettingsResponse)
async def update_ai_settings(payload: AISettingsUpdate, db: AsyncSession = Depends(get_db)):
    """Updates AI provider credentials, Base URL, thresholds, and prompts."""
    settings = await get_or_create_ai_settings(db)
    
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if field == "api_key" and (val is None or val.strip() == ""):
            # Don't overwrite with empty if sent as empty string unless intended
            continue
        setattr(settings, field, val)

    await db.commit()
    await db.refresh(settings)
    
    masked_key = ""
    if settings.api_key:
        if len(settings.api_key) > 8:
            masked_key = settings.api_key[:4] + "••••••••" + settings.api_key[-4:]
        else:
            masked_key = "••••••••"

    resp = AISettingsResponse.model_validate(settings)
    resp.masked_api_key = masked_key
    return resp

@router.post("/test-connection", response_model=ProviderTestResponse)
async def test_ai_connection(payload: ProviderTestRequest, db: AsyncSession = Depends(get_db)):
    """Tests live connection to the specified Base URL & API Key."""
    # If api_key in payload is masked (contains bullets), use existing stored key
    test_key = payload.api_key
    if "••" in test_key:
        curr_settings = await get_or_create_ai_settings(db)
        test_key = curr_settings.api_key

    result = await AIService.test_connection(
        base_url=payload.base_url,
        api_key=test_key,
        model_name=payload.model_name,
        provider_name=payload.provider_name or "Custom"
    )
    return ProviderTestResponse(**result)

@router.get("/decisions")
async def get_recent_decisions(limit: int = 30, db: AsyncSession = Depends(get_db)):
    """Retrieves recent TypeSafe AI decisions for audit and inspection."""
    stmt = select(TypeSafeDecisionLog).order_by(desc(TypeSafeDecisionLog.created_at)).limit(limit)
    res = await db.execute(stmt)
    decisions = res.scalars().all()
    return decisions

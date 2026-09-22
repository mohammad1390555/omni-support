from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import SystemConfig, Agent, Site, AISettings, KnowledgeItem
from app.schemas import SystemStatusResponse, InstallerRequest, LoginResponse
from app.core.security import hash_password, create_access_token
from app.config import settings

router = APIRouter(prefix="/installer", tags=["Web Setup Wizard & Installer"])

async def get_or_create_config(db: AsyncSession) -> SystemConfig:
    stmt = select(SystemConfig).where(SystemConfig.id == 1)
    cfg = (await db.execute(stmt)).scalars().first()
    if not cfg:
        cfg = SystemConfig(id=1, is_installed=False)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg

@router.get("/status", response_model=SystemStatusResponse)
async def check_installer_status(db: AsyncSession = Depends(get_db)):
    cfg = await get_or_create_config(db)
    agents_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0

    return SystemStatusResponse(
        is_installed=cfg.is_installed,
        company_name=cfg.company_name or "سامانه پشتیبانی",
        company_industry=cfg.company_industry or "ecommerce",
        ai_tone=cfg.ai_tone or "friendly",
        installed_at=cfg.installed_at,
        agents_count=agents_count
    )

@router.post("/install", response_model=LoginResponse)
async def run_installer(payload: InstallerRequest, db: AsyncSession = Depends(get_db)):
    cfg = await get_or_create_config(db)
    
    # Check if already installed
    if cfg.is_installed:
        raise HTTPException(status_code=400, detail="سامانه قبلاً با موفقیت نصب و راه‌اندازی شده است.")

    # 1. Create / Update Admin Account
    stmt = select(Agent).where(Agent.username == payload.admin_username.strip())
    admin_user = (await db.execute(stmt)).scalars().first()
    if not admin_user:
        admin_user = Agent(
            username=payload.admin_username.strip(),
            display_name=payload.admin_display_name.strip(),
            email=payload.admin_email.strip(),
            password_hash=hash_password(payload.admin_password),
            role="admin",
            is_active=True,
            is_online=True,
            last_login=datetime.now(timezone.utc)
        )
        db.add(admin_user)
    else:
        admin_user.password_hash = hash_password(payload.admin_password)
        admin_user.display_name = payload.admin_display_name
        admin_user.email = payload.admin_email
        admin_user.role = "admin"
        admin_user.last_login = datetime.now(timezone.utc)

    # 2. Setup System Prompt based on Onboarding Questions
    tone_desc = "صمیمی، گرم، همدلانه و در عین حال کاملاً محترمانه"
    if payload.ai_tone == "formal":
        tone_desc = "بسیار رسمی، اداری، سازمانی و موقر"
    elif payload.ai_tone == "technical":
        tone_desc = "تخصصی، دقیق، مستند و تحلیلی با ارجاع به مراحل گام‌به‌گام"

    custom_prompt = (
        f"شما دستیار هوش مصنوعی رسمی مرکز پشتیبانی '{payload.company_name}' هستید. "
        f"حوزه فعالیت مجموعه ما: {payload.company_industry}. "
        f"لحن پاسخگویی شما باید {tone_desc} باشد. "
        "همواره به زبان فارسی سلیس پاسخ دهید. از پایگاه دانش و سوابق پاسخ‌های همکاران پشتیبان انسانی برای پاسخ‌گویی دقیق استفاده کنید. "
        "در صورتی که اطلاعات قطعی برای پاسخ ندارید یا مشتری ناراضی است، صادقانه اعلام کنید که گفتگو را به پشتیبانان انسانی ارجاع می‌دهید."
    )

    # 3. Configure AI Settings
    ai_stmt = select(AISettings).where(AISettings.id == 1)
    ai_settings = (await db.execute(ai_stmt)).scalars().first()
    if not ai_settings:
        ai_settings = AISettings(id=1)
        db.add(ai_settings)
    
    ai_settings.provider_name = payload.ai_provider or "OpenAI Compatible"
    ai_settings.base_url = payload.ai_base_url or "https://api.openai.com/v1"
    if payload.ai_api_key:
        ai_settings.api_key = payload.ai_api_key
    ai_settings.model_name = payload.ai_model_name or "gpt-4o-mini"
    ai_settings.system_prompt = custom_prompt

    # 4. Setup Default Site & Widget Theme
    site_stmt = select(Site).where(Site.id == "site_default")
    site = (await db.execute(site_stmt)).scalars().first()
    if not site:
        site = Site(
            id="site_default",
            name=payload.company_name,
            welcome_message=payload.welcome_message or "سلام! چطور می‌توانیم امروز به شما کمک کنیم؟",
            primary_color=payload.primary_color or "#4f46e5",
            widget_title=payload.widget_title or "پشتیبانی آنلاین"
        )
        db.add(site)
    else:
        site.name = payload.company_name
        site.welcome_message = payload.welcome_message
        site.primary_color = payload.primary_color
        site.widget_title = payload.widget_title

    # 5. Seed Knowledge Base by Industry
    industry_preset = payload.seed_kb_preset or payload.company_industry
    sample_kb = []
    if industry_preset == "ecommerce":
        sample_kb = [
            KnowledgeItem(
                site_id="site_default",
                title="نحوه پیگیری سفارش‌های پستی و کد رهگیری",
                content="پس از ثبت سفارش، کد رهگیری ۲۴ رقمی پستی از طریق پیامک برای شما ارسال می‌شود. با وارد کردن این کد در سامانه tracking.post.ir می‌توانید موقعیت مرسوله را مشاهده کنید.",
                category="faq",
                source="manual",
                tags="پیگیری سفارش, کد مرسوله, پست, ارسال"
            ),
            KnowledgeItem(
                site_id="site_default",
                title="شرایط و قوانین بازگشت وجه (Refund Policy)",
                content="در صورت هرگونه مغایرت یا آسیب‌دیدگی کالا، تا ۷ روز کاری مهلت بازگرداندن محصول وجود دارد. مبلغ پرداختی ظرف ۲۴ الی ۴۸ ساعت به شماره شبا یا کارت مبدا واریز خواهد شد.",
                category="policy",
                source="manual",
                tags="بازگشت وجه, استرداد, مرجوعی, ضمانت"
            ),
            KnowledgeItem(
                site_id="site_default",
                title="درخواست صدور فاکتور رسمی شرکتی",
                content="برای دریافت فاکتور رسمی دارای شناسه ملی و کد اقتصادی، کافیست پس از پرداخت سفارش، شماره سفارش و مشخصات ثبتی شرکت خود را در تیکت پشتیبانی ارسال فرمایید.",
                category="agent_learned",
                source="agent_learned",
                tags="فاکتور رسمی, شناسه ملی, کد اقتصادی"
            )
        ]
    elif industry_preset == "saas":
        sample_kb = [
            KnowledgeItem(
                site_id="site_default",
                title="نحوه ارتقای پلن و تمدید اشتراک سرویس",
                content="از منوی حساب کاربری > بخش اشتراک‌ها می‌توانید پلن مورد نظر خود را انتخاب و با درگاه شتاب یا ارز دیجیتال تمدید یا ارتقا دهید. ارتقا به صورت آنی اعمال می‌شود.",
                category="faq",
                source="manual",
                tags="ارتقای پلن, تمدید اشتراک, پرداخت"
            ),
            KnowledgeItem(
                site_id="site_default",
                title="محدودیت نرخ و کلیدهای دسترسی API (Rate Limit)",
                content="هر کلید API استاندارد قابلیت ارسال حداکثر ۶۰ درخواست در دقیقه را دارد. در صورت نیاز به پلن سازمانی اختصاصی، با پشتیبانی فنی مکاتبه فرمایید.",
                category="technical",
                source="manual",
                tags="API, Rate limit, کلید دسترسی"
            )
        ]
    else:
        sample_kb = [
            KnowledgeItem(
                site_id="site_default",
                title="ساعات کاری و پاسخگویی تیم پشتیبانی",
                content="پشتیبانی هوش مصنوعی به صورت ۲۴ ساعته در تمام روزهای هفته فعال است. کارشناسان انسانی نیز همه‌روزه از ساعت ۸:۰۰ الی ۲۲:۰۰ آماده خدمت‌رسانی به شما هستند.",
                category="faq",
                source="manual",
                tags="ساعت کاری, تایم, زمان پاسخگویی"
            )
        ]

    db.add_all(sample_kb)

    # 6. Mark System as Installed
    cfg.is_installed = True
    cfg.company_name = payload.company_name
    cfg.company_industry = payload.company_industry
    cfg.ai_tone = payload.ai_tone
    cfg.installed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(admin_user)

    # Issue Auth Token for instant login
    token = create_access_token(
        data={"sub": admin_user.id, "username": admin_user.username, "role": admin_user.role},
        secret_key=settings.SECRET_KEY
    )

    return LoginResponse(
        success=True,
        access_token=token,
        user={
            "id": admin_user.id,
            "username": admin_user.username,
            "display_name": admin_user.display_name,
            "email": admin_user.email,
            "role": admin_user.role
        }
    )

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.models import Site, AISettings, KnowledgeItem, Agent, SystemConfig, CannedResponse
from app.core.security import hash_password
from app.routers.ai_router import router as ai_router
from app.routers.chat import router as chat_router
from app.routers.knowledge import router as knowledge_router
from app.routers.sites import router as sites_router
from app.routers.external_api import router as external_router
from app.routers.auth import router as auth_router
from app.routers.installer import router as installer_router
from app.routers.analytics import router as analytics_router
from app.routers.canned import router as canned_router

async def seed_initial_data():
    """Seeds default site, settings, and rich sample knowledge items."""
    async with AsyncSessionLocal() as session:
        # 1. System Config
        cfg_stmt = select(SystemConfig).where(SystemConfig.id == 1)
        cfg = (await session.execute(cfg_stmt)).scalars().first()
        if not cfg:
            cfg = SystemConfig(
                id=1,
                is_installed=True, # Default installed so preview works immediately; can be re-run in /install
                company_name="مرکز پشتیبانی هوشمند آران",
                company_industry="ecommerce",
                ai_tone="friendly"
            )
            session.add(cfg)

        # 2. Default Site
        site_stmt = select(Site).where(Site.id == "site_default")
        default_site = (await session.execute(site_stmt)).scalars().first()
        if not default_site:
            default_site = Site(
                id="site_default",
                name="فروشگاه آنلاین آران",
                domain="*",
                api_key="omni_live_k8s92f8a129d38c71e041",
                welcome_message="سلام و درود! به پشتیبانی هوشمند آران خوش آمدید. چطور می‌توانیم شما را راهنمایی کنیم؟",
                primary_color="#4f46e5",
                widget_title="پشتیبانی آنلاین آران",
                widget_position="right"
            )
            session.add(default_site)

        # 3. AI Settings
        ai_stmt = select(AISettings).where(AISettings.id == 1)
        ai_set = (await session.execute(ai_stmt)).scalars().first()
        if not ai_set:
            ai_set = AISettings(
                id=1,
                provider_name="OpenAI Compatible",
                base_url="https://api.openai.com/v1",
                api_key="",
                model_name="gpt-4o-mini",
                temperature=0.2,
                auto_answer_threshold=0.75,
                enable_typesafe_decision=True,
                enable_agent_learning=True,
                auto_handoff_on_complaint=True
            )
            session.add(ai_set)

        # 4. Default Admin & Member Agents
        admin_stmt = select(Agent).where(Agent.username == "admin")
        admin = (await session.execute(admin_stmt)).scalars().first()
        if not admin:
            admin = Agent(
                username="admin",
                display_name="مدیر ارشد سیستم (Admin)",
                email="admin@omni-support.local",
                password_hash=hash_password("admin123"),
                role="admin",
                is_active=True,
                is_online=True
            )
            session.add(admin)

        agent_stmt = select(Agent).where(Agent.username == "agent1")
        agent1 = (await session.execute(agent_stmt)).scalars().first()
        if not agent1:
            agent1 = Agent(
                username="agent1",
                display_name="سارا حسینی (پشتیبان فنی)",
                email="sara@omni-support.local",
                password_hash=hash_password("agent123"),
                role="agent",
                is_active=True,
                is_online=True
            )
            session.add(agent1)

        # 5. Canned Responses
        canned_stmt = select(CannedResponse).limit(1)
        has_canned = (await session.execute(canned_stmt)).scalars().first()
        if not has_canned:
            canned_samples = [
                CannedResponse(title="سلام و احوالپرسی", shortcut="/hello", content="سلام و درود! روزتون بخیر. چطور می‌تونم کمکتون کنم؟"),
                CannedResponse(title="درخواست شماره سفارش", shortcut="/order", content="لطفاً شماره فاکتور یا شماره موبایل ثبت‌نامی خود را جهت بررسی بفرمایید."),
                CannedResponse(title="ارجاع به واحد فنی", shortcut="/tech", content="موضوع شما با اولویت بالا به واحد فنی ارجاع داده شد و در اسرع وقت بررسی خواهد شد."),
                CannedResponse(title="پایان مکالمه و تشکر", shortcut="/bye", content="خوشحالیم که مشکل شما حل شد! در صورت وجود هر سوال دیگری، همیشه در خدمت شما هستیم.")
            ]
            session.add_all(canned_samples)

        # 6. Seed Knowledge Base with realistic sample QA
        kb_stmt = select(KnowledgeItem).limit(1)
        has_kb = (await session.execute(kb_stmt)).scalars().first()
        if not has_kb:
            samples = [
                KnowledgeItem(
                    title="ساعات کاری و پاسخگویی پشتیبانی",
                    content="پشتیبانی هوش مصنوعی ۲۴ ساعته در تمام روزهای هفته فعال است. پشتیبان‌های انسانی نیز همه‌روزه از ساعت ۸:۰۰ صبح الی ۲۲:۰۰ شب پاسخگوی شما عزیزان هستند.",
                    category="faq",
                    source="manual",
                    tags="ساعات کاری, تایم, زمان پشتیبانی, ساعت کاری"
                ),
                KnowledgeItem(
                    title="شرایط و نحوه بازگشت وجه (Refund Policy)",
                    content="در صورت عدم رضایت یا عدم کارکرد سرویس، تا ۷ روز پس از خرید می‌توانید درخواست عودت وجه خود را ثبت کنید. مبلغ طی ۲۴ الی ۴۸ ساعت کاری به همان شماره کارت واریز خواهد شد.",
                    category="policy",
                    source="manual",
                    tags="مرجوعی, بازگشت وجه, عودت وجه, پس دادن پول"
                ),
                KnowledgeItem(
                    title="نحوه صدور فاکتور رسمی شرکتی",
                    content="برای دریافت فاکتور رسمی به همراه شناسه ملی و کد اقتصادی، کافیست پس از ثبت سفارش، تیکت درخواست فاکتور را به همراه مشخصات ثبتی شرکت ارسال فرمایید تا فاکتور رسمی دارای امضا و مهر ارسال شود.",
                    category="agent_learned",
                    source="agent_learned",
                    tags="فاکتور رسمی, شناسه ملی, کد اقتصادی, فاکتور خرید"
                ),
                KnowledgeItem(
                    title="روش اتصال پنل چت به وب‌سایت من",
                    content="برای اتصال پنل به هر سایتی، کافی است تگ اسکریپت ویجت را با شناسه سایت (site_id) در انتهای قالب وب‌سایت یا داخل تگ <body> قرار دهید. همچنین از بخش مستندات پنل می‌توانید نمونه کدهای وردپرس، ری‌اکت و PHP را کپی کنید.",
                    category="technical",
                    source="manual",
                    tags="اتصال ویجت, اسکریپت چت, کد چت, اتصال به سایت"
                )
            ]
            session.add_all(samples)

        await session.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_initial_data()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for widget
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(installer_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(canned_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(knowledge_router, prefix=settings.API_V1_STR)
app.include_router(sites_router, prefix=settings.API_V1_STR)
app.include_router(external_router, prefix=settings.API_V1_STR)

# Frontend static files & single page application
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.PROJECT_NAME, "version": settings.VERSION}

@app.get("/install")
async def serve_installer():
    installer_file = os.path.join(frontend_dir, "installer.html")
    if os.path.exists(installer_file):
        return FileResponse(installer_file)
    return {"error": "Installer page not found"}

@app.get("/login")
async def serve_login():
    login_file = os.path.join(frontend_dir, "login.html")
    if os.path.exists(login_file):
        return FileResponse(login_file)
    return {"error": "Login page not found"}

@app.get("/widget-demo")
async def serve_widget_demo():
    demo_file = os.path.join(frontend_dir, "customer_demo.html")
    if os.path.exists(demo_file):
        return FileResponse(demo_file)
    return {"error": "Demo file not found"}

@app.get("/")
async def serve_dashboard():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "OmniSupport AI API is running. Frontend index not found."}

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.models import Site, AISettings, KnowledgeItem, Agent
from app.routers.ai_router import router as ai_router
from app.routers.chat import router as chat_router
from app.routers.knowledge import router as knowledge_router
from app.routers.sites import router as sites_router
from app.routers.external_api import router as external_router

async def seed_initial_data():
    """Seeds default site, settings, and rich sample knowledge items."""
    async with AsyncSessionLocal() as session:
        # 1. Default Site
        site_stmt = select(Site).where(Site.id == "site_default")
        default_site = (await session.execute(site_stmt)).scalars().first()
        if not default_site:
            default_site = Site(
                id="site_default",
                name="فروشگاه و سامانه آنلاین مرکزی",
                domain="*",
                api_key="omni_live_k8s92f8a129d38c71e041",
                welcome_message="سلام و درود! به پشتیبانی هوشمند خوش آمدید. چطور می‌توانیم شما را راهنمایی کنیم؟",
                primary_color="#4f46e5",
                widget_title="مرکز پشتیبانی هوشمند",
                widget_position="right"
            )
            session.add(default_site)

        # 2. AI Settings
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

        # 3. Default Agent
        agent_stmt = select(Agent).where(Agent.username == "admin")
        agent = (await session.execute(agent_stmt)).scalars().first()
        if not agent:
            agent = Agent(
                username="admin",
                display_name="مدیر سیستم (پشتیبان ارشد)",
                role="admin",
                is_online=True
            )
            session.add(agent)

        # 4. Seed Knowledge Base with realistic sample QA
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
    # Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed data
    await seed_initial_data()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS configuration - Allow all origins for the embeddable widget
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

import os
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "OmniSupport AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./omni_support.db")

    # Server bind
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))

if not Settings().SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")

settings = Settings()

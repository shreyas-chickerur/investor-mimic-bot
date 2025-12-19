import os
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # Application settings
    APP_NAME: str = "InvestorMimic Bot"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/investorbot"

    # API Keys
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    CONTACT_EMAIL: str = ""

    # Trading settings
    PAPER_TRADING: bool = True

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # JWT Settings (for future authentication)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # API Settings
    API_V1_STR: str = "/api/v1"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

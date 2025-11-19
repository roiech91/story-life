"""Configuration settings for the Life Story application."""

from typing import Literal
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with LLM provider configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Provider
    PROVIDER: Literal["openai", "anthropic"] = "openai"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # Model Configuration
    MODEL_NAME: str = "gpt-4o-mini"  # default for OpenAI; if anthropic then "claude-3-5-sonnet-latest"
    TEMPERATURE: float = 0.3
    TIMEOUT_SEC: int = 45
    MAX_TOKENS: int | None = None

    # Database Configuration
    DATABASE_URL: str | None = None
    DATABASE_ECHO: bool = False  # Set to True for SQL query logging

    # OAuth2 Configuration
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    SECRET_KEY: str = "your-secret-key-change-this-in-production"  # For JWT signing
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BACKEND_URL: str = "http://localhost:8000"  # Backend URL for OAuth callbacks
    FRONTEND_URL: str = "http://localhost:3000"  # Frontend URL for OAuth redirects


@lru_cache()
def get_settings() -> Settings:
    """Get singleton settings instance."""
    return Settings()


"""
Configuration management using Pydantic Settings.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Admin Auth
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password_hash: str = Field(default="", alias="ADMIN_PASSWORD_HASH")
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # OpenAI / LLM
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    default_llm_model: str = Field(default="gpt-4o", alias="DEFAULT_LLM_MODEL")
    default_embedding_model: str = Field(default="text-embedding-3-small", alias="DEFAULT_EMBEDDING_MODEL")
    default_embedding_dim: int = Field(default=1024, alias="DEFAULT_EMBEDDING_DIM")

    # Frontend Integrations
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    teams_app_id: Optional[str] = Field(default=None, alias="TEAMS_APP_ID")
    teams_app_secret: Optional[str] = Field(default=None, alias="TEAMS_APP_SECRET")
    teams_tenant_id: str = Field(default="common", alias="TEAMS_TENANT_ID")

    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./data/kms.db", alias="DATABASE_URL")

    # Hybrid Search
    hybrid_weight_text: float = Field(default=0.3, alias="HYBRID_WEIGHT_TEXT")
    hybrid_weight_vector: float = Field(default=0.7, alias="HYBRID_WEIGHT_VECTOR")

    # SQLite vec extension
    sqlite_vec_loaded: bool = Field(default=False)

    # Intent Classification
    intent_confidence_threshold: float = Field(default=0.7, alias="INTENT_CONFIDENCE_THRESHOLD")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()

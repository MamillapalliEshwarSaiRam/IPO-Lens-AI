from functools import lru_cache
from typing import Annotated
from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IPO Lens AI"
    environment: str = "local"
    database_url: str = "sqlite+aiosqlite:///./ipo_lens.db"

    llm_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY")
    )
    llm_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_model: str = Field(
        default="gemini-3.5-flash", validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL")
    )
    llm_cheap_model: str = Field(
        default="gemini-3.5-flash",
        validation_alias=AliasChoices("LLM_CHEAP_MODEL", "OPENAI_CHEAP_MODEL"),
    )
    llm_strong_model: str = Field(
        default="gemini-3.5-flash",
        validation_alias=AliasChoices("LLM_STRONG_MODEL", "OPENAI_STRONG_MODEL"),
    )

    alpha_vantage_api_key: Optional[str] = None
    finnhub_api_key: Optional[str] = None
    news_api_key: Optional[str] = None
    sec_user_agent: str = "IPO Lens AI your-email@example.com"

    backend_cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    max_agent_iterations: int = 3
    max_workflow_steps: int = 20
    max_tool_retries: int = 2
    agent_timeout_seconds: float = 12.0
    provider_timeout_seconds: float = 8.0
    cache_default_ttl_seconds: int = 60 * 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

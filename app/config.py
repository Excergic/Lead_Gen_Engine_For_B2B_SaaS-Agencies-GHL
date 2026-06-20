from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "lead-gen-workflow"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = False

    api_key: SecretStr = Field(description="Operator API key for backend access")
    supabase_url: HttpUrl
    supabase_service_role_key: SecretStr

    supabase_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    perplexity_api_key: SecretStr | None = None
    hunter_api_key: SecretStr | None = None
    discover_audit_jsonl: str = "data/tool_audit.jsonl"
    discover_leads_jsonl: str = "data/discovered_leads.jsonl"
    outreach_queue_jsonl: str = "data/outreach_queue.jsonl"
    email_dry_run: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

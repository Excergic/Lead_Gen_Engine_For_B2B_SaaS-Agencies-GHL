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
    apollo_api_key: SecretStr | None = None
    discover_audit_jsonl: str = "data/tool_audit.jsonl"
    discover_leads_jsonl: str = "data/discovered_leads.jsonl"
    outreach_queue_jsonl: str = "data/outreach_queue.jsonl"
    email_dry_run: bool = True

    # Outreach defaults — used when Stage 1 definition has no calendar / sign-off
    outreach_sender_name: str = "Dhaivat NJ"
    outreach_calendar_url: str = "https://calendly.com/dhaivat-jambudia/new-meeting"
    outreach_offer_headline: str = "Qualified meetings on your calendar — fully automated"
    outreach_offer_description: str = (
        "We find prospects, personalize outreach, and book meetings while you focus on closing."
    )
    outreach_value_proposition: str = "Wake up to calendar invites from qualified prospects."

    # SMTP — all optional; required only when email_dry_run=false
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: SecretStr | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = True   # STARTTLS (port 587)
    smtp_use_ssl: bool = False  # Implicit SSL (port 465)
    email_from_address: str | None = None
    email_from_name: str = ""
    email_reply_to: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

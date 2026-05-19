from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional

class Settings(BaseSettings):
    # LLM Settings
    aria_model: str = Field(default="gpt-4o")
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    api_base: Optional[str] = None

    @field_validator(
        "openai_api_key", "deepseek_api_key", "anthropic_api_key", 
        "gemini_api_key", "openrouter_api_key",
        mode="before"
    )
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        if isinstance(v, str):
            v = v.strip()
            if " " in v:
                raise ValueError("API key must not contain spaces.")
        return v

    # Server Settings
    aria_host: str = Field(default="0.0.0.0")
    aria_port: int = Field(default=8000)

    # Memory Settings
    chroma_persist_dir: str = Field(default="./memory/chroma_db")
    sqlite_db_path: str = Field(default="./memory/procedural.db")
    memory_summarize_after_days: int = Field(default=7)
    memory_max_working_messages: int = Field(default=50)

    # Reflection / Agentic Loop Settings
    reflection_max_plan_revisions: int = Field(default=3)
    reflection_max_execution_retries: int = Field(default=2)
    reflection_plan_threshold: float = Field(default=0.7)
    reflection_result_threshold: float = Field(default=0.6)

    # Scheduler Settings
    scheduler_db_path: str = Field(default="./data/scheduler.db")

    # Email Settings (Optional)
    email_host: Optional[str] = None
    email_port: Optional[int] = None
    email_user: Optional[str] = None
    email_pass: Optional[str] = None

    # Notification Settings (Optional)
    slack_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None
    twilio_whatsapp_to: Optional[str] = None
    discord_webhook_url: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Global config instance
config = Settings()

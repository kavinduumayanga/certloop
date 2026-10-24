from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str = "sqlite:///./data/certificates.db"
    data_dir: Path = Path("./data")
    frontend_origin: str = "http://localhost:5173"
    max_upload_mb: int = 25
    delivery_concurrency: int = Field(default=1, ge=1, le=1)
    # Optional conservative application cap. SMTP providers remain authoritative.
    # None/blank disables the app cap while retaining rolling activity counters.
    max_emails_per_day: int | None = Field(default=None, ge=1)
    email_send_delay_seconds: float = 5
    min_email_send_delay_seconds: float = 5
    max_email_send_delay_seconds: float = 120
    healthy_sends_before_speedup: int = 5
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_app_password: str | None = None
    smtp_sender_email: str | None = None
    smtp_allowed_aliases: str = ""
    smtp_timeout_seconds: float = Field(default=30, gt=0)
    smtp_data_timeout_seconds: float = Field(default=300, gt=0)
    smtp_connection_reuse: bool = True
    smtp_max_messages_per_connection: int = Field(default=25, ge=1)
    smtp_workers: int = Field(default=1, ge=1, le=1)

    @property
    def smtp_aliases(self) -> list[str]:
        return [value.strip().casefold() for value in self.smtp_allowed_aliases.split(",") if value.strip()]

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def generated_dir(self) -> Path:
        return self.data_dir / "generated"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    return settings


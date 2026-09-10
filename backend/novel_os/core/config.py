from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=55432, ge=1, le=65535)
    postgres_user: str = Field(default="novel_os", min_length=1)
    postgres_password: SecretStr
    postgres_db: str = Field(default="novel_os_dev", min_length=1)
    db_connect_timeout: int = Field(default=2, ge=1)
    db_statement_timeout_ms: int = Field(default=3000, ge=1)
    db_pool_timeout: int = Field(default=3, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

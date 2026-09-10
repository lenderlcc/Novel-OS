import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from sqlalchemy import URL, make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid", hide_input_in_errors=True)

    postgres_url: SecretStr
    test_database_url: SecretStr | None = None
    db_connect_timeout: int = Field(default=2, ge=1)
    db_statement_timeout_ms: int = Field(default=3000, ge=1)
    db_pool_timeout: int = Field(default=3, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Files are parsed explicitly by from_file; environment sources are disabled.
        return (init_settings,)

    @field_validator("postgres_url", "test_database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+psycopg" and bool(url.database)
        except (ArgumentError, ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError("Use a postgresql+psycopg URL with an explicit database name")
        return value

    @classmethod
    def from_file(cls, path: Path = Path("config.toml")) -> Self:
        try:
            with path.open("rb") as config_file:
                values = tomllib.load(config_file)
        except tomllib.TOMLDecodeError:
            # TOML parser messages can contain the original configuration value.
            raise ValueError(f"Invalid TOML configuration: {path}") from None
        return cls(**values)

    @property
    def database_url(self) -> URL:
        return make_url(self.postgres_url.get_secret_value())

    def for_test_database(self) -> Self:
        if self.test_database_url is None:
            raise ValueError("Configure test_database_url in config.toml")
        url = make_url(self.test_database_url.get_secret_value())
        if not (url.database or "").endswith("_test"):
            raise ValueError("The test database name must end in _test")
        if url.database == self.database_url.database:
            raise ValueError("The test database must differ from the development database")
        # Keep the complete URL, including TLS, socket and multi-host query parameters.
        return self.model_copy(
            update={"postgres_url": self.test_database_url, "test_database_url": None}
        )

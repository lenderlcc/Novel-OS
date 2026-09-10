import socket
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from novel_os.core.config import BACKEND_DIR, Settings
from novel_os.db.session import Database
from novel_os.main import create_app


@pytest.fixture
def settings() -> Iterator[Settings]:
    # Reserve an unused port without listening: the DB is deterministically unavailable.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        yield Settings(
            _env_file=None,
            postgres_host="127.0.0.1",
            postgres_port=reserved.getsockname()[1],
            postgres_user="novel_os",
            postgres_password=SecretStr("unit-test-only"),
            postgres_db="novel_os_test",
            log_level="INFO",
        )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class IntegrationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", extra="ignore", hide_input_in_errors=True
    )
    test_database_url: SecretStr


@pytest.fixture(scope="session")
def database_settings() -> Settings:
    try:
        config = IntegrationSettings()
        url = make_url(config.test_database_url.get_secret_value())
        if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
            pytest.fail(
                "TEST_DATABASE_URL must use postgresql+psycopg and a database ending in _test"
            )
        if url.database == Settings().postgres_db:
            pytest.fail("TEST_DATABASE_URL must not target the configured development database")
        return Settings(
            _env_file=None,
            postgres_host=url.host or "127.0.0.1",
            postgres_port=url.port or 5432,
            postgres_user=url.username or "novel_os",
            postgres_password=SecretStr(url.password or ""),
            postgres_db=url.database,
        )
    except (ValueError, TypeError):
        pytest.fail("Configure TEST_DATABASE_URL and development settings in backend/.env")


@pytest.fixture
def database(database_settings: Settings) -> Iterator[Database]:
    database = Database(database_settings)
    try:
        yield database
    finally:
        database.dispose()

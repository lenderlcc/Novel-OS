import socket
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import URL

from novel_os.core.config import Settings
from novel_os.db.session import Database
from novel_os.main import create_app


@pytest.fixture
def settings() -> Iterator[Settings]:
    # Reserve an unused port without listening: the DB is deterministically unavailable.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        yield Settings(
            postgres_url=SecretStr(
                URL.create(
                    "postgresql+psycopg",
                    host="127.0.0.1",
                    port=reserved.getsockname()[1],
                    username="novel_os",
                    password="unit-test-only",
                    database="novel_os_test",
                ).render_as_string(hide_password=False)
            ),
            log_level="INFO",
        )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture(scope="session")
def database_settings() -> Settings:
    try:
        return Settings.from_file().for_test_database()
    except (OSError, ValueError):
        pytest.fail("Configure separate development and test database URLs in config.toml")


@pytest.fixture
def database(database_settings: Settings) -> Iterator[Database]:
    database = Database(database_settings)
    try:
        yield database
    finally:
        database.dispose()

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from novel_os.core.config import Settings
from novel_os.db.session import Database
from novel_os.main import create_app


@pytest.fixture
def migration_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))


@pytest.fixture
def core_settings(database_settings: Settings, migration_config: Config):
    # Each test uses a fresh schema inside the separately validated _test database.
    schema = f"novel002_{uuid4().hex}"
    admin = Database(database_settings)
    with admin.engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    options = database_settings.database_url.query.get(
        "options", f"-c statement_timeout={database_settings.db_statement_timeout_ms}"
    )
    url = database_settings.database_url.update_query_dict(
        {"options": f"{options} -c search_path={schema}"}
    )
    settings = database_settings.model_copy(
        update={
            "postgres_url": SecretStr(url.render_as_string(hide_password=False)),
        }
    )
    database = Database(settings)
    try:
        with database.engine.begin() as connection:
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "head")
        yield settings
    finally:
        database.dispose()
        with admin.engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def core_database(core_settings: Settings):
    database = Database(core_settings)
    try:
        yield database
    finally:
        database.dispose()


@pytest.fixture
def core_client(core_settings: Settings):
    with TestClient(create_app(core_settings), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def project_api(core_client):
    response = core_client.post("/api/v1/projects", json={"name": "Test novel"})
    assert response.status_code == 201, response.text
    return "/api/v1/projects/" + response.json()["id"]


@pytest.fixture
def chapter_api(core_client, project_api):
    response = core_client.post(
        project_api + "/chapters", json={"sequence": 1, "title": "Chapter 1"}
    )
    assert response.status_code == 201, response.text
    return project_api + "/chapters/" + response.json()["id"]

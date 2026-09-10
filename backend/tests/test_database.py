from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from novel_os.core.config import Settings
from novel_os.db.session import Database
from novel_os.domain.errors import DatabaseUnavailableError
from novel_os.main import create_app
from novel_os.repositories.health import HealthRepository
from novel_os.services.health import HealthService


def test_service_translates_database_failure() -> None:
    session = MagicMock(spec=Session)
    session.execute.side_effect = OperationalError(
        "SELECT 1", {}, RuntimeError("connection failed")
    )
    with pytest.raises(DatabaseUnavailableError):
        HealthService(HealthRepository(session)).check_database()
    session.commit.assert_not_called()


def test_session_rolls_back_and_closes_on_exception(settings: Settings) -> None:
    database = Database(settings)
    session = MagicMock(spec=Session)
    database.session_factory = MagicMock()
    database.session_factory.return_value.__enter__.return_value = session
    try:
        with pytest.raises(RuntimeError, match="test failure"), database.session():
            raise RuntimeError("test failure")
        session.rollback.assert_called_once()
        session.commit.assert_not_called()
        database.session_factory.return_value.__exit__.assert_called_once()
    finally:
        database.dispose()


def test_application_instances_have_independent_engines(settings: Settings) -> None:
    with TestClient(create_app(settings)) as first, TestClient(create_app(settings)) as second:
        assert first.app.state.database.engine is not second.app.state.database.engine
        assert first.get("/api/v1/health").status_code == 200
        assert second.get("/api/v1/health").status_code == 200


@pytest.mark.integration
def test_readiness_uses_real_postgresql(database_settings: Settings) -> None:
    with TestClient(create_app(database_settings)) as client:
        response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers["x-request-id"]


@pytest.mark.integration
@pytest.mark.parametrize("raise_error", [False, True])
def test_uncommitted_work_is_rolled_back(database: Database, raise_error: bool) -> None:
    # A temporary SQL table probes transaction behavior without adding a domain model.
    with database.engine.connect() as connection:
        connection.execute(text("CREATE TEMP TABLE bootstrap_probe (value integer)"))
        connection.commit()
        database.session_factory.configure(bind=connection)
        try:
            with database.session() as session:
                session.execute(text("INSERT INTO bootstrap_probe VALUES (1)"))
                if raise_error:
                    raise RuntimeError("rollback probe")
        except RuntimeError:
            if not raise_error:
                raise
        assert connection.scalar(text("SELECT count(*) FROM bootstrap_probe")) == 0
        connection.execute(text("DROP TABLE bootstrap_probe"))
        connection.commit()


@pytest.mark.integration
def test_health_repository_does_not_end_transaction(database: Database) -> None:
    with database.session() as session:
        transaction_id = session.scalar(text("SELECT txid_current()"))
        HealthRepository(session).ping()
        assert session.in_transaction()
        assert session.scalar(text("SELECT txid_current()")) == transaction_id

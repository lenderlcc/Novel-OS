import pytest
from pydantic import SecretStr
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(params=[None, "-c lock_timeout=1700 -c statement_timeout=2300"])
def database_settings(database_settings, request):
    query = dict(database_settings.database_url.query)
    query.pop("options", None)
    if request.param is not None:
        query["options"] = request.param
    url = database_settings.database_url.set(query=query)
    return database_settings.model_copy(
        update={"postgres_url": SecretStr(url.render_as_string(hide_password=False))}
    )


def test_schema_isolation_preserves_connection_timeouts(core_database, database_settings):
    with core_database.engine.connect() as connection:
        settings = dict(
            connection.execute(
                text(
                    "SELECT name, setting FROM pg_settings "
                    "WHERE name IN ('lock_timeout', 'statement_timeout')"
                )
            )
            .tuples()
            .all()
        )
        assert connection.scalar(text("SELECT current_schema()")).startswith("novel002_")
    if "options" in database_settings.database_url.query:
        assert settings == {"lock_timeout": "1700", "statement_timeout": "2300"}
    else:
        assert settings["statement_timeout"] == str(database_settings.db_statement_timeout_ms)

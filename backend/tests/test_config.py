import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import URL, event

from novel_os.core.config import Settings
from novel_os.db.session import Database
from novel_os.infrastructure.prepare_docker import prepare_docker


def write_config(path: Path, **values: str | int) -> Path:
    path.write_text("".join(f"{key} = {json.dumps(value)}\n" for key, value in values.items()))
    return path


def url_with_password(password: str, database: str = "novel_dev") -> str:
    return URL.create(
        "postgresql+psycopg",
        username="novel",
        password=password,
        host="127.0.0.1",
        port=55432,
        database=database,
    ).render_as_string(hide_password=False)


@pytest.mark.parametrize("password", ["review${NOVEL_REVIEW_UNSET}value", "p@ss:/%?#$'\"\\value"])
def test_file_and_docker_configuration_preserve_passwords(tmp_path, monkeypatch, password) -> None:
    monkeypatch.setenv("NOVEL_REVIEW_UNSET", "must-not-expand")
    path = write_config(tmp_path / "config.toml", postgres_url=url_with_password(password))
    settings = Settings.from_file(path)
    prepare_docker(settings, tmp_path / "runtime")
    docker_settings = Settings.from_file(tmp_path / "runtime/config.toml")
    assert settings.database_url.password == password
    assert docker_settings.database_url.password == password
    assert (tmp_path / "runtime/postgres/password").read_text() == password
    assert docker_settings.database_url.host == "postgres"
    assert docker_settings.database_url.port == 5432
    assert password not in repr(settings)
    assert password not in str(settings.database_url)
    assert (tmp_path / "runtime").stat().st_mode & 0o777 == 0o700


def test_environment_and_dotenv_cannot_supply_or_override_configuration(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("POSTGRES_URL", url_with_password("wrong"))
    monkeypatch.setenv("TEST_DATABASE_URL", url_with_password("wrong", "wrong_test"))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    (tmp_path / ".env").write_text("LOG_LEVEL=ERROR\n")
    with pytest.raises(ValidationError):
        Settings()
    path = write_config(tmp_path / "config.toml", postgres_url=url_with_password("from-file"))
    settings = Settings.from_file(path)
    assert settings.database_url.password == "from-file"
    assert settings.log_level == "INFO"
    assert settings.test_database_url is None


def test_test_database_query_reaches_the_driver_unchanged(tmp_path) -> None:
    query = (
        "sslmode=verify-full&application_name=novel-tests&sslrootcert=/tmp/ca.pem"
        "&host=first.example:5432&host=second.example:5433"
        "&connect_timeout=7&options=-c%20statement_timeout%3D9000"
    )
    path = write_config(
        tmp_path / "config.toml",
        postgres_url=url_with_password("dev"),
        test_database_url=url_with_password("test", "novel_test") + "?" + query,
    )
    settings = Settings.from_file(path).for_test_database()
    database = Database(settings)
    captured = {}

    class ConnectionProbeComplete(Exception):
        pass

    @event.listens_for(database.engine, "do_connect")
    def capture_connection(dialect, connection_record, args, kwargs):
        captured.update(kwargs)
        raise ConnectionProbeComplete

    try:
        with pytest.raises(ConnectionProbeComplete):
            database.engine.connect()
        assert database.engine.url.query == settings.database_url.query
        assert captured["sslmode"] == "verify-full"
        assert captured["sslrootcert"] == "/tmp/ca.pem"
        assert captured["application_name"] == "novel-tests"
        assert captured["host"] == "first.example,second.example"
        assert captured["port"] == "5432,5433"
        assert captured["connect_timeout"] == "7"
        assert captured["options"] == "-c statement_timeout=9000"
    finally:
        database.dispose()


@pytest.mark.parametrize("test_database", [None, "novel_dev", "shared_test"])
def test_test_configuration_rejects_missing_unsafe_or_shared_database(
    tmp_path, test_database
) -> None:
    values = {"postgres_url": url_with_password("dev", "shared_test")}
    if test_database is not None:
        values["test_database_url"] = url_with_password("test", test_database)
    settings = Settings.from_file(write_config(tmp_path / "config.toml", **values))
    with pytest.raises(ValueError):
        settings.for_test_database()


def test_docker_services_receive_only_their_own_credentials(tmp_path) -> None:
    settings = Settings.from_file(
        write_config(
            tmp_path / "config.toml",
            postgres_url=url_with_password("dev-only"),
            test_database_url=url_with_password("test-only", "novel_test"),
        )
    )
    prepare_docker(settings, tmp_path / "runtime")
    backend_config = (tmp_path / "runtime/config.toml").read_text()
    assert "test-only" not in backend_config
    assert "test_database_url" not in backend_config
    assert (tmp_path / "runtime/postgres/password").read_text() == "dev-only"
    assert (tmp_path / "runtime/postgres-test/password").read_text() == "test-only"


def test_docker_regeneration_removes_unconfigured_test_credentials(tmp_path) -> None:
    output = tmp_path / "runtime"
    settings = Settings(
        postgres_url=url_with_password("dev-only"),
        test_database_url=url_with_password("test-only", "novel_test"),
    )
    prepare_docker(settings, output)
    prepare_docker(settings.model_copy(update={"test_database_url": None}), output)
    assert not (output / "postgres-test").exists()
    assert (output / "postgres/password").read_text() == "dev-only"
    assert Settings.from_file(output / "config.toml").database_url.database == "novel_dev"


@pytest.mark.parametrize("field", ["postgres_url", "test_database_url"])
@pytest.mark.parametrize(
    "query",
    [
        "sslmode=require",
        "sslmode=verify-ca",
        "sslmode=verify-full",
        "sslmode=prefer&sslrootcert=/tmp/ca.pem",
        "channel_binding=require",
        "gssencmode=require",
    ],
)
def test_bundled_docker_rejects_encryption_before_changing_runtime(tmp_path, field, query) -> None:
    values = {
        "postgres_url": url_with_password("dev-only"),
        "test_database_url": url_with_password("test-only", "novel_test"),
    }
    output = tmp_path / "runtime"
    prepare_docker(Settings(**values), output)
    before = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    values[field] += "?" + query
    with pytest.raises(ValueError, match="Bundled Compose PostgreSQL"):
        prepare_docker(Settings(**values), output)
    assert {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    } == before


def test_restrictive_host_umask_does_not_block_container_config_access(tmp_path) -> None:
    settings = Settings(postgres_url=url_with_password("dev-only"))
    previous_umask = os.umask(0o077)
    try:
        prepare_docker(settings, tmp_path / "runtime")
    finally:
        os.umask(previous_umask)
    assert (tmp_path / "runtime").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "runtime/postgres").stat().st_mode & 0o777 == 0o755
    assert (tmp_path / "runtime/postgres/password").stat().st_mode & 0o777 == 0o644
    assert (tmp_path / "runtime/config.toml").stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize("url", ["malformed-private-password", "sqlite:///private-password"])
def test_invalid_database_url_does_not_disclose_input(tmp_path, url) -> None:
    path = write_config(tmp_path / "config.toml", postgres_url=url)
    with pytest.raises(ValidationError) as error:
        Settings.from_file(path)
    assert "private-password" not in str(error.value)


def test_missing_or_invalid_config_fails_without_fallback(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        Settings.from_file(tmp_path / "missing.toml")
    path = tmp_path / "invalid.toml"
    path.write_text("postgres_url = private-password\n")
    with pytest.raises(ValueError) as error:
        Settings.from_file(path)
    assert "private-password" not in str(error.value)

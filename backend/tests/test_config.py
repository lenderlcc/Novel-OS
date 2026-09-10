from pydantic import SecretStr

from novel_os.core.config import Settings


def test_password_special_characters_are_preserved(settings: Settings) -> None:
    settings.postgres_password = SecretStr("p@ss:/%?#value")
    assert settings.database_url.password == "p@ss:/%?#value"
    assert "p@ss" not in repr(settings)
    assert "p@ss" not in str(settings.database_url)


def test_environment_overrides_dotenv(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_DB=from_file\nPOSTGRES_PASSWORD=local-placeholder\n")
    monkeypatch.setenv("POSTGRES_DB", "from_environment")
    settings = Settings(_env_file=env_file)
    assert settings.postgres_db == "from_environment"

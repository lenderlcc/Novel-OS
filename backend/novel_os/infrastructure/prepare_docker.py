"""Render file-only configuration for the bundled local Compose services."""

import argparse
import json
import shutil
from pathlib import Path

from sqlalchemy import URL

from novel_os.core.config import Settings


def prepare_docker(settings: Settings, output: Path) -> None:
    databases = {"postgres": settings.database_url}
    if settings.test_database_url is not None:
        databases["postgres-test"] = settings.for_test_database().database_url
    for url in databases.values():
        if (
            url.host not in {"localhost", "127.0.0.1"}
            or {"host", "port", "service"} & url.query.keys()
        ):
            raise ValueError(
                "Compose preparation requires local database URLs without host overrides"
            )
        if url.query.get("sslmode", "prefer") not in {"disable", "allow", "prefer"} or any(
            key.startswith("ssl") and key != "sslmode" for key in url.query
        ):
            raise ValueError("Bundled Compose PostgreSQL does not support TLS options")
        if any(url.query.get(key) == "require" for key in ("channel_binding", "gssencmode")):
            raise ValueError(
                "Bundled Compose PostgreSQL does not support required channel binding or GSS"
            )
        if not all((url.username, url.password, url.database)):
            raise ValueError("Compose database URLs require a username, password and database")
        if any(
            char in value
            for value in (url.username, url.password, url.database)
            for char in "\r\n\0"
        ):
            raise ValueError("Compose database credentials cannot contain line breaks or NUL")

    # The private parent protects host secrets; mounted files must be readable by
    # the containers' distinct non-root UIDs (10001 for the API, 70 for PostgreSQL).
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.chmod(0o700)
    for service, url in databases.items():
        directory = output / service
        directory.mkdir(mode=0o755, exist_ok=True)
        directory.chmod(0o755)
        for name, value in {
            "username": url.username,
            "password": url.password,
            "database": url.database,
        }.items():
            path = directory / name
            path.write_text(value, encoding="utf-8")
            path.chmod(0o644)

    docker_url: URL = settings.database_url.set(host="postgres", port=5432)
    values = settings.model_dump(exclude={"postgres_url", "test_database_url"})
    values["postgres_url"] = docker_url.render_as_string(hide_password=False)
    path = output / "config.toml"
    path.write_text(
        "".join(
            f"{name} = {json.dumps(value, ensure_ascii=False)}\n" for name, value in values.items()
        ),
        encoding="utf-8",
    )
    path.chmod(0o644)
    stale_test_directory = output / "postgres-test"
    if "postgres-test" not in databases and stale_test_directory.exists():
        shutil.rmtree(stale_test_directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--output", type=Path, default=Path(".runtime"))
    args = parser.parse_args()
    prepare_docker(Settings.from_file(args.config), args.output)
    print(f"Prepared Docker configuration files in {args.output}")


if __name__ == "__main__":
    main()

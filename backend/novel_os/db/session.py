from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from novel_os.core.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        url = settings.database_url
        # Explicit URL options take precedence over the application defaults.
        connect_args = {}
        if "connect_timeout" not in url.query:
            connect_args["connect_timeout"] = settings.db_connect_timeout
        if "options" not in url.query:
            connect_args["options"] = f"-c statement_timeout={settings.db_statement_timeout_ms}"
        # Engine construction is lazy: application startup does not need a live DB.
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_timeout=settings.db_pool_timeout,
            hide_parameters=True,
            connect_args=connect_args,
        )
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        # Closing also rolls back uncommitted work on the successful path.
        # A future write service must explicitly own its transaction boundary.
        with self.session_factory() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    def dispose(self) -> None:
        self.engine.dispose()

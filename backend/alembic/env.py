from alembic import context
from novel_os.core.config import Settings
from novel_os.core.logging import configure_logging
from novel_os.db.base import Base
from novel_os.db.session import Database

settings = Settings()
configure_logging(settings.log_level)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

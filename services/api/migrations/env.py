from alembic import context

from src.core.settings import Settings
from src.db.models import Base
from src.db.session import create_db_engine

target_metadata = Base.metadata
# Read fresh environment values: CLI migration and test invocation need not
# share the API process's cached settings or engine.
url = Settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
from app.core.config import settings
from app.models.base import Base

# Register every model's table with Base.metadata by importing the module.
# Add a new import here whenever a new ORM model file is created.
import app.models.user                  # noqa: F401
import app.models.token_blacklist       # noqa: F401
import app.models.pending_action        # noqa: F401

# ---------------------------------------------------------------------------
# Standard Alembic setup
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url(url: str) -> str:
    """Coerce async driver URLs to their sync equivalents.

    When the app migrates to asyncpg (DATABASE_URL becomes
    postgresql+asyncpg://...), Alembic continues to use psycopg2 for its
    synchronous migration engine with no env.py changes required.
    """
    return url.replace("+asyncpg", "+psycopg2")


# Supply URL from pydantic-settings; ignore whatever is in alembic.ini.
config.set_main_option("sqlalchemy.url", _sync_url(settings.DATABASE_URL))


# ---------------------------------------------------------------------------
# Offline mode — generates SQL without connecting to the database
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connects to the live database
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""
Alembic environment configuration.

Sources the database URL from the project's Pydantic settings
and uses the project's SQLAlchemy Base.metadata for autogenerate.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base  # noqa: F401 — registers metadata
import app.models  # noqa: F401 — registers models with Base.metadata

# ── Alembic Config object ──────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from application settings
# so no credentials are stored in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

# ── Target metadata ────────────────────────────────────────────────
# When domain models are added (next phase), they will register
# on Base.metadata through their module imports.
target_metadata = Base.metadata


# ── Offline migrations ─────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL without a live DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations ──────────────────────────────────────────────

def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the live DB."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

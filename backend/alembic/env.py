from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# --- Make sure `app` package is importable ---
# env.py lives at backend/alembic/env.py; the app package is at backend/app
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# --- Import the app's settings and models ---
from app.config import settings          # noqa: E402
from app.models import Base              # noqa: E402  (must import so metadata is populated)

# Alembic Config object
config = context.config

# Point Alembic at the same DATABASE_URL our app uses.
# This overrides whatever is in alembic.ini, so there is only one source of truth.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Python logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata Alembic compares against
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
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


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,        # detect column type changes
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
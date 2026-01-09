import os
import sys
from pathlib import Path

# --- Configuración del Entorno ---
# 1. Añadir la raíz del proyecto al PYTHONPATH para que Python encuentre el módulo 'src'.
#    Esto permite que Alembic importe los modelos de la aplicación.
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 2. Cargar las variables de entorno desde el fichero .env de la raíz del proyecto.
#    'override=False' significa que las variables YA EXISTENTES en el entorno tienen prioridad
#    sobre las del fichero .env. Esto permite:
#    - Docker Compose: Las variables del docker-compose.yml prevalecen sobre .env
#    - Desarrollo local: Se usan las del fichero .env (si no hay otras definidas)
#    - CI/CD: Variables del pipeline tienen precedencia sobre .env
from dotenv import load_dotenv  # noqa: E402 - Must be after sys.path setup
load_dotenv(dotenv_path=project_root / '.env', override=False)
# --- Fin de la Configuración del Entorno ---

from logging.config import fileConfig  # noqa: E402
from alembic import context  # noqa: E402
from sqlalchemy import engine_from_config, pool  # noqa: E402

# Importar TODOS los mappers para que Alembic detecte todas las tablas
# IMPORTANTE: Importar los mappers (no solo metadata) para registrar las tablas
from src.shared.infrastructure.persistence.sqlalchemy.base import metadata  # noqa: E402
from src.shared.infrastructure.persistence.sqlalchemy import country_mappers  # noqa: E402
from src.modules.user.infrastructure.persistence.sqlalchemy import mappers as user_mappers  # noqa: E402
from src.modules.competition.infrastructure.persistence.sqlalchemy import mappers as competition_mappers  # noqa: E402

# Constantes para drivers de PostgreSQL
ASYNCPG_DRIVER = "postgresql+asyncpg"
PSYCOPG2_DRIVER = "postgresql+psycopg2"

# Iniciar todos los mappers para registrar las tablas en el metadata
country_mappers.start_mappers()
user_mappers.start_mappers()
competition_mappers.start_mappers()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# Usamos el metadata centralizado que ahora contiene TODAS las tablas
target_metadata = metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# Example: config.get_main_option("my_important_option")
# etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Priorizar DATABASE_URL de entorno sobre alembic.ini
    url = os.getenv('DATABASE_URL')
    if not url:
        url = config.get_main_option("sqlalchemy.url")

    # Alembic necesita un driver síncrono. Reemplazamos asyncpg con psycopg2.
    if url and ASYNCPG_DRIVER in url:
        url = url.replace(ASYNCPG_DRIVER, PSYCOPG2_DRIVER)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("La variable de entorno DATABASE_URL no está configurada")

    # Alembic necesita un driver síncrono. Reemplazamos asyncpg con psycopg2.
    if ASYNCPG_DRIVER in db_url:
        db_url = db_url.replace(ASYNCPG_DRIVER, PSYCOPG2_DRIVER)

    config.set_main_option('sqlalchemy.url', db_url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

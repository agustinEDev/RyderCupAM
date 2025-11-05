import os
import sys
from pathlib import Path

# --- Configuración del Entorno ---
# 1. Añadir la raíz del proyecto al PYTHONPATH para que Python encuentre el módulo 'src'.
#    Esto permite que Alembic importe los modelos de la aplicación.
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 2. Cargar las variables de entorno desde el fichero .env de la raíz del proyecto.
#    'override=True' asegura que los valores del fichero .env siempre tengan prioridad,
#    evitando problemas con variables de entorno preexistentes en el sistema.
from dotenv import load_dotenv
load_dotenv(dotenv_path=project_root / '.env', override=True)
# --- Fin de la Configuración del Entorno ---

from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Importar los metadatos de los modelos de la aplicación
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import metadata as user_metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = user_metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
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
    # Obtenemos la URL de la base de datos desde la variable de entorno
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("La variable de entorno DATABASE_URL no está configurada")

    # Inyectamos la URL de la base de datos en la configuración de Alembic
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

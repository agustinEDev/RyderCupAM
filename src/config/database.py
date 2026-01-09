import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Cargar las variables de entorno del fichero .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Si DATABASE_URL no está definida (ej. en desarrollo local), la construimos
if not DATABASE_URL:
    user = os.getenv("POSTGRES_USER", "user")
    password = os.getenv("POSTGRES_PASSWORD", "pass")
    db = os.getenv("POSTGRES_DB", "rydercup_db")
    port = os.getenv("DATABASE_PORT", "5434")
    host = "localhost"
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"

if not DATABASE_URL:
    raise ValueError("No se ha definido la variable de entorno DATABASE_URL o sus componentes")

# 1. Reemplazar 'postgresql://' por 'postgresql+asyncpg://' si es necesario
# asyncpg es el driver que SQLAlchemy usa para operaciones asíncronas con PostgreSQL
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 2. Crear un motor (engine) asíncrono
async_engine = create_async_engine(DATABASE_URL, echo=False)  # echo=False para no llenar los logs


# 3. Crear un "sessionmaker" asíncrono
# Esta es la fábrica que creará nuevas sesiones de base de datos
async_session_maker = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session_for_scripts() -> AsyncGenerator[AsyncSession, None]:
    """
    Función de utilidad para obtener una sesión en scripts o pruebas aisladas.
    No usar directamente en endpoints de FastAPI.
    """

    async with async_session_maker() as session:
        yield session

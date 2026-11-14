import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.env import env_int

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


def ajustes_de_la_conexion() -> dict[str, dict[str, str]]:
    """
    Los tiempos límite de cada conexión (auditoría de la fase 6, DB-04), en milisegundos.

    Sin ellos, una consulta lenta o una petición que muere a mitad de una transacción
    retenía una conexión del pool y sus bloqueos sin límite. La consulta, 15 s. La
    transacción abierta y parada, 2 minutos: por encima de lo que puede esperar una
    petición a un servicio externo (un correo que prueba tres proveedores, la RFEG), y
    corta lo que de verdad se queda colgado (decidido por Agustín el 14 nov 2026). Un
    valor que no sirva (0 sería «sin límite» en Postgres) vuelve al de por defecto.
    """
    return {
        "server_settings": {
            "statement_timeout": str(_milisegundos("DB_STATEMENT_TIMEOUT_MS", 15_000)),
            "idle_in_transaction_session_timeout": str(
                _milisegundos("DB_IDLE_IN_TRANSACTION_TIMEOUT_MS", 120_000)
            ),
        }
    }


# El máximo que acepta Postgres en estos ajustes: por encima rechaza la conexión y la API
# no arrancaría (CodeRabbit)
MAXIMO_DE_POSTGRES_MS = 2_147_483_647


def _milisegundos(nombre: str, defecto: int) -> int:
    """El valor de la variable si es un entero de 1 al máximo de Postgres; si no, `defecto`."""
    valor = env_int(nombre, default=defecto)
    return valor if valor <= MAXIMO_DE_POSTGRES_MS else defecto


AJUSTES_DE_LA_CONEXION = ajustes_de_la_conexion()

# 2. Crear un motor (engine) asíncrono
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # Detecta conexiones muertas antes de reutilizarlas
    pool_recycle=1800,  # Recicla conexiones cada 30 min (evita stale connections)
    # El pool es POR PROCESO, y uvicorn lee WEB_CONCURRENCY del entorno por su cuenta
    # (uvicorn/config.py), sin que este repo la declare en ninguna parte: subirla
    # multiplica las conexiones contra Postgres por N x (pool_size + max_overflow), que
    # los planes pequeños no dan. Los valores por defecto son los de SQLAlchemy, así que
    # mientras haya un solo proceso nada cambia.
    pool_size=env_int("DB_POOL_SIZE", default=5),
    max_overflow=env_int("DB_MAX_OVERFLOW", default=10),
    connect_args=AJUSTES_DE_LA_CONEXION,
)


# 3. Crear un "sessionmaker" asíncrono
# Esta es la fábrica que creará nuevas sesiones de base de datos
async_session_maker = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

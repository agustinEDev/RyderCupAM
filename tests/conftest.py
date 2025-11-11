# tests/conftest.py
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Constants
POSTGRESQL_PREFIX = "postgresql://"
POSTGRESQL_ASYNC_PREFIX = "postgresql+asyncpg://"

# --- Configuración Inicial del Entorno de Test ---
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ['TESTING'] = 'true'

# --- Importaciones de la Aplicación ---
from main import app as fastapi_app
from src.config.database import DATABASE_URL as APP_DATABASE_URL # Renombramos para evitar conflicto
from src.config.dependencies import get_db_session
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import metadata, start_mappers

# Usamos la URL de la app como base, pero la sobreescribimos si es necesario
DATABASE_URL = APP_DATABASE_URL
if not DATABASE_URL:
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB")
    port = os.getenv("DATABASE_PORT")
    host = "localhost"
    DATABASE_URL = f"{POSTGRESQL_PREFIX}{user}:{password}@{host}:{port}/{db}"

# ======================================================================================
# HOOKS DE CONFIGURACIÓN GLOBAL DE PYTEST
# ======================================================================================

def pytest_configure(config):
    """
    Se ejecuta una vez por cada proceso trabajador al inicio.
    Utilizamos un truco para asegurar que los mappers se inicien solo una vez
    en el proceso principal cuando se usa pytest-xdist.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    
    # Solo el proceso maestro (master) o una ejecución sin xdist inicializará los mappers
    if worker_id is None or worker_id == "master":
        print(f"\n🧪 Iniciando tests del Ryder Cup Manager - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🚀 Inicializando mappers de SQLAlchemy...")
        start_mappers()
        # Marcamos que los mappers ya fueron iniciados para evitar reinicialización
        config.mappers_initialized = True

    # Si los mappers ya fueron iniciados por el maestro, no hacemos nada en los workers
    elif hasattr(config, 'mappers_initialized') and config.mappers_initialized:
        # Mappers already initialized by master process, skip initialization
        return
        
    # Fallback por si un worker arranca sin que el maestro haya terminado
    else:
        try:
            start_mappers()
        except Exception:
            # Es probable que falle si otro proceso ya lo hizo, lo ignoramos.
            pass


def pytest_sessionfinish(session, exitstatus):
    """Se ejecuta al final de la sesión de tests."""
    if exitstatus == 0:
        print("✅ Todos los tests pasaron correctamente!")
    else:
        print(f"❌ Algunos tests fallaron. Código de salida: {exitstatus}")

# ======================================================================================
# FIXTURE PRINCIPAL PARA TESTS DE INTEGRACIÓN
# ======================================================================================

@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture principal para tests de integración. Garantiza una base de datos
    limpia y aislada para CADA test, incluso en ejecuciones paralelas.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    db_name = f"test_db_{worker_id}"
    
    # URL base para conectarse a PostgreSQL (sin la base de datos específica)
    db_url_base = DATABASE_URL.rsplit('/', 1)[0]
    if db_url_base.startswith(POSTGRESQL_PREFIX):
        db_url_base = db_url_base.replace(POSTGRESQL_PREFIX, POSTGRESQL_ASYNC_PREFIX, 1)

    # URL para la base de datos de test específica
    test_db_url = f"{db_url_base}/{db_name}"

    # Motor para crear/eliminar la base de datos
    engine = create_async_engine(f"{db_url_base}/postgres", isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        await conn.execute(text(f"CREATE DATABASE {db_name}"))
    await engine.dispose()

    # Motor conectado a la base de datos de test
    test_engine = create_async_engine(test_db_url)
    async with test_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    test_session_local = async_sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_local() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Limpieza
    await test_engine.dispose()
    
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE {db_name}"))
    await engine.dispose()
    
    fastapi_app.dependency_overrides.clear()

# ======================================================================================
# FIXTURES DE DATOS PARA TESTS
# ======================================================================================

@pytest.fixture(scope="session")
def sample_user_data() -> dict:
    """Fixture con datos de ejemplo para un usuario."""
    return {
        "name": "Agustín",
        "surname": "Estévez",
        "email": "agustin.estevez@example.com",
    }

@pytest.fixture(scope="session")
def multiple_users_data() -> list[dict]:
    """Fixture con datos para múltiples usuarios."""
    return [
        {"name": "Carlos", "surname": "García", "email": "carlos.garcia@test.com"},
        {"name": "Ana", "surname": "Martínez", "email": "ana.martinez@test.com"},
        {"name": "Luis", "surname": "Rodríguez", "email": "luis.rodriguez@test.com"},
    ]

@pytest.fixture(scope="session")
def invalid_user_data() -> dict:
    """Fixture con datos de un usuario inválido (email incorrecto)."""
    return {
        "name": "Usuario",
        "surname": "Inválido",
        "email": "email-invalido",
    }


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture que proporciona una sesión de BD asíncrona y aislada para cada test,
    usando una base de datos temporal específica para tests.
    """
    # Crear una base de datos temporal para este test específico
    import uuid
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    test_id = str(uuid.uuid4())[:8]
    db_name = f"test_db_session_{worker_id}_{test_id}"
    
    # URL base para conectarse a PostgreSQL (sin la base de datos específica)
    db_url_base = DATABASE_URL.rsplit('/', 1)[0]
    if db_url_base.startswith(POSTGRESQL_PREFIX):
        db_url_base = db_url_base.replace(POSTGRESQL_PREFIX, POSTGRESQL_ASYNC_PREFIX, 1)

    # URL para la base de datos de test específica
    test_db_url = f"{db_url_base}/{db_name}"

    # Motor para crear/eliminar la base de datos temporal
    admin_engine = create_async_engine(f"{db_url_base}/postgres", isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"CREATE DATABASE {db_name}"))
    await admin_engine.dispose()

    # Motor conectado a la base de datos de test
    engine = create_async_engine(test_db_url)
    
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    test_session_local = async_sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with test_session_local() as session:
        yield session

    # Limpieza: eliminar la base de datos temporal completa
    await engine.dispose()

    admin_engine = create_async_engine(f"{db_url_base}/postgres", isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE {db_name}"))
    await admin_engine.dispose()


# ======================================================================================
# AUTHENTICATION HELPERS FOR INTEGRATION TESTS
# ======================================================================================

@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient) -> tuple[AsyncClient, dict]:
    """
    Fixture que proporciona un cliente autenticado con un token JWT válido.

    Returns:
        Tuple con (client, user_data) donde user_data incluye el token de acceso
    """
    # Registrar un usuario
    user_data = {
        "email": "testuser@example.com",
        "password": "TestPass123!",
        "first_name": "Test",
        "last_name": "User"
    }

    register_response = await client.post("/api/v1/auth/register", json=user_data)
    assert register_response.status_code == 201

    # Hacer login para obtener el token
    login_data = {
        "email": user_data["email"],
        "password": user_data["password"]
    }

    login_response = await client.post("/api/v1/auth/login", json=login_data)
    assert login_response.status_code == 200

    response_data = login_response.json()
    access_token = response_data["access_token"]
    user_info = response_data["user"]

    # Agregar el token al cliente como header por defecto
    client.headers.update({"Authorization": f"Bearer {access_token}"})

    return client, {
        "token": access_token,
        "user": user_info,
        "credentials": user_data
    }


async def create_authenticated_user(client: AsyncClient, email: str, password: str, first_name: str, last_name: str) -> dict:
    """
    Helper para crear un usuario y obtener su token de autenticación.

    Args:
        client: Cliente HTTP de testing
        email: Email del usuario
        password: Contraseña del usuario
        first_name: Nombre
        last_name: Apellido

    Returns:
        Dict con 'token', 'user_id' y 'user_data'
    """
    # Registrar usuario
    user_data = {
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name
    }

    register_response = await client.post("/api/v1/auth/register", json=user_data)
    assert register_response.status_code == 201
    user_id = register_response.json()["id"]

    # Login
    login_response = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    return {
        "token": token,
        "user_id": user_id,
        "user_data": user_data
    }
# tests/conftest.py
import os
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Constants
POSTGRESQL_PREFIX = "postgresql://"
POSTGRESQL_ASYNC_PREFIX = "postgresql+asyncpg://"

# --- Configuración Inicial del Entorno de Test ---
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ['TESTING'] = 'true'

# --- Importaciones de la Aplicación ---
from main import app as fastapi_app
from src.config.database import (
    DATABASE_URL as APP_DATABASE_URL,  # Renombramos para evitar conflicto
)
from src.config.dependencies import get_db_session
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    start_mappers as start_competition_mappers,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import (
    metadata,
    start_mappers,
)
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import (
    start_mappers as start_country_mappers,
)

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
# HELPER FUNCTIONS
# ======================================================================================

async def seed_countries_and_adjacencies(conn) -> None:
    """
    Inserta países y adyacencias básicas para tests de integración.

    Args:
        conn: Conexión de SQLAlchemy (dentro de un bloque begin())
    """
    # Insertar países esenciales para tests
    await conn.execute(text("""
        INSERT INTO countries (code, name_en, name_es, active) VALUES
        ('ES', 'Spain', 'España', true),
        ('PT', 'Portugal', 'Portugal', true),
        ('FR', 'France', 'Francia', true),
        ('IT', 'Italy', 'Italia', true),
        ('DE', 'Germany', 'Alemania', true),
        ('GB', 'United Kingdom', 'Reino Unido', true),
        ('US', 'United States', 'Estados Unidos', true),
        ('AD', 'Andorra', 'Andorra', true),
        ('JP', 'Japan', 'Japón', true)
        ON CONFLICT (code) DO NOTHING;
    """))

    # Insertar adyacencias básicas
    await conn.execute(text("""
        INSERT INTO country_adjacencies (country_code_1, country_code_2) VALUES
        ('ES', 'PT'), ('PT', 'ES'),
        ('ES', 'FR'), ('FR', 'ES'),
        ('ES', 'AD'), ('AD', 'ES'),
        ('FR', 'IT'), ('IT', 'FR'),
        ('FR', 'DE'), ('DE', 'FR'),
        ('FR', 'AD'), ('AD', 'FR')
        ON CONFLICT (country_code_1, country_code_2) DO NOTHING;
    """))


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
        start_mappers()  # User module
        start_country_mappers()  # Shared domain (Country)
        start_competition_mappers()  # Competition module
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
            start_country_mappers()
            start_competition_mappers()
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
# FIXTURE PARA TESTS UNITARIOS (SIN BASE DE DATOS)
# ======================================================================================

@pytest_asyncio.fixture(scope="function")
async def unit_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture para tests unitarios que NO requieren base de datos.

    Crea un cliente HTTP para probar middlewares, handlers y lógica
    que no depende de persistencia. Ideal para tests unitarios puros.

    Uso:
        async def test_middleware(unit_client: AsyncClient):
            response = await unit_client.get("/health")
            assert response.status_code == 200
    """
    from fastapi import FastAPI

    from src.shared.infrastructure.http.correlation_middleware import (
        CorrelationMiddleware,
    )

    # Crear una app mínima solo con middlewares (sin BD)
    minimal_app = FastAPI()
    minimal_app.add_middleware(CorrelationMiddleware)

    # Endpoint simple para testing
    @minimal_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=minimal_app),
        base_url="http://test"
    ) as ac:
        yield ac

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
    # Usar UUID único para cada test para evitar colisiones
    unique_id = str(uuid.uuid4())[:8]
    db_name = f"test_db_{worker_id}_{unique_id}"

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
        await seed_countries_and_adjacencies(conn)

    test_session_local = async_sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_local() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_session] = override_get_db_session

    # Generar ID único para este test (evita colisiones con rate limiter)
    test_client_id = f"test-{uuid.uuid4()}"

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Test-Client-ID": test_client_id}  # IP simulada única por test
    ) as ac:
        yield ac

    # Limpieza
    await test_engine.dispose()

    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE {db_name}"))
    await engine.dispose()

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="module")
async def module_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Fixture de cliente para tests a nivel de módulo.
    Crea una base de datos que se reutiliza para todos los tests del módulo.

    Scope: module (creado una vez por módulo de tests)
    Uso: Para fixtures de usuario reutilizables (module_creator_user, etc.)
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    unique_id = str(uuid.uuid4())[:8]
    db_name = f"test_db_module_{worker_id}_{unique_id}"

    # URL base para conectarse a PostgreSQL
    db_url_base = DATABASE_URL.rsplit('/', 1)[0]
    if db_url_base.startswith(POSTGRESQL_PREFIX):
        db_url_base = db_url_base.replace(POSTGRESQL_PREFIX, POSTGRESQL_ASYNC_PREFIX, 1)

    test_db_url = f"{db_url_base}/{db_name}"

    # Motor para crear la base de datos
    engine = create_async_engine(f"{db_url_base}/postgres", isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        await conn.execute(text(f"CREATE DATABASE {db_name}"))
    await engine.dispose()

    # Motor conectado a la base de datos de test
    test_engine = create_async_engine(test_db_url)
    async with test_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await seed_countries_and_adjacencies(conn)

    test_session_local = async_sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_local() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_session] = override_get_db_session

    test_client_id = f"test-module-{uuid.uuid4()}"

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Test-Client-ID": test_client_id}
    ) as ac:
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
        await seed_countries_and_adjacencies(conn)

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
    Helper para crear un usuario y obtener sus cookies de autenticación.

    Simula el flujo real de producción donde el frontend usa HTTPOnly cookies
    en lugar de headers Authorization.

    Args:
        client: Cliente HTTP de testing
        email: Email del usuario
        password: Contraseña del usuario
        first_name: Nombre
        last_name: Apellido

    Returns:
        Dict con 'cookies', 'token' (legacy), 'user'
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

    # Login
    login_response = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    user_info = login_response.json()["user"]

    # Capturar cookies HTTPOnly del response (como lo haría el navegador)
    cookies = dict(login_response.cookies)

    # Limpiar cookies del cliente para evitar conflictos entre usuarios
    client.cookies.clear()

    return {
        "cookies": cookies,
        "token": token,  # Mantener por compatibilidad
        "user": user_info
    }


def set_auth_cookies(client: AsyncClient, cookies: dict) -> None:
    """
    Helper para establecer cookies de autenticación en el cliente.

    Evita el DeprecationWarning de httpx al usar cookies= en cada request.
    Usar antes de requests autenticadas en tests.

    Args:
        client: Cliente HTTP de testing
        cookies: Dict de cookies de autenticación

    Example:
        set_auth_cookies(client, user["cookies"])
        response = await client.get("/api/v1/protected")
    """
    client.cookies.clear()
    client.cookies.update(cookies)


async def get_user_by_email(client: AsyncClient, email: str):
    """
    Helper para obtener un usuario desde la base de datos por email.
    Útil para tests que necesitan acceder al usuario completo con su estado interno.

    Args:
        client: Cliente HTTP de testing
        email: Email del usuario a buscar

    Returns:
        User: Entidad de usuario encontrada

    Raises:
        AssertionError: Si el usuario no existe
    """
    from src.config.dependencies import (
        get_db_session,
    )
    from src.modules.user.domain.value_objects.email import Email
    from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
        SQLAlchemyUserRepository,
    )

    # Obtener la sesión DB desde el override del cliente
    # El override está configurado en el fixture client()
    db_session_override = fastapi_app.dependency_overrides.get(get_db_session)
    if db_session_override is None:
        raise RuntimeError("get_db_session no tiene override - el test debe usar el fixture client()")

    # Usar la sesión overrideada
    # IMPORTANTE: Usar async with para asegurar que la sesión se cierra correctamente
    async for session in db_session_override():
        try:
            repo = SQLAlchemyUserRepository(session)
            email_vo = Email(email)
            user = await repo.find_by_email(email_vo)
            assert user is not None, f"Usuario con email {email} no encontrado"
            return user
        finally:
            # Cerrar la sesión explícitamente para liberar la conexión
            await session.close()

    # Este punto nunca debería alcanzarse
    raise RuntimeError("No se pudo obtener sesión DB")


# ======================================================================================
# MOCK AUTOMÁTICO DE SERVICIOS EXTERNOS (EMAIL Y TOKEN)
# ======================================================================================
# Para tests de integración, mockeamos los servicios en dependencies.py para evitar
# llamadas reales a Mailgun y mantener los tests rápidos y sin límites de API.

@pytest.fixture(autouse=True)
def mock_external_services():
    """
    Mock automático de servicios externos para todos los tests.

    Mockea:
    - EmailService: Para evitar envíos reales a Mailgun
    - Los tests unitarios usan sus propios mocks
    - Los tests de integración usan estos mocks via dependencies.py
    """
    from unittest.mock import MagicMock, patch

    # Mock para EmailService
    mock_email = MagicMock()
    mock_email.send_verification_email.return_value = True

    # Patchear el factory en dependencies.py
    with patch('src.config.dependencies.EmailService', return_value=mock_email):
        yield mock_email


# ======================================================================================
# REUSABLE USER FIXTURES (Performance optimization)
# ======================================================================================
# Estos fixtures crean usuarios UNA VEZ por módulo de tests (scope="module")
# y los reutilizan en todos los tests del módulo, ahorrando ~10-15s en total.
#
# IMPORTANTE: Estos usuarios NO deben modificarse en los tests (read-only).
# Si un test necesita modificar un usuario, debe crear uno nuevo.

@pytest_asyncio.fixture(scope="module")
async def module_creator_user(module_client: AsyncClient) -> dict:
    """
    Usuario creador reutilizable para todo el módulo de tests.

    Scope: module (creado una vez, reutilizado en todos los tests del módulo)
    Performance: Ahorra ~50ms por test (bcrypt hashing)

    Returns:
        Dict con user data y cookies de autenticación
    """
    return await create_authenticated_user(
        module_client,
        "module_creator@test.com",
        "CreatorPass123!",
        "Module",
        "Creator"
    )


@pytest_asyncio.fixture(scope="module")
async def module_player_user(module_client: AsyncClient) -> dict:
    """
    Usuario jugador reutilizable para todo el módulo de tests.

    Scope: module (creado una vez, reutilizado en todos los tests del módulo)
    Performance: Ahorra ~50ms por test (bcrypt hashing)

    Returns:
        Dict con user data y cookies de autenticación
    """
    return await create_authenticated_user(
        module_client,
        "module_player@test.com",
        "PlayerPass123!",
        "Module",
        "Player"
    )


@pytest_asyncio.fixture(scope="module")
async def module_second_player(module_client: AsyncClient) -> dict:
    """
    Segundo usuario jugador reutilizable para tests que necesitan múltiples jugadores.

    Scope: module (creado una vez, reutilizado en todos los tests del módulo)
    Performance: Ahorra ~50ms por test (bcrypt hashing)

    Returns:
        Dict con user data y cookies de autenticación
    """
    return await create_authenticated_user(
        module_client,
        "module_player2@test.com",
        "Player2Pass123!",
        "Second",
        "Player"
    )


# ======================================================================================
# COMPETITION MODULE FIXTURES
# ======================================================================================

@pytest.fixture(scope="session")
def sample_competition_data() -> dict:
    """Fixture con datos de ejemplo para una competición."""
    from datetime import date, timedelta

    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=3)

    return {
        "name": "Ryder Cup Test 2025",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "main_country": "ES",
        "adjacent_country_1": None,
        "adjacent_country_2": None,
        "handicap_type": "PERCENTAGE",
        "handicap_percentage": 95,
        "max_players": 24,
        "team_assignment": "MANUAL"
    }


async def create_competition(
    client: AsyncClient,
    cookies: dict,
    competition_data: dict | None = None
) -> dict:
    """
    Helper para crear una competición.

    Args:
        client: Cliente HTTP de testing
        cookies: Cookies HTTPOnly de autenticación
        competition_data: Datos de la competición (opcional)

    Returns:
        Dict con los datos de la competición creada
    """
    import uuid
    from datetime import date, timedelta

    if competition_data is None:
        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)
        competition_data = {
            "name": f"Test Competition {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "handicap_type": "PERCENTAGE",
            "handicap_percentage": 95,
            "max_players": 24,
            "team_assignment": "MANUAL"
        }

    # Establecer cookies en el cliente (evita DeprecationWarning de httpx)
    client.cookies.clear()
    client.cookies.update(cookies)

    response = await client.post(
        "/api/v1/competitions",
        json=competition_data
    )
    assert response.status_code == 201, f"Failed to create competition: {response.text}"
    return response.json()


async def activate_competition(client: AsyncClient, cookies: dict, competition_id: str) -> dict:
    """Helper para activar una competición (DRAFT -> ACTIVE)."""
    # Establecer cookies en el cliente (evita DeprecationWarning de httpx)
    client.cookies.clear()
    client.cookies.update(cookies)

    response = await client.post(
        f"/api/v1/competitions/{competition_id}/activate"
    )
    assert response.status_code == 200, f"Failed to activate competition: {response.text}"
    return response.json()

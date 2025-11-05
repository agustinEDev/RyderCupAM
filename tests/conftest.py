# tests/conftest.py
import os
import sys
from pathlib import Path
from datetime import datetime
import pytest

# Configurar variable de entorno para testing (acelera bcrypt)
os.environ['TESTING'] = 'true'

# Añadir el directorio raíz del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ================================
# FIXTURES DE DATOS DE PRUEBA
# ================================

@pytest.fixture
def sample_user_data():
    """Datos de usuario válidos."""
    return {"name": "Juan", "surname": "Pérez", "email": "juan.perez@test.com", "birth_date": "1985-03-15"}

@pytest.fixture
def invalid_user_data():
    """Datos de usuario inválidos."""
    return {"name": "", "surname": "García", "email": "email-invalido", "birth_date": "fecha-invalida"}

@pytest.fixture
def multiple_users_data():
    """Múltiples usuarios para tests de listas."""
    return [
        {"name": "Carlos", "surname": "Rodríguez", "email": "carlos@test.com", "birth_date": "1990-01-01"},
        {"name": "Ana", "surname": "Martínez", "email": "ana@test.com", "birth_date": "1988-05-20"},
        {"name": "Luis", "surname": "González", "email": "luis@test.com", "birth_date": "1992-12-10"}
    ]

# ================================
# FIXTURES PARA FASTAPI TESTS
# ================================

@pytest.fixture
def app():
    """Proporciona la aplicación FastAPI para tests de integración."""
    from main import app
    return app

# ================================
# CONFIGURACIÓN DE PYTEST
# ================================

def pytest_configure(config):
    """Se ejecuta al inicio de pytest."""
    print(f"\n🧪 Iniciando tests del Ryder Cup Manager - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def pytest_sessionfinish(session, exitstatus):
    """Se ejecuta al final de pytest."""
    if exitstatus == 0:
        print("✅ Todos los tests pasaron correctamente!")
    else:
        print(f"❌ Algunos tests fallaron. Código de salida: {exitstatus}")

# ================================
# FIXTURES PARA BASE DE DATOS (AISLADOS)
# ================================

@pytest.fixture(scope="function")
def test_engine():
    """
    Crea un motor de base de datos SQLite en memoria para un único test.
    Las importaciones de SQLAlchemy se hacen aquí para evitar contaminación global.
    """
    from sqlalchemy import create_engine
    # Usar una base de datos en memoria para los tests para máxima velocidad y aislamiento.
    # DATABASE_URL podría apuntar a Docker, pero para tests de función, en memoria es mejor.
    return create_engine("sqlite:///:memory:")

@pytest.fixture(scope="function")
def setup_test_database(test_engine):
    """
    Prepara la base de datos para un test: inicia mappers y crea tablas.
    Se ejecuta por cada test que lo necesite, garantizando un estado limpio.
    """
    # Mover importaciones aquí para evitar la contaminación del espacio de nombres global
    from sqlalchemy.orm import clear_mappers
    from src.modules.user.infrastructure.persistence.sqlalchemy.mappers import metadata, start_mappers
    
    try:
        start_mappers()
        metadata.create_all(test_engine)
        yield test_engine
    finally:
        metadata.drop_all(test_engine)
        clear_mappers()

@pytest.fixture(scope="function")
def db_session(setup_test_database):
    """
    Proporciona una sesión de BD transaccional y aislada para cada test.
    El motor (`setup_test_database`) ya viene con las tablas creadas.
    """
    # Mover importación aquí
    from sqlalchemy.orm import sessionmaker

    connection = setup_test_database.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
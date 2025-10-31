# -*- coding: utf-8 -*-
"""
Configuración global de pytest para el proyecto Ryder Cup Manager.

Este archivo contiene:
- Configuración de paths para importar código fuente
- Fixtures compartidas entre todos los tests
- Configuraciones globales de pytest
"""

import os
import sys
from pathlib import Path
from datetime import datetime

import pytest

# Configurar variable de entorno para testing (acelera bcrypt)
os.environ['TESTING'] = 'true'

# Añadir el directorio raíz del proyecto al path de Python
# Esto permite importar módulos desde src/ en los tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ================================
# FIXTURES DE DATOS DE PRUEBA
# ================================

@pytest.fixture
def sample_user_data():
    """
    Fixture que proporciona datos de usuario válidos para tests.
    
    Returns:
        dict: Diccionario con datos de usuario de prueba
    """
    return {
        "name": "Juan",
        "surname": "Pérez",
        "email": "juan.perez@test.com",
        "birth_date": "1985-03-15"
    }


@pytest.fixture
def invalid_user_data():
    """
    Fixture que proporciona datos de usuario inválidos para tests.
    
    Returns:
        dict: Diccionario con datos de usuario inválidos
    """
    return {
        "name": "",  # Nombre vacío
        "surname": "García",
        "email": "email-invalido",  # Email sin formato correcto
        "birth_date": "fecha-invalida"  # Fecha en formato incorrecto
    }


@pytest.fixture
def multiple_users_data():
    """
    Fixture que proporciona múltiples usuarios para tests de listas.
    
    Returns:
        list: Lista con datos de varios usuarios
    """
    return [
        {
            "name": "Carlos",
            "surname": "Rodríguez",
            "email": "carlos@test.com",
            "birth_date": "1990-01-01"
        },
        {
            "name": "Ana",
            "surname": "Martínez",
            "email": "ana@test.com",
            "birth_date": "1988-05-20"
        },
        {
            "name": "Luis",
            "surname": "González",
            "email": "luis@test.com",
            "birth_date": "1992-12-10"
        }
    ]


# ================================
# FIXTURES PARA FASTAPI TESTS
# ================================

@pytest.fixture
def app():
    """
    Fixture que proporciona la aplicación FastAPI para tests de integración.
    
    Returns:
        FastAPI: Instancia de la aplicación configurada para testing
    """
    from main import app
    return app


# ================================
# CONFIGURACIÓN DE PYTEST
# ================================

def pytest_configure(config):
    """
    Configuración que se ejecuta al inicio de pytest.
    """
    print(f"\n🧪 Iniciando tests del Ryder Cup Manager - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def pytest_sessionfinish(session, exitstatus):
    """
    Configuración que se ejecuta al final de pytest.
    """
    if exitstatus == 0:
        print("✅ Todos los tests pasaron correctamente!")
    else:
        print(f"❌ Algunos tests fallaron. Código de salida: {exitstatus}")

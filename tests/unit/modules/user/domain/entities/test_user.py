# -*- coding: utf-8 -*-
"""
Tests unitarios para la entidad User.

Este archivo contiene tests que verifican:
- Creación correcta de usuarios
- Validación de campos
- Métodos de la clase User
- Casos de borde y errores
"""

import pytest
from datetime import datetime

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email, InvalidEmailError
from src.modules.user.domain.value_objects.password import Password, InvalidPasswordError


class TestUserCreation:
    """Tests para la creación de usuarios"""

    def test_create_user_with_valid_data(self, sample_user_data):
        """
        Test: Crear usuario con datos válidos
        Given: Datos válidos de usuario
        When: Se crea una instancia de User
        Then: El usuario se crea correctamente con todos los campos
        """
        # Arrange - usando fixture de conftest.py
        data = sample_user_data
        
        # Act
        user = User(
            first_name=data["name"],
            last_name=data["surname"],
            email=data["email"]
        )
        
        # Assert
        assert user.first_name == data["name"]
        assert user.last_name == data["surname"]
        assert user.email == data["email"]

    def test_create_user_with_spanish_characters(self):
        """
        Test: Crear usuario con caracteres españoles
        Given: Datos con acentos y ñ
        When: Se crea una instancia de User
        Then: Los caracteres especiales se mantienen correctamente
        """
        # Arrange
        first_name = "José María"
        last_name = "Aznar Botín"
        email = "jose.maria@español.com"
        
        # Act
        user = User(first_name=first_name, last_name=last_name, email=email)
        
        # Assert
        assert user.first_name == "José María"
        assert user.last_name == "Aznar Botín"
        assert user.email == "jose.maria@español.com"

    def test_create_multiple_users(self, multiple_users_data):
        """
        Test: Crear múltiples usuarios
        Given: Lista de datos de usuarios
        When: Se crean múltiples instancias
        Then: Todos los usuarios se crean correctamente
        """
        # Arrange & Act
        users = []
        for data in multiple_users_data:
            user = User(
                first_name=data["name"],
                last_name=data["surname"],
                email=data["email"]
            )
            users.append(user)
        
        # Assert
        assert len(users) == 3
        assert users[0].first_name == "Carlos"
        assert users[1].first_name == "Ana"
        assert users[2].first_name == "Luis"


class TestUserMethods:
    """Tests para los métodos de la clase User"""

    def test_get_full_name_normal_case(self):
        """
        Test: Método get_full_name con caso normal
        Given: Usuario con nombre y apellido
        When: Se llama a get_full_name()
        Then: Retorna nombre completo con formato correcto
        """
        # Arrange
        user = User(first_name="Carlos", last_name="Rodríguez", email="carlos@test.com")
        
        # Act
        full_name = user.get_full_name()
        
        # Assert
        assert full_name == "Carlos Rodríguez"

    def test_get_full_name_with_compound_names(self):
        """
        Test: Método get_full_name con nombres compuestos
        Given: Usuario con nombres y apellidos compuestos
        When: Se llama a get_full_name()
        Then: Retorna nombre completo respetando espacios
        """
        # Arrange
        user = User(first_name="María José", last_name="García López", email="maria@test.com")
        
        # Act
        full_name = user.get_full_name()
        
        # Assert
        assert full_name == "María José García López"

    def test_get_full_name_with_single_word_names(self):
        """
        Test: Método get_full_name con nombres de una palabra
        Given: Usuario con nombre y apellido simples
        When: Se llama a get_full_name()
        Then: Retorna nombre completo con un espacio entre ellos
        """
        # Arrange
        user = User(first_name="Ana", last_name="Martín", email="ana@test.com")
        
        # Act
        full_name = user.get_full_name()
        
        # Assert
        assert full_name == "Ana Martín"


class TestUserValidation:
    """Tests para las validaciones de la clase User"""

    def test_is_valid_with_correct_email(self):
        """
        Test: Validación con email correcto
        Given: Usuario con email válido y todos los campos requeridos
        When: Se llama a is_valid()
        Then: Retorna True
        """
        # Arrange
        user = User(
            first_name="Pedro", 
            last_name="Sánchez", 
            email="pedro.sanchez@test.com",
            password="password123"
        )
        
        # Act
        is_valid = user.is_valid()
        
        # Assert
        assert is_valid is True

    def test_is_valid_with_simple_email(self):
        """
        Test: Validación con email simple pero válido
        Given: Usuario con email formato simple y todos los campos
        When: Se llama a is_valid()
        Then: Retorna True
        """
        # Arrange
        user = User(
            first_name="Laura", 
            last_name="González", 
            email="laura@test.com",
            password="password123"
        )
        
        # Act
        is_valid = user.is_valid()
        
        # Assert
        assert is_valid is True

    def test_is_valid_with_invalid_email_no_at(self):
        """
        Test: Usuario con email sin @ debe fallar al crearse
        Given: Email sin símbolo @
        When: Se intenta crear usuario
        Then: La creación falla porque el Email Value Object valida
        """
        # Act & Assert - Ahora falla al crear el Email Value Object
        with pytest.raises(InvalidEmailError):
            User(first_name="Miguel", last_name="Ruiz", email=Email("email-sin-arroba.com"))

    def test_is_valid_with_invalid_email_no_domain(self):
        """
        Test: Usuario con email sin dominio debe fallar al crearse
        Given: Email sin dominio completo
        When: Se intenta crear usuario
        Then: La creación falla porque el Email Value Object valida
        """
        # Act & Assert
        with pytest.raises(InvalidEmailError):
            User(first_name="Carmen", last_name="López", email=Email("carmen@"))

    def test_is_valid_with_empty_email(self):
        """
        Test: Usuario con email vacío debe fallar al crearse
        Given: Email vacío
        When: Se intenta crear usuario
        Then: La creación falla porque el Email Value Object valida
        """
        # Act & Assert
        with pytest.raises(InvalidEmailError):
            User(first_name="Roberto", last_name="Martínez", email=Email(""))

    def test_is_valid_with_complex_valid_email(self):
        """
        Test: Usuario con email complejo pero válido se crea correctamente
        Given: Email válido con números y caracteres especiales
        When: Se crea usuario
        Then: Se crea exitosamente y tiene email válido
        """
        # Arrange & Act
        user = User(
            first_name="Antonio", 
            last_name="García", 
            email=Email("antonio.garcia123+test@empresa.co.es")
        )
        
        # Assert
        assert user.has_valid_email() is True
        assert str(user.email) == "antonio.garcia123+test@empresa.co.es"


class TestUserEdgeCases:
    """Tests para casos de borde y situaciones especiales"""

    def test_user_with_empty_name(self):
        """
        Test: Usuario con nombre vacío
        Given: Datos con nombre vacío
        When: Se crea el usuario
        Then: Se crea pero nombre queda vacío (comportamiento actual)
        """
        # Arrange & Act
        user = User(first_name="", last_name="Pérez", email="test@example.com")
        
        # Assert
        assert user.first_name == ""
        assert user.last_name == "Pérez"

    def test_user_with_empty_surname(self):
        """
        Test: Usuario con apellido vacío
        Given: Datos con apellido vacío
        When: Se crea el usuario
        Then: Se crea pero apellido queda vacío
        """
        # Arrange & Act
        user = User(first_name="Juan", last_name="", email="test@example.com")
        
        # Assert
        assert user.first_name == "Juan"
        assert user.last_name == ""

    def test_get_full_name_with_empty_name(self):
        """
        Test: get_full_name con nombre vacío
        Given: Usuario con nombre vacío
        When: Se llama a get_full_name()
        Then: Retorna solo el apellido (strip elimina espacios)
        """
        # Arrange
        user = User(first_name="", last_name="Rodríguez", email="test@example.com")
        
        # Act
        full_name = user.get_full_name()
        
        # Assert
        assert full_name == "Rodríguez"

    def test_get_full_name_with_empty_surname(self):
        """
        Test: get_full_name con apellido vacío
        Given: Usuario con apellido vacío
        When: Se llama a get_full_name()
        Then: Retorna solo el nombre (strip elimina espacios)
        """
        # Arrange
        user = User(first_name="Carlos", last_name="", email="test@example.com")
        
        # Act
        full_name = user.get_full_name()
        
        # Assert
        assert full_name == "Carlos"


# ================================
# TESTS DE INTEGRACIÓN LOCAL
# ================================

class TestUserIntegration:
    """Tests de integración para flujos completos con User"""

    def test_create_and_validate_user_flow(self):
        """
        Test: Flujo completo de creación y validación
        Given: Datos válidos de usuario
        When: Se crea y valida el usuario
        Then: Todo el flujo funciona correctamente
        """
        # Arrange
        first_name = "Fernando"
        last_name = "Alonso"
        email = "fernando.alonso@f1.com"
        password = "password123"
        
        # Act
        user = User(
            first_name=first_name, 
            last_name=last_name, 
            email=email, 
            password=password
        )
        full_name = user.get_full_name()
        is_valid = user.is_valid()
        
        # Assert
        assert user.first_name == first_name
        assert user.last_name == last_name
        assert user.email == email
        assert user.password == password
        assert full_name == "Fernando Alonso"
        assert is_valid is True

    def test_create_invalid_user_and_check_validation(self, invalid_user_data):
        """
        Test: Flujo con usuario inválido
        Given: Datos inválidos de usuario
        When: Se crea y valida el usuario
        Then: La validación detecta los errores
        """
        # Arrange
        data = invalid_user_data
        
        # Act
        user = User(
            first_name=data["name"],
            last_name=data["surname"],
            email=data["email"]
        )
        is_valid = user.is_valid()
        
        # Assert
        assert user.first_name == ""  # Nombre vacío
        assert user.email == "email-invalido"  # Email inválido
        assert is_valid is False  # Validación falla por email y otros campos


class TestUserEntityEventCollection:
    """Tests para la colección de eventos de dominio en la entidad User"""

    def test_new_user_has_no_domain_events_initially(self):
        """
        Test: Usuario nuevo no tiene eventos de dominio inicialmente
        Given: Se crea una instancia nueva de User
        When: Se verifica si tiene eventos
        Then: No debe tener eventos de dominio
        """
        # Arrange & Act
        user = User(first_name="Test", last_name="User", email="test@test.com")
        
        # Assert
        assert user.has_domain_events() is False
        assert len(user.get_domain_events()) == 0
    
    def test_create_user_generates_user_registered_event(self):
        """
        Test: Crear usuario con factory method genera evento UserRegistered
        Given: Datos válidos para crear usuario
        When: Se usa User.create()
        Then: Debe generar evento UserRegisteredEvent
        """
        # Arrange
        first_name = "Juan"
        last_name = "Pérez"
        email = "juan.perez@test.com"
        password = "SecurePass123!"
        
        # Act
        user = User.create(first_name, last_name, email, password)
        
        # Assert
        assert user.has_domain_events() is True
        events = user.get_domain_events()
        assert len(events) == 1
        
        # Verificar que es el evento correcto
        from src.users.domain.events.user_registered_event import UserRegisteredEvent
        event = events[0]
        assert isinstance(event, UserRegisteredEvent)
        assert event.user_id == str(user.id.value)
        assert event.email == email
        assert event.name == first_name
        assert event.surname == last_name
    
    def test_clear_domain_events_removes_all_events(self):
        """
        Test: clear_domain_events elimina todos los eventos
        Given: Usuario con eventos de dominio
        When: Se llama a clear_domain_events()
        Then: No debe tener eventos de dominio
        """
        # Arrange
        user = User.create("Ana", "García", "ana@test.com", "Password123!")
        assert user.has_domain_events() is True
        
        # Act
        user.clear_domain_events()
        
        # Assert
        assert user.has_domain_events() is False
        assert len(user.get_domain_events()) == 0
    
    def test_get_domain_events_returns_copy(self):
        """
        Test: get_domain_events retorna una copia, no la lista original
        Given: Usuario con eventos de dominio
        When: Se obtiene la lista de eventos y se modifica
        Then: La lista interna no debe cambiar
        """
        # Arrange
        user = User.create("Luis", "Martín", "luis@test.com", "Password123!")
        original_count = len(user.get_domain_events())
        
        # Act
        events = user.get_domain_events()
        events.clear()  # Modificamos la copia
        
        # Assert
        assert len(user.get_domain_events()) == original_count  # Original no cambió
        assert user.has_domain_events() is True
    
    def test_add_domain_event_method(self):
        """
        Test: _add_domain_event agrega eventos correctamente
        Given: Usuario sin eventos
        When: Se agrega un evento manualmente
        Then: Debe tener el evento agregado
        """
        # Arrange
        user = User(first_name="Test", last_name="User", email="test@test.com")
        from src.users.domain.events.user_registered_event import UserRegisteredEvent
        
        # Act
        event = UserRegisteredEvent(
            user_id="test-id-123",
            email="test@test.com",
            name="Test",
            surname="User"
        )
        user._add_domain_event(event)
        
        # Assert
        assert user.has_domain_events() is True
        assert len(user.get_domain_events()) == 1
        assert user.get_domain_events()[0] == event
    
    def test_user_created_event_has_correct_aggregate_id(self):
        """
        Test: Evento generado tiene el aggregate_id correcto
        Given: Se crea un usuario
        When: Se verifica el evento generado
        Then: El aggregate_id debe coincidir con el ID del usuario
        """
        # Arrange & Act
        user = User.create("Pedro", "López", "pedro@test.com", "Password123!")
        
        # Assert
        events = user.get_domain_events()
        event = events[0]
        assert event.aggregate_id == str(user.id.value)
        assert event.aggregate_id == event.user_id

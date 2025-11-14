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
        user = User.create(
            first_name=data["name"],
            last_name=data["surname"],
            email_str=data["email"],
            plain_password="DefaultPassword123!"
        )
        
        # Assert
        assert user.first_name == data["name"]
        assert user.last_name == data["surname"]
        assert str(user.email) == data["email"]

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
        user = User.create(
            first_name=first_name, 
            last_name=last_name, 
            email_str=email,
            plain_password="DefaultPassword123!"
        )
        
        # Assert
        assert user.first_name == "José María"
        assert user.last_name == "Aznar Botín"
        assert str(user.email) == "jose.maria@español.com"

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
            user = User.create(
                first_name=data["name"],
                last_name=data["surname"],
                email_str=data["email"],
                plain_password="DefaultPassword123!"
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
        user = User.create(
            first_name="Carlos", 
            last_name="Rodríguez", 
            email_str="carlos@test.com",
            plain_password="DefaultPassword123!"
        )
        
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
        user = User.create(
            first_name="María José", 
            last_name="García López", 
            email_str="maria@test.com",
            plain_password="DefaultPassword123!"
        )
        
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
        user = User.create(
            first_name="Ana", 
            last_name="Martín", 
            email_str="ana@test.com",
            plain_password="DefaultPassword123!"
        )
        
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
        user = User.create(
            first_name="Pedro", 
            last_name="Sánchez", 
            email_str="pedro.sanchez@test.com",
            plain_password="ValidPassword123!"
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
        user = User.create(
            first_name="Laura", 
            last_name="González", 
            email_str="laura@test.com",
            plain_password="ValidPassword123!"
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
            User.create(
                first_name="Miguel", 
                last_name="Ruiz", 
                email_str="email-sin-arroba.com",
                plain_password="ValidPassword123!"
            )

    def test_is_valid_with_invalid_email_no_domain(self):
        """
        Test: Usuario con email sin dominio debe fallar al crearse
        Given: Email sin dominio completo
        When: Se intenta crear usuario
        Then: La creación falla porque el Email Value Object valida
        """
        # Act & Assert
        with pytest.raises(InvalidEmailError):
            User.create(
                first_name="Carmen", 
                last_name="López", 
                email_str="carmen@",
                plain_password="ValidPassword123!"
            )

    def test_is_valid_with_empty_email(self):
        """
        Test: Usuario con email vacío debe fallar al crearse
        Given: Email vacío
        When: Se intenta crear usuario
        Then: La creación falla porque el Email Value Object valida
        """
        # Act & Assert
        with pytest.raises(InvalidEmailError):
            User.create(
                first_name="Roberto", 
                last_name="Martínez", 
                email_str="",
                plain_password="ValidPassword123!"
            )

    def test_is_valid_with_complex_valid_email(self):
        """
        Test: Usuario con email complejo pero válido se crea correctamente
        Given: Email válido con números y caracteres especiales
        When: Se crea usuario
        Then: Se crea exitosamente y tiene email válido
        """
        # Arrange & Act
        user = User.create(
            first_name="Antonio", 
            last_name="García", 
            email_str="antonio.garcia123+test@empresa.co.es",
            plain_password="ValidPassword123!"
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
        user = User.create(
            first_name="", 
            last_name="Pérez", 
            email_str="test@example.com",
            plain_password="ValidPassword123!"
        )
        
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
        user = User.create(
            first_name="Juan", 
            last_name="", 
            email_str="test@example.com",
            plain_password="ValidPassword123!"
        )
        
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
        user = User.create(
            first_name="", 
            last_name="Rodríguez", 
            email_str="test@example.com",
            plain_password="ValidPassword123!"
        )
        
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
        user = User.create(
            first_name="Carlos", 
            last_name="", 
            email_str="test@example.com",
            plain_password="ValidPassword123!"
        )
        
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
        password = "ValidPassword123!"
        
        # Act
        user = User.create(
            first_name=first_name, 
            last_name=last_name, 
            email_str=email, 
            plain_password=password
        )
        full_name = user.get_full_name()
        is_valid = user.is_valid()
        
        # Assert
        assert user.first_name == first_name
        assert user.last_name == last_name
        assert str(user.email) == email
        assert user.verify_password(password) is True
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
        
        # Act & Assert
        with pytest.raises(InvalidEmailError):
            User.create(
                first_name=data["name"],
                last_name=data["surname"],
                email_str=data["email"],
                plain_password="ValidPassword123!"
            )


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
        user = User.create(
            first_name="Test", 
            last_name="User", 
            email_str="test@test.com",
            plain_password="ValidPassword123!"
        )
        # Limpiamos el evento de creación para este test específico
        user.clear_domain_events()
        
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
        from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
        event = events[0]
        assert isinstance(event, UserRegisteredEvent)
        assert event.user_id == str(user.id.value)
        assert event.email == email
        assert event.first_name == first_name
        assert event.last_name == last_name
    
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
        user = User.create(
            first_name="Test", 
            last_name="User", 
            email_str="test@test.com",
            plain_password="ValidPassword123!"
        )
        user.clear_domain_events() # Limpiar evento de creación
        from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
        
        # Act
        event = UserRegisteredEvent(
            user_id="test-id-123",
            email="test@test.com",
            first_name="Test",
            last_name="User"
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


class TestUserUpdateHandicap:
    """Tests para el método update_handicap() de User."""

    def test_update_handicap_with_valid_value(self):
        """Test: Actualizar hándicap con un valor válido."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        
        user.update_handicap(15.5)
        
        assert user.handicap == 15.5

    def test_update_handicap_emits_domain_event(self):
        """Test: Actualizar hándicap emite un evento de dominio."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        user.clear_domain_events()  # Limpiar evento de creación
        
        user.update_handicap(15.5)
        
        events = user.get_domain_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "HandicapUpdatedEvent"

    def test_update_handicap_event_contains_correct_data(self):
        """Test: El evento de actualización contiene los datos correctos."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        user.clear_domain_events()
        
        user.update_handicap(15.5)
        
        event = user.get_domain_events()[0]
        assert event.user_id == str(user.id.value)
        assert event.old_handicap is None
        assert event.new_handicap == 15.5

    def test_update_handicap_from_existing_value(self):
        """Test: Actualizar hándicap cuando ya tiene un valor previo."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        user.update_handicap(15.5)
        user.clear_domain_events()
        
        user.update_handicap(20.0)
        
        event = user.get_domain_events()[0]
        assert event.old_handicap == 15.5
        assert event.new_handicap == 20.0

    def test_update_handicap_to_none(self):
        """Test: Actualizar hándicap a None (eliminar hándicap)."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        user.update_handicap(15.5)
        user.clear_domain_events()
        
        user.update_handicap(None)
        
        assert user.handicap is None
        event = user.get_domain_events()[0]
        assert event.old_handicap == 15.5
        assert event.new_handicap is None

    def test_update_handicap_does_not_emit_event_if_same_value(self):
        """Test: No emite evento si el valor no cambia."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        user.update_handicap(15.5)
        user.clear_domain_events()
        
        user.update_handicap(15.5)
        
        events = user.get_domain_events()
        assert len(events) == 0

    def test_update_handicap_with_invalid_value_raises_error(self):
        """Test: Actualizar con valor inválido lanza ValueError."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        
        with pytest.raises(ValueError, match=r"debe estar entre -10\.0 y 54\.0"):
            user.update_handicap(100.0)

    def test_update_handicap_below_minimum_raises_error(self):
        """Test: Actualizar con valor por debajo del mínimo lanza error."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        
        with pytest.raises(ValueError):
            user.update_handicap(-15.0)

    def test_update_handicap_updates_timestamp(self):
        """Test: Actualizar hándicap actualiza el timestamp updated_at."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        original_updated_at = user.updated_at
        
        import time
        time.sleep(0.01)  # Pequeña espera para asegurar diferencia de timestamp
        
        user.update_handicap(15.5)
        
        assert user.updated_at > original_updated_at

    def test_update_handicap_with_negative_value(self):
        """Test: Actualizar con hándicap negativo válido."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        
        user.update_handicap(-5.0)
        
        assert user.handicap == -5.0

    def test_update_handicap_with_zero(self):
        """Test: Actualizar con hándicap cero."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        
        user.update_handicap(0.0)
        
        assert user.handicap == 0.0

    def test_update_handicap_minimum_valid_value(self):
        """Test: Actualizar con valor mínimo válido (-10.0)."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        
        user.update_handicap(-10.0)
        
        assert user.handicap == -10.0

    def test_update_handicap_maximum_valid_value(self):
        """Test: Actualizar con valor máximo válido (54.0)."""
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")

        user.update_handicap(54.0)

        assert user.handicap == 54.0


class TestUserEmailVerification:
    """Tests para la verificación de email de usuarios"""

    def test_generate_verification_token_creates_token(self):
        """
        Test: Generar token de verificación
        Given: Un usuario recién creado
        When: Se llama a generate_verification_token()
        Then: Se genera un token y se asigna al usuario
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        assert user.verification_token is None

        # Act
        token = user.generate_verification_token()

        # Assert
        assert token is not None
        assert len(token) > 0
        assert user.verification_token == token
        assert isinstance(token, str)

    def test_generate_verification_token_returns_unique_tokens(self):
        """
        Test: Tokens generados son únicos
        Given: Un usuario
        When: Se genera un token múltiples veces
        Then: Cada token es diferente
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")

        # Act
        token1 = user.generate_verification_token()
        token2 = user.generate_verification_token()
        token3 = user.generate_verification_token()

        # Assert
        assert token1 != token2
        assert token2 != token3
        assert token1 != token3

    def test_generate_verification_token_updates_updated_at(self):
        """
        Test: Generar token actualiza updated_at
        Given: Un usuario con updated_at inicial
        When: Se genera un token de verificación
        Then: updated_at se actualiza
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        original_updated_at = user.updated_at

        # Act
        user.generate_verification_token()

        # Assert
        assert user.updated_at > original_updated_at

    def test_verify_email_with_valid_token_success(self):
        """
        Test: Verificar email con token válido
        Given: Un usuario con token de verificación generado
        When: Se llama a verify_email() con el token correcto
        Then: El email se marca como verificado
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        token = user.generate_verification_token()

        # Act
        result = user.verify_email(token)

        # Assert
        assert result is True
        assert user.email_verified is True
        assert user.verification_token is None

    def test_verify_email_with_invalid_token_raises_error(self):
        """
        Test: Verificar email con token inválido
        Given: Un usuario con token de verificación
        When: Se llama a verify_email() con token incorrecto
        Then: Se lanza ValueError
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        user.generate_verification_token()

        # Act & Assert
        with pytest.raises(ValueError, match="Token de verificación inválido"):
            user.verify_email("invalid_token_12345")

    def test_verify_email_when_already_verified_raises_error(self):
        """
        Test: No se puede verificar un email ya verificado
        Given: Un usuario con email ya verificado
        When: Se intenta verificar nuevamente
        Then: Se lanza ValueError
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        token = user.generate_verification_token()
        user.verify_email(token)

        # Act & Assert
        with pytest.raises(ValueError, match="El email ya está verificado"):
            new_token = "any_token"
            user.verify_email(new_token)

    def test_verify_email_clears_verification_token(self):
        """
        Test: Verificación limpia el token
        Given: Un usuario con token de verificación
        When: Se verifica el email exitosamente
        Then: El token se elimina (se pone en None)
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        token = user.generate_verification_token()
        assert user.verification_token is not None

        # Act
        user.verify_email(token)

        # Assert
        assert user.verification_token is None

    def test_verify_email_updates_updated_at(self):
        """
        Test: Verificación actualiza updated_at
        Given: Un usuario con updated_at inicial
        When: Se verifica el email
        Then: updated_at se actualiza
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        token = user.generate_verification_token()
        original_updated_at = user.updated_at

        # Act
        user.verify_email(token)

        # Assert
        assert user.updated_at > original_updated_at

    def test_verify_email_emits_domain_event(self):
        """
        Test: Verificación emite evento de dominio
        Given: Un usuario con token de verificación
        When: Se verifica el email exitosamente
        Then: Se emite un EmailVerifiedEvent
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        token = user.generate_verification_token()
        user.clear_domain_events()  # Limpiar eventos anteriores

        # Act
        user.verify_email(token)

        # Assert
        events = user.get_domain_events()
        assert len(events) > 0

        # Verificar que hay un EmailVerifiedEvent
        from src.modules.user.domain.events.email_verified_event import EmailVerifiedEvent
        email_verified_events = [e for e in events if isinstance(e, EmailVerifiedEvent)]
        assert len(email_verified_events) == 1

        event = email_verified_events[0]
        assert event.user_id == str(user.id.value)
        assert event.email == str(user.email.value)
        assert event.verified_at is not None

    def test_is_email_verified_returns_false_initially(self):
        """
        Test: Email no verificado inicialmente
        Given: Un usuario recién creado
        When: Se verifica el estado de verificación
        Then: Retorna False
        """
        # Arrange & Act
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")

        # Assert
        assert user.is_email_verified() is False

    def test_is_email_verified_returns_true_after_verification(self):
        """
        Test: Email verificado retorna True
        Given: Un usuario con email verificado
        When: Se verifica el estado
        Then: Retorna True
        """
        # Arrange
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")
        token = user.generate_verification_token()
        user.verify_email(token)

        # Act & Assert
        assert user.is_email_verified() is True

    def test_user_created_with_email_not_verified(self):
        """
        Test: Usuario creado con email no verificado por defecto
        Given: Datos válidos de usuario
        When: Se crea un usuario
        Then: email_verified es False y verification_token es None
        """
        # Act
        user = User.create("Juan", "Pérez", "juan@test.com", "Password123!")

        # Assert
        assert user.email_verified is False
        assert user.verification_token is None

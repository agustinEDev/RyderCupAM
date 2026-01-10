"""
Tests para PasswordHistory Entity.

Tests unitarios para la entidad de dominio PasswordHistory, que representa
el historial de contraseñas de un usuario para prevenir reutilización.

Arquitectura:
- Capa: Unit Tests (Domain)
- Módulo: User
- Feature: Password History (OWASP A07)
"""

from datetime import datetime, timedelta

from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.events.password_history_recorded_event import (
    PasswordHistoryRecordedEvent,
)
from src.modules.user.domain.value_objects.password_history_id import PasswordHistoryId
from src.modules.user.domain.value_objects.user_id import UserId


class TestPasswordHistoryCreation:
    """Tests para creación de PasswordHistory."""

    def test_create_factory_method_generates_valid_history(self):
        """
        Test: El factory method create() genera un PasswordHistory válido.

        Given: Un user_id y un password_hash
        When: Se llama a PasswordHistory.create()
        Then:
            - Retorna un PasswordHistory con ID único generado
            - Tiene el user_id correcto
            - Tiene el password_hash correcto
            - created_at está cerca de NOW()
        """
        # Given
        user_id = UserId.generate()
        password_hash = "$2b$12$abcdefghijklmnopqrstuv"
        total_count = 3

        # When
        history = PasswordHistory.create(
            user_id=user_id,
            password_hash=password_hash,
            total_history_count=total_count,
        )

        # Then
        assert history.id is not None
        assert isinstance(history.id, PasswordHistoryId)
        assert history.user_id == user_id
        assert history.password_hash == password_hash
        assert history.created_at <= datetime.now()
        assert history.created_at >= datetime.now() - timedelta(seconds=1)

    def test_create_emits_password_history_recorded_event(self):
        """
        Test: create() emite PasswordHistoryRecordedEvent.

        Given: Parámetros válidos para crear PasswordHistory
        When: Se llama a create()
        Then: Emite un evento PasswordHistoryRecordedEvent con los datos correctos
        """
        # Given
        user_id = UserId.generate()
        password_hash = "$2b$12$hashvalue"
        total_count = 5

        # When
        history = PasswordHistory.create(
            user_id=user_id,
            password_hash=password_hash,
            total_history_count=total_count,
        )

        # Then
        events = history.get_domain_events()
        assert len(events) == 1
        assert isinstance(events[0], PasswordHistoryRecordedEvent)
        assert events[0].user_id == str(user_id.value)
        assert events[0].history_id == str(history.id.value)
        assert events[0].total_history_count == total_count

    def test_constructor_creates_history_with_explicit_id(self):
        """
        Test: El constructor acepta un ID explícito.

        Given: Un PasswordHistoryId explícito
        When: Se crea PasswordHistory con ese ID
        Then: El history tiene ese ID específico
        """
        # Given
        history_id = PasswordHistoryId.generate()
        user_id = UserId.generate()
        password_hash = "$2b$12$explicit_id"

        # When
        history = PasswordHistory(id=history_id, user_id=user_id, password_hash=password_hash)

        # Then
        assert history.id == history_id

    def test_constructor_generates_id_if_none_provided(self):
        """
        Test: El constructor genera un ID si se pasa None.

        Given: id=None en el constructor
        When: Se crea PasswordHistory
        Then: Se genera un ID automáticamente
        """
        # Given
        user_id = UserId.generate()
        password_hash = "$2b$12$auto_id"

        # When
        history = PasswordHistory(id=None, user_id=user_id, password_hash=password_hash)

        # Then
        assert history.id is not None
        assert isinstance(history.id, PasswordHistoryId)


class TestPasswordHistoryAgeValidation:
    """Tests para validación de antigüedad de registros."""

    def test_is_older_than_returns_true_for_old_record(self):
        """
        Test: is_older_than() retorna True para registros antiguos.

        Given: Un PasswordHistory con created_at hace 400 días
        When: Se llama a is_older_than(365)
        Then: Retorna True
        """
        # Given
        user_id = UserId.generate()
        password_hash = "$2b$12$old_record"
        history = PasswordHistory(
            id=None,
            user_id=user_id,
            password_hash=password_hash,
            created_at=datetime.now() - timedelta(days=400),
        )

        # When
        result = history.is_older_than(365)

        # Then
        assert result is True

    def test_is_older_than_returns_false_for_recent_record(self):
        """
        Test: is_older_than() retorna False para registros recientes.

        Given: Un PasswordHistory con created_at hace 30 días
        When: Se llama a is_older_than(365)
        Then: Retorna False
        """
        # Given
        user_id = UserId.generate()
        password_hash = "$2b$12$recent_record"
        history = PasswordHistory(
            id=None,
            user_id=user_id,
            password_hash=password_hash,
            created_at=datetime.now() - timedelta(days=30),
        )

        # When
        result = history.is_older_than(365)

        # Then
        assert result is False

    def test_is_older_than_boundary_case(self):
        """
        Test: is_older_than() maneja caso límite correctamente.

        Given: Un PasswordHistory con created_at hace exactamente 365 días
        When: Se llama a is_older_than(365)
        Then: Retorna False (no es MAYOR que 365)
        """
        # Given
        user_id = UserId.generate()
        password_hash = "$2b$12$boundary"
        history = PasswordHistory(
            id=None,
            user_id=user_id,
            password_hash=password_hash,
            created_at=datetime.now() - timedelta(days=365),
        )

        # When
        result = history.is_older_than(365)

        # Then
        assert result is False  # Exactamente 365 días NO es MAYOR que 365


class TestPasswordHistoryDomainEvents:
    """Tests para manejo de eventos de dominio."""

    def test_get_domain_events_returns_copy(self):
        """
        Test: get_domain_events() retorna una copia de los eventos.

        Given: Un PasswordHistory con eventos
        When: Se llama a get_domain_events()
        Then: Retorna una copia (modificar la lista no afecta al original)
        """
        # Given
        user_id = UserId.generate()
        history = PasswordHistory.create(
            user_id=user_id, password_hash="$2b$12$test", total_history_count=1
        )

        # When
        events1 = history.get_domain_events()
        events1.clear()  # Modificar la copia
        events2 = history.get_domain_events()

        # Then
        assert len(events2) == 1  # El original no se modificó

    def test_clear_domain_events_removes_all_events(self):
        """
        Test: clear_domain_events() elimina todos los eventos.

        Given: Un PasswordHistory con eventos
        When: Se llama a clear_domain_events()
        Then: get_domain_events() retorna lista vacía
        """
        # Given
        user_id = UserId.generate()
        history = PasswordHistory.create(
            user_id=user_id, password_hash="$2b$12$test", total_history_count=1
        )
        assert history.has_domain_events()

        # When
        history.clear_domain_events()

        # Then
        assert not history.has_domain_events()
        assert len(history.get_domain_events()) == 0

    def test_has_domain_events_returns_correct_boolean(self):
        """
        Test: has_domain_events() retorna True/False correctamente.

        Given: Un PasswordHistory recién creado (con eventos)
        When: Se verifica has_domain_events()
        Then: Retorna True antes de limpiar, False después
        """
        # Given
        user_id = UserId.generate()
        history = PasswordHistory.create(
            user_id=user_id, password_hash="$2b$12$test", total_history_count=1
        )

        # When & Then
        assert history.has_domain_events() is True
        history.clear_domain_events()
        assert history.has_domain_events() is False


class TestPasswordHistoryStringRepresentation:
    """Tests para representación string."""

    def test_str_contains_key_information(self):
        """
        Test: __str__ contiene información clave (sin mostrar hash completo).

        Given: Un PasswordHistory
        When: Se convierte a string
        Then: Contiene id, user_id y created_at (no password_hash completo)
        """
        # Given
        user_id = UserId.generate()
        history = PasswordHistory.create(
            user_id=user_id,
            password_hash="$2b$12$secret_hash_should_not_appear_in_full",
            total_history_count=1,
        )

        # When
        str_representation = str(history)

        # Then
        assert "PasswordHistory" in str_representation
        assert str(history.id) in str_representation
        assert str(user_id) in str_representation
        # No debe mostrar el hash completo por seguridad
        assert "secret_hash_should_not_appear_in_full" not in str_representation

    def test_repr_equals_str(self):
        """
        Test: __repr__ es igual a __str__.

        Given: Un PasswordHistory
        When: Se obtiene __repr__ y __str__
        Then: Son iguales
        """
        # Given
        user_id = UserId.generate()
        history = PasswordHistory.create(
            user_id=user_id, password_hash="$2b$12$test", total_history_count=1
        )

        # When & Then
        assert repr(history) == str(history)

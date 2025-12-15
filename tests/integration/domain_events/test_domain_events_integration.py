"""
Tests de integración para el sistema completo de Domain Events.

Verifica que todos los componentes trabajen juntos correctamente:
- Entity Event Collection en User
- Event Bus y handlers
- Publicación y procesamiento de eventos
"""

from unittest.mock import patch

import pytest

from src.modules.user.application.handlers.user_registered_event_handler import (
    UserRegisteredEventHandler,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
from src.shared.domain.events.in_memory_event_bus import InMemoryEventBus


class TestDomainEventsIntegration:
    """Tests de integración para el sistema completo de Domain Events."""

    @pytest.mark.asyncio
    async def test_complete_user_registration_flow(self):
        """
        Test: Flujo completo de registro de usuario con eventos
        Given: Un event bus, un handler, y datos de usuario
        When: Se crea un usuario y se publican sus eventos
        Then: El handler debe procesar el evento correctamente
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler = UserRegisteredEventHandler()
        event_bus.register(handler)

        # Mock de métodos del handler para verificar ejecución
        with patch.object(handler, '_send_welcome_email') as mock_email, \
             patch.object(handler, '_log_registration') as mock_log, \
             patch.object(handler, '_notify_external_systems') as mock_notify:

            # Act
            # 1. Crear usuario (genera evento automáticamente)
            user = User.create(
                first_name="Carlos",
                last_name="Rodríguez",
                email_str="carlos.rodriguez@test.com",
                plain_password="SecurePass123!"
            )

            # 2. Verificar que el usuario tiene eventos
            assert user.has_domain_events() is True
            events = user.get_domain_events()
            assert len(events) == 1
            assert isinstance(events[0], UserRegisteredEvent)

            # 3. Publicar eventos a través del event bus
            await event_bus.publish_all(events)

            # 4. Limpiar eventos del usuario (simular repositorio)
            user.clear_domain_events()

            # Assert
            # Verificar que el handler procesó el evento
            mock_email.assert_called_once()
            mock_log.assert_called_once()
            mock_notify.assert_called_once()

            # Verificar que el usuario ya no tiene eventos pendientes
            assert user.has_domain_events() is False

    @pytest.mark.asyncio
    async def test_multiple_handlers_for_same_event(self):
        """
        Test: Múltiples handlers para el mismo tipo de evento
        Given: Un event bus con múltiples handlers para UserRegisteredEvent
        When: Se publica un evento
        Then: Todos los handlers deben procesarlo
        """
        # Arrange
        event_bus = InMemoryEventBus()

        # Crear múltiples handlers
        welcome_handler = UserRegisteredEventHandler()
        audit_handler = UserRegisteredEventHandler()
        notification_handler = UserRegisteredEventHandler()

        # Registrar todos los handlers
        event_bus.register(welcome_handler)
        event_bus.register(audit_handler)
        event_bus.register(notification_handler)

        # Crear usuario
        user = User.create(
            first_name="Ana",
            last_name="García",
            email_str="ana.garcia@test.com",
            plain_password="T3stP@ssw0rd!"
        )

        # Mock de métodos para todos los handlers
        with patch.object(UserRegisteredEventHandler, '_send_welcome_email') as mock_email, \
             patch.object(UserRegisteredEventHandler, '_log_registration') as mock_log, \
             patch.object(UserRegisteredEventHandler, '_notify_external_systems') as mock_notify:

            # Act
            await event_bus.publish_all(user.get_domain_events())

            # Assert
            # Cada método debe haber sido llamado 3 veces (una por cada handler)
            assert mock_email.call_count == 3
            assert mock_log.call_count == 3
            assert mock_notify.call_count == 3

    @pytest.mark.asyncio
    async def test_event_bus_statistics_after_registration(self):
        """
        Test: Estadísticas del event bus después de registrar handlers
        Given: Un event bus con handlers registrados
        When: Se obtienen estadísticas
        Then: Deben reflejar el estado correcto
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler1 = UserRegisteredEventHandler()
        handler2 = UserRegisteredEventHandler()

        # Act
        event_bus.register(handler1)
        event_bus.register(handler2)
        stats = event_bus.get_statistics()

        # Assert
        assert stats["total_event_types"] == 1
        assert stats["total_handlers"] == 2
        assert stats["handlers_by_event_type"]["UserRegisteredEvent"] == 2

    @pytest.mark.asyncio
    async def test_repository_pattern_simulation(self):
        """
        Test: Simulación del patrón Repository con eventos
        Given: Un usuario con eventos y un event bus
        When: Se simula el guardado en repositorio
        Then: Los eventos deben publicarse y limpiarse
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler = UserRegisteredEventHandler()
        event_bus.register(handler)

        # Simular creación de usuario en servicio de aplicación
        user = User.create(
            first_name="Luis",
            last_name="Martín",
            email_str="luis.martin@test.com",
            plain_password="T3stP@ssw0rd!"
        )

        # Mock del handler
        with patch.object(handler, 'handle') as mock_handle:

            # Act - Simular patrón Repository
            # 1. Obtener eventos antes de guardar
            events = user.get_domain_events()

            # 2. "Guardar" usuario en base de datos (simulado)


            # 3. Publicar eventos después del guardado exitoso
            await event_bus.publish_all(events)

            # 4. Limpiar eventos del usuario
            user.clear_domain_events()

            # Assert
            mock_handle.assert_called_once()
            assert user.has_domain_events() is False

            # Verificar que el evento publicado tiene los datos correctos
            published_event = mock_handle.call_args[0][0]
            assert isinstance(published_event, UserRegisteredEvent)
            assert published_event.email == "luis.martin@test.com"
            assert published_event.first_name == "Luis"
            assert published_event.last_name == "Martín"

    @pytest.mark.asyncio
    async def test_error_resilience_in_event_processing(self):
        """
        Test: Resistencia a errores en procesamiento de eventos
        Given: Un event bus con un handler que falla y otro que funciona
        When: Se procesa un evento
        Then: El handler que funciona debe ejecutarse a pesar del error
        """
        # Arrange
        event_bus = InMemoryEventBus()

        working_handler = UserRegisteredEventHandler()
        failing_handler = UserRegisteredEventHandler()

        event_bus.register(working_handler)
        event_bus.register(failing_handler)

        # Crear usuario
        user = User.create(
            first_name="Pedro",
            last_name="López",
            email_str="pedro.lopez@test.com",
            plain_password="T3stP@ssw0rd!"
        )

        # Configurar mocks: uno que falla y otro que funciona
        with patch.object(working_handler, 'handle') as mock_working, \
             patch.object(failing_handler, 'handle', side_effect=Exception("Handler failed")) as mock_failing:

            # Act
            await event_bus.publish_all(user.get_domain_events())

            # Assert
            # Ambos handlers deben haber sido llamados
            mock_working.assert_called_once()
            mock_failing.assert_called_once()

            # Verificar que el working handler recibió el evento correcto
            published_event = mock_working.call_args[0][0]
            assert published_event.email == "pedro.lopez@test.com"

    @pytest.mark.asyncio
    async def test_event_immutability_during_processing(self):
        """
        Test: Inmutabilidad de eventos durante procesamiento
        Given: Un evento de registro de usuario
        When: Se procesa a través del event bus
        Then: El evento no debe ser modificado
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler = UserRegisteredEventHandler()
        event_bus.register(handler)

        user = User.create(
            first_name="María",
            last_name="González",
            email_str="maria.gonzalez@test.com",
            plain_password="T3stP@ssw0rd!"
        )

        original_events = user.get_domain_events()
        original_event = original_events[0]

        # Guardar datos originales
        original_data = {
            "event_id": original_event.event_id,
            "user_id": original_event.user_id,
            "email": original_event.email,
            "first_name": original_event.first_name,
            "last_name": original_event.last_name,
            "occurred_on": original_event.occurred_on
        }

        # Act
        await event_bus.publish_all(original_events)

        # Assert
        # El evento debe mantener todos sus datos originales
        assert original_event.event_id == original_data["event_id"]
        assert original_event.user_id == original_data["user_id"]
        assert original_event.email == original_data["email"]
        assert original_event.first_name == original_data["first_name"]
        assert original_event.last_name == original_data["last_name"]
        assert original_event.occurred_on == original_data["occurred_on"]

    def test_event_collection_returns_copy(self):
        """
        Test: La colección de eventos retorna una copia
        Given: Un usuario con eventos
        When: Se obtiene la lista de eventos múltiples veces
        Then: Debe retornar copias independientes
        """
        # Arrange
        user = User.create(
            first_name="Sofía",
            last_name="Hernández",
            email_str="sofia.hernandez@test.com",
            plain_password="T3stP@ssw0rd!"
        )

        # Act
        events1 = user.get_domain_events()
        events2 = user.get_domain_events()

        # Assert
        # Las listas deben ser diferentes objetos pero con el mismo contenido
        assert events1 is not events2  # Diferentes objetos
        assert len(events1) == len(events2)  # Mismo contenido
        assert events1[0] is events2[0]  # Mismo evento (es inmutable)

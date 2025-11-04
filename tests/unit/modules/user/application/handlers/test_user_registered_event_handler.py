import pytest
from unittest.mock import patch
from src.modules.user.application.handlers.user_registered_event_handler import UserRegisteredEventHandler
from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
from src.shared.domain.events.event_handler import EventHandler

class TestUserRegisteredEventHandler:
    """Tests para UserRegisteredEventHandler."""

    def test_handler_creation(self):
        handler = UserRegisteredEventHandler()
        assert isinstance(handler, EventHandler)

    def test_event_type_property(self):
        handler = UserRegisteredEventHandler()
        assert handler.event_type == UserRegisteredEvent

    def test_can_handle_user_registered_event(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="123", email="test@test.com", first_name="Test", last_name="User")
        assert handler.can_handle(event) is True

    @pytest.mark.asyncio
    async def test_handle_user_registered_event(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="test-user-123", email="juan.perez@test.com", first_name="Juan", last_name="Pérez")
        with patch.object(handler, '_send_welcome_email') as mock_email, \
             patch.object(handler, '_log_registration') as mock_log, \
             patch.object(handler, '_notify_external_systems') as mock_notify:
            await handler.handle(event)
            mock_email.assert_called_once_with(event)
            mock_log.assert_called_once_with(event)
            mock_notify.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_send_welcome_email_logging(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="test-user-123", email="test@test.com", first_name="Test", last_name="User")
        with patch.object(handler._logger, 'info') as mock_logger:
            await handler._send_welcome_email(event)
            mock_logger.assert_called()

    @pytest.mark.asyncio
    async def test_log_registration_logging(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="test-user-123", email="test@test.com", first_name="Test", last_name="User")
        with patch.object(handler._logger, 'info') as mock_logger:
            await handler._log_registration(event)
            mock_logger.assert_called()

    @pytest.mark.asyncio
    async def test_notify_external_systems_logging(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="test-user-123", email="test@test.com", first_name="Test", last_name="User")
        with patch.object(handler._logger, 'info') as mock_logger:
            await handler._notify_external_systems(event)
            mock_logger.assert_called()

    @pytest.mark.asyncio
    async def test_handle_logs_processing_start_and_end(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="test-user-123", email="ana.garcia@test.com", first_name="Ana", last_name="García")
        with patch.object(handler, '_send_welcome_email'), \
             patch.object(handler, '_log_registration'), \
             patch.object(handler, '_notify_external_systems'), \
             patch.object(handler._logger, 'info') as mock_logger:
            await handler.handle(event)
            assert mock_logger.call_count >= 2

class TestUserRegisteredEventHandlerIntegration:
    @pytest.mark.asyncio
    async def test_complete_event_processing_flow(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="integration-test-123", email="integration@test.com", first_name="Integration", last_name="Test")
        await handler.handle(event)
        assert True

    @pytest.mark.asyncio
    async def test_handler_with_real_event_data(self):
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(user_id="real-user-456", email="josé.maría@español.com", first_name="José María", last_name="González Rodríguez")
        await handler.handle(event)
        assert event.full_name == "José María González Rodríguez"
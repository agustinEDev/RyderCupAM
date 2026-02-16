"""
Tests para OAuth DTOs - Verificación de contratos Pydantic.
"""

import pytest
from pydantic import ValidationError

from src.modules.user.application.dto.oauth_dto import (
    GoogleLoginRequestDTO,
    GoogleLoginResponseDTO,
    LinkGoogleAccountRequestDTO,
    LinkGoogleAccountResponseDTO,
    UnlinkGoogleAccountResponseDTO,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO


class TestGoogleLoginRequestDTO:
    """Tests para GoogleLoginRequestDTO."""

    def test_valid_request_with_all_fields(self):
        dto = GoogleLoginRequestDTO(
            authorization_code="4/0AbCD-EfGh_code",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            device_id_from_cookie="abc-123",
        )
        assert dto.authorization_code == "4/0AbCD-EfGh_code"
        assert dto.ip_address == "192.168.1.1"
        assert dto.user_agent == "Mozilla/5.0"
        assert dto.device_id_from_cookie == "abc-123"

    def test_valid_request_with_only_required_fields(self):
        dto = GoogleLoginRequestDTO(authorization_code="some-code")
        assert dto.authorization_code == "some-code"
        assert dto.ip_address is None
        assert dto.user_agent is None
        assert dto.device_id_from_cookie is None

    def test_missing_authorization_code_raises(self):
        with pytest.raises(ValidationError):
            GoogleLoginRequestDTO()

    def test_empty_authorization_code_raises(self):
        with pytest.raises(ValidationError):
            GoogleLoginRequestDTO(authorization_code="")

    def test_serialization(self):
        dto = GoogleLoginRequestDTO(
            authorization_code="code-123",
            ip_address="10.0.0.1",
        )
        data = dto.model_dump()
        assert data["authorization_code"] == "code-123"
        assert data["ip_address"] == "10.0.0.1"
        assert data["user_agent"] is None


class TestGoogleLoginResponseDTO:
    """Tests para GoogleLoginResponseDTO."""

    @pytest.fixture
    def user_response(self):
        from datetime import datetime

        return UserResponseDTO(
            id="550e8400-e29b-41d4-a716-446655440000",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            email_verified=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_valid_response(self, user_response):
        dto = GoogleLoginResponseDTO(
            access_token="jwt-access",
            refresh_token="jwt-refresh",
            csrf_token="csrf-xyz",
            user=user_response,
            is_new_user=True,
        )
        assert dto.access_token == "jwt-access"
        assert dto.refresh_token == "jwt-refresh"
        assert dto.csrf_token == "csrf-xyz"
        assert dto.token_type == "bearer"
        assert dto.is_new_user is True
        assert dto.user.email == "test@example.com"

    def test_default_values(self, user_response):
        dto = GoogleLoginResponseDTO(
            access_token="a",
            refresh_token="r",
            csrf_token="c",
            user=user_response,
        )
        assert dto.token_type == "bearer"
        assert dto.is_new_user is False
        assert dto.device_id is None
        assert dto.should_set_device_cookie is False

    def test_with_device_info(self, user_response):
        dto = GoogleLoginResponseDTO(
            access_token="a",
            refresh_token="r",
            csrf_token="c",
            user=user_response,
            device_id="dev-123",
            should_set_device_cookie=True,
        )
        assert dto.device_id == "dev-123"
        assert dto.should_set_device_cookie is True

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            GoogleLoginResponseDTO(access_token="a")


class TestLinkGoogleAccountRequestDTO:
    """Tests para LinkGoogleAccountRequestDTO."""

    def test_valid_request(self):
        dto = LinkGoogleAccountRequestDTO(authorization_code="link-code")
        assert dto.authorization_code == "link-code"

    def test_missing_code_raises(self):
        with pytest.raises(ValidationError):
            LinkGoogleAccountRequestDTO()

    def test_empty_code_raises(self):
        with pytest.raises(ValidationError):
            LinkGoogleAccountRequestDTO(authorization_code="")


class TestLinkGoogleAccountResponseDTO:
    """Tests para LinkGoogleAccountResponseDTO."""

    def test_valid_response(self):
        dto = LinkGoogleAccountResponseDTO(
            message="Google account linked successfully",
            provider="google",
            provider_email="user@gmail.com",
        )
        assert dto.message == "Google account linked successfully"
        assert dto.provider == "google"
        assert dto.provider_email == "user@gmail.com"

    def test_serialization(self):
        dto = LinkGoogleAccountResponseDTO(
            message="OK",
            provider="google",
            provider_email="a@b.com",
        )
        data = dto.model_dump()
        assert "message" in data
        assert "provider" in data
        assert "provider_email" in data


class TestUnlinkGoogleAccountResponseDTO:
    """Tests para UnlinkGoogleAccountResponseDTO."""

    def test_valid_response(self):
        dto = UnlinkGoogleAccountResponseDTO(
            message="Google account unlinked successfully",
            provider="google",
        )
        assert dto.message == "Google account unlinked successfully"
        assert dto.provider == "google"

    def test_serialization(self):
        dto = UnlinkGoogleAccountResponseDTO(
            message="OK",
            provider="google",
        )
        data = dto.model_dump()
        assert data["message"] == "OK"
        assert data["provider"] == "google"

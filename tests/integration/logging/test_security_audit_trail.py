"""Tests E2E del Security Audit Trail"""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSecurityAuditTrail:
    """Tests end-to-end del audit trail de seguridad"""

    async def test_login_success_creates_audit_log(self, client: AsyncClient):
        """Login exitoso registra evento en security_audit.log"""
        # Register user
        register_data = {
            "email": "audit.test@example.com",
            "password": "AuditT3st123!",
            "first_name": "Audit",
            "last_name": "Test",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login
        login_data = {
            "email": "audit.test@example.com",
            "password": "AuditT3st123!",
        }
        response = await client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200

        # Verificar que existe security_audit.log
        log_file = Path("logs/security_audit.log")
        assert log_file.exists()

        # Verificar que contiene LoginAttemptEvent
        content = log_file.read_text()
        assert "LoginAttemptEvent" in content
        assert "audit.test@example.com" in content

    async def test_login_failure_creates_audit_log_with_reason(self, client: AsyncClient):
        """Login fallido registra evento con failure_reason"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "WrongPass123!",
        }
        response = await client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401

        # Verificar log contiene failure
        log_file = Path("logs/security_audit.log")
        content = log_file.read_text()
        assert "LOGIN FAILED" in content or "success\": false" in content

    async def test_logout_creates_logout_and_revocation_events(self, client: AsyncClient):
        """Logout registra LogoutEvent + RefreshTokenRevokedEvent"""
        # Register + Login
        register_data = {
            "email": "logout.audit@example.com",
            "password": "LogoutT3st123!",
            "first_name": "Logout",
            "last_name": "Audit",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "logout.audit@example.com",
                "password": "LogoutT3st123!",
            },
        )
        access_token = login_response.json()["access_token"]

        # Logout
        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert logout_response.status_code == 200

        # Verificar logs
        log_file = Path("logs/security_audit.log")
        content = log_file.read_text()
        assert "LOGOUT" in content
        assert "REFRESH TOKENS REVOKED" in content or "RefreshTokenRevokedEvent" in content

    async def test_refresh_token_used_creates_audit_log(self, client: AsyncClient):
        """Uso de refresh token registra RefreshTokenUsedEvent"""
        # Register
        register_data = {
            "email": "refresh.audit@example.com",
            "password": "RefreshT3st123!",
            "first_name": "Refresh",
            "last_name": "Test",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login (genera refresh token)
        await client.post(
            "/api/v1/auth/login",
            json={
                "email": "refresh.audit@example.com",
                "password": "RefreshT3st123!",
            },
        )

        # Usar refresh token
        await client.post("/api/v1/auth/refresh-token")

        # Verificar log
        log_file = Path("logs/security_audit.log")
        content = log_file.read_text()
        assert "REFRESH TOKEN USED" in content or "RefreshTokenUsedEvent" in content

    async def test_audit_log_entries_are_valid_json(self, client: AsyncClient):
        """Todas las entradas del log son JSON válido"""
        log_file = Path("logs/security_audit.log")

        if not log_file.exists():
            pytest.skip("No security_audit.log file exists yet")

        # Leer todas las líneas
        lines = log_file.read_text().strip().split("\n")

        # Verificar que cada línea es JSON válido
        valid_json_count = 0
        for line in lines:
            if not line.strip():
                continue
            try:
                log_entry = json.loads(line)
                # Verificar estructura básica
                assert "timestamp" in log_entry
                assert "level" in log_entry
                assert "message" in log_entry
                valid_json_count += 1
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON line: {line[:100]}")

        assert valid_json_count > 0, "No valid JSON entries found"

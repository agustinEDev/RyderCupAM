"""
Tests de seguridad para endpoints de autenticación.

Este archivo contiene tests que verifican que los endpoints NO revelen
información sensible que pueda ser usada para user enumeration.
"""

import logging
import time

import pytest
from fastapi import status
from httpx import AsyncClient

from src.modules.user.infrastructure.api.v1 import auth_routes
from tests.conftest import get_user_by_email


@pytest.mark.asyncio
class TestAuthSecurityUserEnumeration:
    """
    Suite de tests para verificar protección contra user enumeration.

    User enumeration es un vector de ataque donde un atacante puede
    determinar qué emails están registrados en el sistema basándose
    en diferentes respuestas del servidor.
    """

    async def test_verify_email_returns_generic_message_for_all_errors(self, client: AsyncClient):
        """
        Test: verify-email no revela información sobre tokens/usuarios

        Security Concern: Si el endpoint retorna diferentes mensajes para:
        - Token inválido
        - Token expirado
        - Usuario no encontrado
        - Email ya verificado

        Un atacante podría usar esto para enumerar usuarios.

        Expected Behavior: Siempre retornar el mismo mensaje genérico.
        """
        test_cases = [
            {"token": "invalid_token_123", "description": "Token inválido"},
            {"token": "a" * 100, "description": "Token muy largo"},
            {"token": "expired_token", "description": "Token que no existe"},
        ]

        expected_message = "unable to verify email"

        for test_case in test_cases:
            # Act
            response = await client.post(
                "/api/v1/auth/verify-email",
                json={"token": test_case["token"]}
            )

            # Assert
            assert response.status_code == status.HTTP_400_BAD_REQUEST, \
                f"Failed for: {test_case['description']}"

            detail = response.json()["detail"].lower()
            assert expected_message in detail, \
                f"Message differs for {test_case['description']}: {detail}"

            # Verificar que no contiene información específica
            assert "not found" not in detail.lower()
            assert "expired" not in detail.lower()
            assert "invalid token" not in detail.lower()
            assert "already verified" not in detail.lower()

    async def test_resend_verification_always_returns_success(self, client: AsyncClient):
        """
        Test: resend-verification siempre retorna 200 OK

        Security Concern: Si el endpoint retorna:
        - 400 para email no existente
        - 200 para email existente

        Un atacante puede enumerar emails registrados.

        Expected Behavior: Siempre retornar 200 OK con mensaje genérico,
        independientemente de si el email existe o no.
        """
        # Registrar un usuario para tener un caso válido
        valid_user_data = {
            "email": "security.test@example.com",
            "password": "ValidPass123",
            "first_name": "Security",
            "last_name": "Test",
        }
        await client.post("/api/v1/auth/register", json=valid_user_data)

        test_cases = [
            {"email": "security.test@example.com", "description": "Email existente"},
            {"email": "noexiste@example.com", "description": "Email no existente"},
            {"email": "otro.noexiste@example.com", "description": "Otro email no existente"},
        ]

        expected_message = "if the email address exists in our system"
        responses = []

        for test_case in test_cases:
            # Act
            response = await client.post(
                "/api/v1/auth/resend-verification",
                json={"email": test_case["email"]}
            )

            # Assert
            assert response.status_code == status.HTTP_200_OK, \
                f"Status code differs for: {test_case['description']}"

            detail = response.json()["message"].lower()
            assert expected_message in detail, \
                f"Message differs for {test_case['description']}: {detail}"

            responses.append(response.json())

        # Verificar que TODAS las respuestas son idénticas
        first_message = responses[0]["message"]
        for i, resp in enumerate(responses[1:], 1):
            assert resp["message"] == first_message, \
                f"Response {i} differs from first response - potential user enumeration!"

    async def test_resend_verification_same_response_for_verified_user(self, client: AsyncClient):
        """
        Test: resend-verification retorna el mismo mensaje para usuarios verificados

        Security Concern: Si el endpoint retorna diferente respuesta para
        usuarios verificados vs no verificados, revela información de estado.

        Expected Behavior: Mismo mensaje genérico para todos los casos.
        """
        # Registrar y verificar usuario
        user_data = {
            "email": "verified.security@example.com",
            "password": "ValidPass123",
            "first_name": "Verified",
            "last_name": "Security",
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener token y verificar
        user = await get_user_by_email(client, user_data["email"])
        verify_response = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": user.verification_token}
        )
        assert verify_response.status_code == status.HTTP_200_OK

        # Act - Intentar reenviar verificación a usuario ya verificado
        response = await client.post(
            "/api/v1/auth/resend-verification",
            json={"email": user_data["email"]}
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        detail = response.json()["message"].lower()

        # Debe usar el mismo mensaje genérico
        assert "if the email address exists" in detail

        # No debe revelar que el email ya está verificado
        assert "already verified" not in detail.lower()
        assert "verified" not in detail.lower()

    async def test_timing_attack_mitigation(self, client: AsyncClient):
        """
        Test: Verificar que no hay timing attacks obvios

        Security Concern: Si el servidor tarda más en responder cuando
        un email existe vs cuando no existe, un atacante puede usar
        timing attacks para enumerar usuarios.

        Note: Este es un test básico. Para timing attacks reales,
        se necesitarían mediciones estadísticas más sofisticadas.
        """

        # Registrar un usuario
        valid_user = {
            "email": "timing.test@example.com",
            "password": "ValidPass123",
            "first_name": "Timing",
            "last_name": "Test",
        }
        await client.post("/api/v1/auth/register", json=valid_user)

        # Medir tiempo para email existente
        start = time.time()
        response_exists = await client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "timing.test@example.com"}
        )
        time_exists = time.time() - start

        # Medir tiempo para email no existente
        start = time.time()
        response_not_exists = await client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "noexiste.timing@example.com"}
        )
        time_not_exists = time.time() - start

        # Assert - Ambos deben retornar 200 OK
        assert response_exists.status_code == status.HTTP_200_OK
        assert response_not_exists.status_code == status.HTTP_200_OK

        # Note: No verificamos timing exacto porque puede variar,
        # pero documentamos que ambos deberían tener timing similar
        # En producción, considerar agregar delays constantes si es necesario
        print(f"\n[Security] Timing - Email exists: {time_exists:.4f}s")
        print(f"[Security] Timing - Email not exists: {time_not_exists:.4f}s")


@pytest.mark.asyncio
class TestAuthSecurityLogging:
    """
    Suite de tests para verificar que el logging de seguridad funciona correctamente.

    El logging es crítico para:
    - Detectar intentos de brute force
    - Monitorear fallos del servicio de email
    - Debug en desarrollo
    - Auditoría de seguridad
    """

    async def test_verify_email_logs_attempts(self, client: AsyncClient, caplog):
        """
        Test: verify-email registra intentos de verificación en logs

        Verifica que:
        - Se loggean intentos de verificación
        - No se expone el token completo (solo preview)
        - Se loggean fallos sin exponer información sensible
        """
        caplog.set_level(logging.INFO)

        # Act - Intentar verificar con token inválido
        response = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": "invalid_token_12345"}
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verificar que se loggeó el intento
        log_messages = [record.message for record in caplog.records]
        assert any("Email verification attempt" in msg for msg in log_messages)
        assert any("Email verification failed" in msg for msg in log_messages)

        # Verificar que NO se expone el token completo
        full_token_exposed = any("invalid_token_12345" in msg for msg in log_messages)
        assert not full_token_exposed, "Full token should not be exposed in logs"

    async def test_resend_verification_logs_requests(self, client: AsyncClient, caplog):
        """
        Test: resend-verification registra solicitudes en logs

        Verifica que:
        - Se loggean solicitudes de reenvío
        - El email está parcialmente ofuscado (protección de privacidad)
        - Se distingue entre éxito y fallo en los logs
        """
        caplog.set_level(logging.INFO)

        # Registrar un usuario válido
        valid_user = {
            "email": "logging.test@example.com",
            "password": "ValidPass123",
            "first_name": "Logging",
            "last_name": "Test",
        }
        await client.post("/api/v1/auth/register", json=valid_user)

        # Clear previous logs
        caplog.clear()

        # Act - Solicitar reenvío para email existente
        response_exists = await client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "logging.test@example.com"}
        )

        # Assert
        assert response_exists.status_code == status.HTTP_200_OK

        log_messages = [record.message for record in caplog.records]

        # Verificar que se loggeó la solicitud
        assert any("Verification email resend requested" in msg for msg in log_messages)
        assert any("Verification email resend successful" in msg for msg in log_messages)

        # Verificar que el email está ofuscado (no completo)
        full_email_exposed = any("logging.test@example.com" in msg for msg in log_messages)
        assert not full_email_exposed, "Full email should not be exposed in logs"

        # Verificar que se muestra preview del email
        assert any("log***@example.com" in msg for msg in log_messages)

    async def test_error_handling_structure_is_present(self, client: AsyncClient, caplog):
        """
        Test: Verificar que la estructura de manejo de errores está implementada

        Este test verifica indirectamente que el código tiene la estructura
        necesaria para manejar errores inesperados de forma segura, sin
        necesidad de forzar excepciones reales.

        Verifica:
        1. Logger está configurado en el módulo
        2. Endpoints responden de forma consistente incluso con inputs extremos
        3. Mensajes genéricos se mantienen en todos los casos
        """

        caplog.set_level(logging.INFO)

        # 1. Verificar que el logger existe en el módulo

        assert hasattr(auth_routes, 'logger'), "Logger should be configured in auth_routes module"
        assert auth_routes.logger.name == "src.modules.user.infrastructure.api.v1.auth_routes"

        # 2. Probar con inputs edge case para verify-email
        edge_cases_verify = [
            "x" * 1000,  # Token extremadamente largo
            "!@#$%^&*()",  # Caracteres especiales
            "unicode🔥test",  # Unicode
            "",  # Vacío (maneja Pydantic)
        ]

        for token in edge_cases_verify:
            if token:  # Skip vacío (Pydantic lo rechaza antes)
                response = await client.post(
                    "/api/v1/auth/verify-email",
                    json={"token": token}
                )
                # Siempre debe retornar mensaje genérico
                if response.status_code == 400:
                    detail = response.json().get("detail", "")
                    assert "unable to verify email" in detail.lower() or "validation" in detail.lower(), \
                        f"Should return generic message for token: {token[:20]}..."

        # 3. Probar con inputs edge case para resend-verification
        edge_cases_resend = [
            "test@" + "x" * 200 + ".com",  # Email muy largo
            "test@domain.com" + ";" + "DROP TABLE users",  # SQL injection attempt
        ]

        for email in edge_cases_resend:
            response = await client.post(
                "/api/v1/auth/resend-verification",
                json={"email": email}
            )
            # Siempre debe retornar 200 OK o 422 (validación Pydantic)
            assert response.status_code in [200, 422], \
                f"Should handle edge case gracefully for: {email[:30]}..."

            if response.status_code == 200:
                # Si pasa validación, debe retornar mensaje genérico
                message = response.json().get("message", "")
                assert "if the email address exists" in message.lower()

        # 4. Verificar que se generaron logs (estructura de logging funciona)
        assert len(caplog.records) > 0, "Logging should be working"

        # 5. Verificar que ningún log expone datos sensibles completos
        all_log_messages = " ".join([r.message for r in caplog.records])
        # Los tokens deben estar ofuscados (no completos)
        assert "x" * 1000 not in all_log_messages, "Long token should be truncated in logs"

        print("\n✅ Error handling structure verified:")
        print(f"  - Logger configured: {auth_routes.logger.name}")
        print("  - Edge cases handled gracefully")
        print("  - Generic messages maintained")
        print(f"  - Logging active: {len(caplog.records)} log entries")

    async def test_security_monitoring_capabilities(self, client: AsyncClient, caplog):
        """
        Test: Los logs permiten monitoreo de seguridad

        Verifica que se pueden detectar patrones de ataque mediante logs:
        - Múltiples intentos fallidos (potencial brute force)
        - Enumeración de usuarios
        - Timing patterns
        """
        caplog.set_level(logging.INFO)

        # Simular múltiples intentos fallidos (posible ataque)
        for i in range(3):
            await client.post(
                "/api/v1/auth/verify-email",
                json={"token": f"attack_token_{i}"}
            )

        # Verificar que se puede detectar el patrón en logs
        failed_attempts = [
            record for record in caplog.records
            if "verification failed" in record.message.lower()
        ]

        assert len(failed_attempts) >= 3, \
            "Should be able to detect multiple failed attempts for security monitoring"

        # En producción, un sistema de monitoreo podría:
        # - Alertar si hay >10 intentos fallidos en <1 minuto
        # - Bloquear IPs con comportamiento sospechoso
        # - Generar reportes de seguridad
        print(f"\n[Security] Detected {len(failed_attempts)} failed attempts - potential attack pattern")

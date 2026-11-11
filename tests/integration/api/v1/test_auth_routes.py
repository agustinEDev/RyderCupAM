import pytest
from fastapi import status
from httpx import AsyncClient

from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes
from tests.conftest import (
    create_authenticated_user,
    get_user_by_email,
    token_de_reset_enviado,
    token_de_verificacion_enviado,
)

# Marcar todos los tests para ejecutarse con asyncio
pytestmark = pytest.mark.asyncio


class TestAuthRoutes:
    """
    Suite de tests de integración para las rutas de autenticación.
    """

    async def test_register_user_successfully(self, client: AsyncClient):
        """
        Verifica que un usuario puede registrarse correctamente a través del endpoint.
        Espera un código de estado 201 Created.
        """
        # Arrange
        user_data = {
            "email": "integration.test@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Integration",
            "last_name": "Test",
            "accept_terms": True,
        }

        # Act
        response = await client.post("/api/v1/auth/register", json=user_data)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["email"] == user_data["email"]
        assert response_data["first_name"] == user_data["first_name"]
        assert "id" in response_data

    async def test_register_with_an_existing_email_answers_the_same_201(self, client: AsyncClient):
        """
        Con un email que ya existe ya no hay 409 (fase 3, F-01): el mismo 201 que un alta
        nueva, sin decir que existe.
        """
        # Arrange: Primero, registrar un usuario.
        user_data = {
            "email": "conflict.test@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Conflict",
            "last_name": "Test",
            "accept_terms": True,
        }
        first_response = await client.post("/api/v1/auth/register", json=user_data)
        assert first_response.status_code == status.HTTP_201_CREATED

        # Act: Intentar registrarlo de nuevo con el mismo email.
        second_response = await client.post("/api/v1/auth/register", json=user_data)

        # Assert
        assert second_response.status_code == status.HTTP_201_CREATED
        assert "ya está registrado" not in second_response.text
        assert second_response.json()["id"] != first_response.json()["id"]

    @pytest.mark.parametrize(
        ("password", "motivo"),
        [
            # 12+ caracteres, así que Pydantic la deja pasar: la rechaza el VO
            ("Abcdefghijk1", "carácter especial"),
            (" Abcdefghi1!", "espacios"),
            ("abcdefghij1!", "mayúscula"),
        ],
    )
    async def test_register_with_a_password_that_breaks_the_policy_is_a_400(
        self, client: AsyncClient, password: str, motivo: str
    ):
        """
        Una contraseña fuera de la política es un 400 con el motivo, no un 500.

        `InvalidPasswordError` no era un `ValueError`, el router no la capturaba y
        el usuario veía «Error interno del servidor» en un toast.
        """
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"policy.{motivo.replace(' ', '')}@example.com",
                "password": password,
                "first_name": "Policy",
                "last_name": "Test",
                "accept_terms": True,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert motivo in response.json()["detail"]

    async def test_reset_with_a_password_without_symbol_carries_its_code_and_keeps_the_token(
        self, client: AsyncClient
    ):
        """
        Given un token de reseteo válido
        When se manda una contraseña sin símbolo
        Then 400 con `error_code` PASSWORD_NO_SYMBOL (BE #519) y el token sigue valiendo
        """
        email = "reset.policy@example.com"
        await create_authenticated_user(client, email, "V@l1dP@ss123!", "Reset", "Policy")
        await client.post("/api/v1/auth/forgot-password", json={"email": email})
        token = await token_de_reset_enviado(email)

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "Abcdefghijk1"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error_code"] == "PASSWORD_NO_SYMBOL"
        sigue = await client.post("/api/v1/auth/validate-reset-token", json={"token": token})
        assert sigue.json()["valid"] is True

    async def test_reset_with_an_unknown_token_carries_its_code(self, client: AsyncClient):
        """
        Given un token que no existe
        When se intenta resetear
        Then 400 con `error_code` RESET_TOKEN_INVALID: el cliente no puede reconocerlo
        por el texto, que va en español («inválido», no «invalid»)
        """
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "t" * 43, "new_password": "V@l1dP@ss123!"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error_code"] == "RESET_TOKEN_INVALID"

    async def test_register_with_a_common_password_carries_its_code(
        self, client: AsyncClient, monkeypatch
    ):
        """
        Given una contraseña de la lista de comunes que cumple todo lo demás
        When se registra
        Then 400 con `error_code` PASSWORD_TOO_COMMON en la raíz (BE #519), para traducirlo

        La lista negra se simula: aquí se prueba el código, no la lista (BE #518).
        """
        monkeypatch.setattr(
            "src.modules.user.domain.value_objects.password.is_common_password",
            lambda candidate: candidate == "Password123!",
        )
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "policy.common@example.com",
                "password": "Password123!",
                "first_name": "Policy",
                "last_name": "Test",
                "accept_terms": True,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error_code"] == "PASSWORD_TOO_COMMON"
        assert response.json()["detail"]

    async def test_logout_user_successfully(self, client: AsyncClient):
        """
        Verifica que un usuario autenticado puede hacer logout correctamente.
        """
        # Arrange: Crear y autenticar un usuario

        auth_data = await create_authenticated_user(
            client, "logout.test@example.com", "V@l1dP@ss123!", "Logout", "Test"
        )
        token = auth_data["token"]
        headers = {"Cookie": f"access_token={token}"}

        # Act: Hacer logout
        logout_data = {}  # LogoutRequestDTO está vacío en Fase 1
        response = await client.post("/api/v1/auth/logout", json=logout_data, headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["message"] == "Logout exitoso"
        assert "logged_out_at" in response_data

    async def test_logout_fails_without_authentication(self, client: AsyncClient):
        """
        Verifica que el logout falla si no se proporciona token de autenticación.
        """
        # Arrange
        logout_data = {}

        # Act: Intentar logout sin autenticación
        response = await client.post("/api/v1/auth/logout", json=logout_data)

        # Assert
        # Con HTTPOnly Cookies, devuelve 401 cuando no hay cookie de autenticación
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_logout_fails_with_invalid_token(self, client: AsyncClient):
        """
        Verifica que el logout falla con un token inválido.
        """
        # Arrange
        invalid_token = "invalid-jwt-token"
        headers = {"Cookie": f"access_token={invalid_token}"}
        logout_data = {}

        # Act: Intentar logout con token inválido
        response = await client.post("/api/v1/auth/logout", json=logout_data, headers=headers)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_verify_email_endpoint_success(self, client: AsyncClient):
        """
        Test: Verificar email exitosamente
        Given: Un usuario registrado con token de verificación
        When: Se llama al endpoint con el token correcto
        Then: Retorna 200 OK, un JWT y el usuario autenticado con email verificado
        """
        # Arrange - Registrar usuario
        user_data = {
            "email": "verify.success@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Verify",
            "last_name": "Success",
            "accept_terms": True,
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener el token de verificación desde la BD (en un escenario real vendría por email)

        verification_token = await token_de_verificacion_enviado(user_data["email"])

        # Act - Verificar email
        verify_data = {"token": verification_token}
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        # Solo verifica, sin sesión (BE #753)
        assert response_data["email_verified"] is True
        assert "access_token" not in response_data

    async def test_verify_email_endpoint_invalid_token(self, client: AsyncClient):
        """
        Test: Verificar email con token inválido
        Given: Un token que no existe
        When: Se llama al endpoint
        Then: Retorna 400 Bad Request con mensaje genérico (seguridad)
        """
        # Arrange
        verify_data = {"token": "invalid_token_that_does_not_exist"}

        # Act
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Verificar mensaje genérico (no revela información específica)
        assert "unable to verify email" in response.json()["detail"].lower()

    async def test_verify_email_endpoint_empty_token(self, client: AsyncClient):
        """
        Test: Verificar email con token vacío
        Given: Un token vacío
        When: Se llama al endpoint
        Then: Retorna 422 Unprocessable Entity (error de validación de Pydantic)
        """
        # Arrange
        verify_data = {"token": ""}

        # Act
        response = await client.post("/api/v1/auth/verify-email", json=verify_data)

        # Assert
        # FastAPI retorna 422 para errores de validación de Pydantic
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_verify_email_endpoint_already_verified(self, client: AsyncClient):
        """
        Test: Intentar verificar email ya verificado
        Given: Un usuario con email ya verificado
        When: Se intenta verificar de nuevo
        Then: Retorna 400 Bad Request
        """
        # Arrange - Registrar y verificar usuario
        user_data = {
            "email": "already.verified@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Already",
            "last_name": "Verified",
            "accept_terms": True,
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener token y verificar primera vez

        verification_token = await token_de_verificacion_enviado(user_data["email"])

        verify_data = {"token": verification_token}
        first_verify = await client.post("/api/v1/auth/verify-email", json=verify_data)
        assert first_verify.status_code == status.HTTP_200_OK

        # Act - Intentar verificar de nuevo con cualquier token
        verify_data_again = {"token": "any_token"}
        response = await client.post("/api/v1/auth/verify-email", json=verify_data_again)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_resend_verification_email_endpoint_success(self, client: AsyncClient):
        """
        Test: Reenviar email de verificación exitosamente
        Given: Un usuario registrado sin verificar
        When: Con su sesión, se llama al endpoint con su email
        Then: Retorna 200 OK y se genera nuevo token
        """
        # Arrange - Registrar usuario
        user_data = {
            "email": "resend.success@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Resend",
            "last_name": "Success",
            "accept_terms": True,
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Obtener el token original

        # La BD guarda el SHA-256 del token (fase 3): se compara ese hash
        user_before = await get_user_by_email(client, user_data["email"])
        original_token = user_before.verification_token
        assert original_token is not None

        # Act - Reenviar email de verificación con sesión: el reenvío por correo es el de
        # la propia cuenta (fase 3). Sale en segundo plano y se guarda al salir
        await client.post(
            "/api/v1/auth/login",
            json={"email": user_data["email"], "password": user_data["password"]},
        )
        resend_data = {"email": user_data["email"]}
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)
        await espera_los_avisos_pendientes(tope_s=10)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["email"] == user_data["email"]
        # Mensaje genérico por seguridad
        assert "if the email address exists" in response_data["message"].lower()

        # Verificar que se generó un nuevo token
        user_after = await get_user_by_email(client, user_data["email"])
        assert user_after.verification_token != original_token
        assert user_after.email_verified is False

    async def test_resend_verification_email_endpoint_nonexistent_email(self, client: AsyncClient):
        """
        Test: Reenviar verificación con email no existente
        Given: Un email que no existe en la BD
        When: Se llama al endpoint
        Then: Retorna 200 OK con mensaje genérico (por seguridad, no revela que no existe)
        """
        # Arrange
        resend_data = {"email": "noexiste@example.com"}

        # Act
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)

        # Assert
        # Por seguridad, siempre retorna 200 OK con mensaje genérico
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "if the email address exists" in response_data["message"].lower()

    async def test_resend_verification_email_endpoint_already_verified(self, client: AsyncClient):
        """
        Test: Reenviar verificación a email ya verificado
        Given: Un usuario con email ya verificado
        When: Se intenta reenviar verificación
        Then: Retorna 200 OK con mensaje genérico (por seguridad, no revela que ya está verificado)
        """
        # Arrange - Registrar y verificar usuario
        user_data = {
            "email": "verified.resend@example.com",
            "password": "V@l1dP@ss123!",
            "first_name": "Verified",
            "last_name": "Resend",
            "accept_terms": True,
        }
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == status.HTTP_201_CREATED

        # Verificar el email

        verification_token = await token_de_verificacion_enviado(user_data["email"])

        verify_data = {"token": verification_token}
        verify_response = await client.post("/api/v1/auth/verify-email", json=verify_data)
        assert verify_response.status_code == status.HTTP_200_OK

        # Act - Intentar reenviar verificación
        resend_data = {"email": user_data["email"]}
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)

        # Assert
        # Por seguridad, siempre retorna 200 OK con mensaje genérico
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert "if the email address exists" in response_data["message"].lower()

    async def test_resend_verification_email_endpoint_invalid_email_format(
        self, client: AsyncClient
    ):
        """
        Test: Reenviar verificación con formato de email inválido
        Given: Un email con formato inválido
        When: Se llama al endpoint
        Then: Retorna 422 Unprocessable Entity
        """
        # Arrange
        resend_data = {"email": "invalid-email-format"}

        # Act
        response = await client.post("/api/v1/auth/resend-verification", json=resend_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_login_with_short_password_returns_generic_error(self, client: AsyncClient):
        """
        Verifica que el login con contraseña corta devuelve "Credenciales incorrectas"
        en lugar de revelar información sobre validaciones de contraseña.

        Esto es importante por seguridad: no debemos revelar reglas de validación
        de contraseñas en el endpoint de login.
        """
        # Arrange
        login_data = {
            "email": "any@example.com",
            "password": "short",  # Contraseña de solo 5 caracteres (< 8 requeridos)
        }

        # Act
        response = await client.post("/api/v1/auth/login", json=login_data)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        response_data = response.json()
        assert response_data["detail"] == "Credenciales incorrectas"
        # NO debe contener información sobre validación de longitud
        assert "8 characters" not in response_data["detail"]
        assert "min_length" not in response_data["detail"]
        assert "password" not in response_data["detail"].lower()


class TestValidateResetTokenMalformed:
    """
    BE #453: un token con una longitud imposible daba 500 y un evento de error
    en Sentry, porque la ruta construye el DTO (32-100 caracteres) dentro del
    manejador. La ruta promete responder siempre 200 con valid=True/False, y un
    token mal formado no es más que un token inválido.

        #   token                      | respuesta
        ----|---------------------------|-------------------------------------
        M1  15 caracteres (corto)      | 200, valid=False, el mensaje de siempre
        M2  101 caracteres (largo)     | 200, valid=False, el mensaje de siempre
        M3  48 caracteres desconocido  | 200, valid=False (lo que ya hacía)
    """

    MENSAJE_INVALIDO = "Token de reseteo inválido o expirado. Solicita un nuevo enlace."

    @pytest.mark.parametrize(
        "token",
        ["token-falso-123", "a" * 101, "b" * 48],
        ids=["M1-corto", "M2-largo", "M3-desconocido"],
    )
    async def test_a_malformed_token_is_just_invalid(self, client: AsyncClient, token: str):
        """
        GIVEN: Un token de reseteo que no existe, con cualquier longitud
        WHEN: Se valida con POST /api/v1/auth/validate-reset-token
        THEN: 200 con valid=False y el mismo mensaje que cualquier token
              inválido: la longitud no revela nada distinto
        """
        response = await client.post("/api/v1/auth/validate-reset-token", json={"token": token})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"valid": False, "message": self.MENSAJE_INVALIDO}


class TestVerifyEmailNoTokenInLogs:
    async def test_verify_email_does_not_log_any_part_of_the_token(
        self, client: AsyncClient, caplog
    ):
        """
        Given: Una verificación de email con un token cualquiera
        When: Se intenta verificar
        Then: Ni el token ni su principio salen en el log: con LoggingIntegration a INFO,
              iban a las migas de Sentry (auditoría OWASP, A09, 5 nov 2026)
        """
        import logging

        token = "ZzTokenDePrueba-0123456789abcdef"
        with caplog.at_level(logging.DEBUG):
            await client.post("/api/v1/auth/verify-email", json={"token": token})

        assert token[:8] not in caplog.text

"""
Tests para RefreshToken Entity.

Tests unitarios para la entidad de dominio RefreshToken, que representa
tokens de renovación para autenticación (Session Timeout v1.8.0).

Arquitectura:
- Capa: Unit Tests (Domain)
- Módulo: User
- Feature: Session Timeout with Refresh Tokens (OWASP A01/A02/A07)
"""
import pytest
from datetime import datetime, timedelta

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.domain.value_objects.token_hash import TokenHash
from src.modules.user.domain.value_objects.user_id import UserId


class TestRefreshTokenCreation:
    """Tests para creación de RefreshToken."""

    def test_create_factory_method_generates_valid_token(self):
        """
        Test: El factory method create() genera un RefreshToken válido.

        Given: Un user_id y un token JWT
        When: Se llama a RefreshToken.create()
        Then:
            - Retorna un RefreshToken con ID único generado
            - Token hash es SHA256 del JWT
            - Expira en 7 días por defecto
            - No está revocado
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"

        # When
        refresh_token = RefreshToken.create(user_id, token_jwt)

        # Then
        assert refresh_token.id is not None
        assert isinstance(refresh_token.id, RefreshTokenId)
        assert refresh_token.user_id == user_id
        assert refresh_token.token_hash.verify(token_jwt)
        assert refresh_token.revoked is False
        assert refresh_token.revoked_at is None
        assert refresh_token.created_at <= datetime.now()

        # Verificar expiración (7 días)
        expected_expiry = datetime.now() + timedelta(days=7)
        assert refresh_token.expires_at <= expected_expiry + timedelta(seconds=1)
        assert refresh_token.expires_at >= expected_expiry - timedelta(seconds=1)

    def test_create_with_custom_expiration_days(self):
        """
        Test: create() acepta días de expiración personalizados.

        Given: Un user_id, token JWT y expires_in_days=30
        When: Se llama a RefreshToken.create(user_id, token, expires_in_days=30)
        Then: El token expira en 30 días
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.custom"
        expires_in_days = 30

        # When
        refresh_token = RefreshToken.create(
            user_id,
            token_jwt,
            expires_in_days=expires_in_days
        )

        # Then
        expected_expiry = datetime.now() + timedelta(days=expires_in_days)
        assert refresh_token.expires_at <= expected_expiry + timedelta(seconds=1)
        assert refresh_token.expires_at >= expected_expiry - timedelta(seconds=1)

    def test_create_hashes_token_with_sha256(self):
        """
        Test: create() hashea el token con SHA256 (no almacena texto plano).

        Given: Un token JWT en texto plano
        When: Se crea RefreshToken con create()
        Then: El token_hash es SHA256 del JWT
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.plaintext"

        # When
        refresh_token = RefreshToken.create(user_id, token_jwt)

        # Then
        # No podemos verificar el hash directamente, pero podemos verificar con verify()
        assert refresh_token.token_hash.verify(token_jwt)
        # Hash debe tener longitud de SHA256 (64 caracteres hex)
        assert len(refresh_token.token_hash.value) == 64


class TestRefreshTokenValidation:
    """Tests para validación de RefreshToken."""

    def test_is_valid_returns_true_for_valid_token(self):
        """
        Test: is_valid() retorna True para token válido.

        Given: Un RefreshToken recién creado (no revocado, no expirado)
        When: Se llama a is_valid() con el token JWT correcto
        Then: Retorna True
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.valid_token"
        refresh_token = RefreshToken.create(user_id, token_jwt)

        # When
        result = refresh_token.is_valid(token_jwt)

        # Then
        assert result is True

    def test_is_valid_returns_false_for_revoked_token(self):
        """
        Test: is_valid() retorna False para token revocado.

        Given: Un RefreshToken revocado
        When: Se llama a is_valid()
        Then: Retorna False (aunque el hash coincida y no esté expirado)
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.revoked_token"
        refresh_token = RefreshToken.create(user_id, token_jwt)
        refresh_token.revoke()

        # When
        result = refresh_token.is_valid(token_jwt)

        # Then
        assert result is False

    def test_is_valid_returns_false_for_expired_token(self):
        """
        Test: is_valid() retorna False para token expirado.

        Given: Un RefreshToken con expiración en el pasado
        When: Se llama a is_valid()
        Then: Retorna False
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.expired_token"
        token_hash = TokenHash.from_token(token_jwt)

        # Token expirado hace 1 día
        expires_at = datetime.now() - timedelta(days=1)
        refresh_token = RefreshToken(
            id=RefreshTokenId.generate(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        # When
        result = refresh_token.is_valid(token_jwt)

        # Then
        assert result is False

    def test_is_valid_returns_false_for_wrong_token(self):
        """
        Test: is_valid() retorna False cuando el token no coincide.

        Given: Un RefreshToken creado con un token JWT
        When: Se llama a is_valid() con un token JWT diferente
        Then: Retorna False
        """
        # Given
        user_id = UserId.generate()
        original_token = "eyJhbGciOiJIUzI1NiJ9.original"
        wrong_token = "eyJhbGciOiJIUzI1NiJ9.wrong"
        refresh_token = RefreshToken.create(user_id, original_token)

        # When
        result = refresh_token.is_valid(wrong_token)

        # Then
        assert result is False


class TestRefreshTokenRevocation:
    """Tests para revocación de RefreshToken."""

    def test_revoke_marks_token_as_revoked(self):
        """
        Test: revoke() marca el token como revocado.

        Given: Un RefreshToken válido
        When: Se llama a revoke()
        Then:
            - revoked es True
            - revoked_at contiene timestamp
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.to_revoke"
        refresh_token = RefreshToken.create(user_id, token_jwt)

        # Verificar estado inicial
        assert refresh_token.revoked is False
        assert refresh_token.revoked_at is None

        # When
        refresh_token.revoke()

        # Then
        assert refresh_token.revoked is True
        assert refresh_token.revoked_at is not None
        assert refresh_token.revoked_at <= datetime.now()

    def test_revoke_is_idempotent(self):
        """
        Test: Llamar revoke() múltiples veces no causa errores.

        Given: Un RefreshToken revocado
        When: Se llama a revoke() de nuevo
        Then: No se modifica revoked_at (conserva la primera fecha)
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.idempotent"
        refresh_token = RefreshToken.create(user_id, token_jwt)

        refresh_token.revoke()
        first_revoked_at = refresh_token.revoked_at

        # When - Esperar un momento para asegurar timestamp diferente
        import time
        time.sleep(0.01)
        refresh_token.revoke()

        # Then - revoked_at debe ser el mismo (no actualiza)
        assert refresh_token.revoked_at == first_revoked_at


class TestRefreshTokenExpiration:
    """Tests para expiración de RefreshToken."""

    def test_is_expired_returns_false_for_future_expiration(self):
        """
        Test: is_expired() retorna False para token con expiración futura.

        Given: Un RefreshToken que expira en 7 días
        When: Se llama a is_expired()
        Then: Retorna False
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.future"
        refresh_token = RefreshToken.create(user_id, token_jwt, expires_in_days=7)

        # When
        result = refresh_token.is_expired()

        # Then
        assert result is False

    def test_is_expired_returns_true_for_past_expiration(self):
        """
        Test: is_expired() retorna True para token expirado.

        Given: Un RefreshToken con expiración en el pasado
        When: Se llama a is_expired()
        Then: Retorna True
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.past"
        token_hash = TokenHash.from_token(token_jwt)

        expires_at = datetime.now() - timedelta(days=1)
        refresh_token = RefreshToken(
            id=RefreshTokenId.generate(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        # When
        result = refresh_token.is_expired()

        # Then
        assert result is True

    def test_is_expired_boundary_condition_exactly_now(self):
        """
        Test: is_expired() maneja correctamente expiración exacta en este momento.

        Given: Un RefreshToken que expira exactamente ahora (±1 segundo)
        When: Se llama a is_expired()
        Then: Retorna True (expiró justo ahora)
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.boundary"
        token_hash = TokenHash.from_token(token_jwt)

        # Expiración exactamente ahora (o hace 1 segundo para evitar race condition)
        expires_at = datetime.now() - timedelta(seconds=1)
        refresh_token = RefreshToken(
            id=RefreshTokenId.generate(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        # When
        result = refresh_token.is_expired()

        # Then
        assert result is True


class TestRefreshTokenEquality:
    """Tests para igualdad y hashing de RefreshToken."""

    def test_equality_compares_by_id(self):
        """
        Test: Dos RefreshTokens son iguales si tienen el mismo ID.

        Given: Dos RefreshTokens con el mismo ID pero diferentes datos
        When: Se comparan con ==
        Then: Son iguales
        """
        # Given
        token_id = RefreshTokenId.generate()
        user_id1 = UserId.generate()
        user_id2 = UserId.generate()

        token_hash = TokenHash.from_token("token")
        expires_at = datetime.now() + timedelta(days=7)

        token1 = RefreshToken(
            id=token_id,
            user_id=user_id1,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        token2 = RefreshToken(
            id=token_id,
            user_id=user_id2,  # Usuario diferente, pero mismo ID
            token_hash=token_hash,
            expires_at=expires_at,
        )

        # When / Then
        assert token1 == token2

    def test_inequality_for_different_ids(self):
        """
        Test: Dos RefreshTokens con IDs diferentes no son iguales.

        Given: Dos RefreshTokens con IDs diferentes
        When: Se comparan con ==
        Then: No son iguales
        """
        # Given
        user_id = UserId.generate()
        token_hash = TokenHash.from_token("token")
        expires_at = datetime.now() + timedelta(days=7)

        token1 = RefreshToken(
            id=RefreshTokenId.generate(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        token2 = RefreshToken(
            id=RefreshTokenId.generate(),  # ID diferente
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        # When / Then
        assert token1 != token2

    def test_hash_allows_use_in_sets(self):
        """
        Test: RefreshToken puede usarse en sets (implementa __hash__).

        Given: Dos RefreshTokens diferentes
        When: Se añaden a un set
        Then: El set contiene ambos tokens
        """
        # Given
        user_id = UserId.generate()
        token1 = RefreshToken.create(user_id, "token1")
        token2 = RefreshToken.create(user_id, "token2")

        # When
        token_set = {token1, token2}

        # Then
        assert len(token_set) == 2
        assert token1 in token_set
        assert token2 in token_set


class TestRefreshTokenRepresentation:
    """Tests para representación string de RefreshToken."""

    def test_repr_includes_id_user_id_and_status(self):
        """
        Test: __repr__ incluye ID, user_id y status del token.

        Given: Un RefreshToken válido
        When: Se convierte a string con repr()
        Then: Incluye id, user_id y status="valid"
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.repr_test"
        refresh_token = RefreshToken.create(user_id, token_jwt)

        # When
        repr_str = repr(refresh_token)

        # Then
        assert "RefreshToken" in repr_str
        assert str(refresh_token.id.value) in repr_str
        assert str(user_id.value) in repr_str
        assert "status=valid" in repr_str

    def test_repr_shows_revoked_status(self):
        """
        Test: __repr__ muestra "revoked" para token revocado.

        Given: Un RefreshToken revocado
        When: Se convierte a string con repr()
        Then: status="revoked"
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.revoked_repr"
        refresh_token = RefreshToken.create(user_id, token_jwt)
        refresh_token.revoke()

        # When
        repr_str = repr(refresh_token)

        # Then
        assert "status=revoked" in repr_str

    def test_repr_shows_expired_status(self):
        """
        Test: __repr__ muestra "expired" para token expirado.

        Given: Un RefreshToken expirado
        When: Se convierte a string con repr()
        Then: status="expired"
        """
        # Given
        user_id = UserId.generate()
        token_jwt = "eyJhbGciOiJIUzI1NiJ9.expired_repr"
        token_hash = TokenHash.from_token(token_jwt)

        expires_at = datetime.now() - timedelta(days=1)
        refresh_token = RefreshToken(
            id=RefreshTokenId.generate(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        # When
        repr_str = repr(refresh_token)

        # Then
        assert "status=expired" in repr_str

"""
Tests para UnlinkGoogleAccountUseCase

Tests unitarios para el caso de uso de desvincular cuenta Google.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.oauth_dto import UnlinkGoogleAccountRequestDTO
from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def auditoria():
    """El log de seguridad, simulado."""
    return MagicMock()


@pytest.fixture
def correos():
    """El servicio de correo, simulado."""
    return AsyncMock()


@pytest.fixture
def use_case(uow, auditoria, correos):
    return UnlinkGoogleAccountUseCase(uow=uow, email_service=correos, security_audit=auditoria)


@pytest.fixture
async def user_with_password(uow):
    """Usuario con password Y cuenta Google vinculada."""
    user = User.create(
        first_name="Has",
        last_name="Password",
        email_str="password@example.com",
        plain_password="V@l1dP@ss123!",
    )
    async with uow:
        await uow.users.save(user)

    oauth = UserOAuthAccount.create(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-unlink-123",
        provider_email="password@gmail.com",
    )
    async with uow:
        await uow.oauth_accounts.save(oauth)

    return user


@pytest.fixture
async def oauth_only_user(uow):
    """Usuario sin password (creado via OAuth)."""
    user = User.create_from_oauth(
        first_name="OAuth",
        last_name="Only",
        email_str="oauthonly@example.com",
    )
    async with uow:
        await uow.users.save(user)

    oauth = UserOAuthAccount.create(
        user_id=user.id,
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-oauth-only",
        provider_email="oauthonly@gmail.com",
    )
    async with uow:
        await uow.oauth_accounts.save(oauth)

    return user


@pytest.mark.asyncio
class TestUnlinkGoogleAccountUseCase:
    """Tests para desvincular cuenta Google."""

    async def test_unlink_google_account_successfully(self, use_case, uow, user_with_password):
        """Debe desvincular Google cuando el usuario tiene password."""
        response = await use_case.execute(
            UnlinkGoogleAccountRequestDTO(user_id=str(user_with_password.id.value)),
            reautenticado=True,
        )

        assert response.message == "Google account unlinked successfully"
        assert response.provider == "google"

        # Verificar que ya no existe la OAuth account
        oauth = await uow.oauth_accounts.find_by_user_id_and_provider(
            user_with_password.id, OAuthProvider.GOOGLE
        )
        assert oauth is None

    async def test_unlink_fails_when_no_google_linked(self, use_case, uow):
        """Debe fallar si el usuario no tiene cuenta Google vinculada."""
        user = User.create(
            first_name="No",
            last_name="Google",
            email_str="nogoogle@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(user)

        with pytest.raises(ValueError, match="No Google account linked"):
            await use_case.execute(
                UnlinkGoogleAccountRequestDTO(user_id=str(user.id.value)), reautenticado=True
            )

    async def test_unlink_fails_when_oauth_only_user(self, use_case, oauth_only_user):
        """Debe fallar si el usuario no tiene password (único método auth)."""
        with pytest.raises(ValueError, match="only authentication method"):
            await use_case.execute(
                UnlinkGoogleAccountRequestDTO(user_id=str(oauth_only_user.id.value)),
                reautenticado=True,
            )

    async def test_unlink_fails_when_user_not_found(self, use_case, uow):
        """Debe fallar cuando el usuario no existe."""
        # Crear OAuth account sin usuario correspondiente
        from src.modules.user.domain.value_objects.user_id import UserId

        fake_id = UserId.generate()
        oauth = UserOAuthAccount.create(
            user_id=fake_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-fake",
            provider_email="fake@gmail.com",
        )
        async with uow:
            await uow.oauth_accounts.save(oauth)

        with pytest.raises(ValueError, match="User not found"):
            await use_case.execute(
                UnlinkGoogleAccountRequestDTO(user_id=str(fake_id.value)), reautenticado=True
            )

    async def test_unlink_emits_domain_event(self, use_case, user_with_password):
        """Debe emitir GoogleAccountUnlinkedEvent en el usuario."""
        await use_case.execute(
            UnlinkGoogleAccountRequestDTO(user_id=str(user_with_password.id.value)),
            reautenticado=True,
        )

        from src.modules.user.domain.events.google_account_unlinked_event import (
            GoogleAccountUnlinkedEvent,
        )

        events = user_with_password.get_domain_events()
        unlinked_events = [e for e in events if isinstance(e, GoogleAccountUnlinkedEvent)]
        assert len(unlinked_events) == 1
        assert unlinked_events[0].provider == "google"


@pytest.mark.asyncio
async def test_the_google_link_is_looked_up_after_locking_the_account():
    """
    Given: Una cuenta con su Google
    When: Se desvincula
    Then: El vínculo se busca con la fila ya bloqueada: dos desvinculaciones a la vez no
          dicen las dos «hecho» (CodeRabbit en #752)
    """
    from src.modules.user.application.use_cases.unlink_google_account_use_case import (
        UnlinkGoogleAccountUseCase,
    )
    from src.modules.user.domain.entities.user import User
    from src.modules.user.domain.entities.user_oauth_account import UserOAuthAccount
    from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
    from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
        InMemoryUnitOfWork,
    )

    uow = InMemoryUnitOfWork()
    ana = User.create(
        first_name="Ana",
        last_name="Dueña",
        email_str="ana@example.com",
        plain_password="SecureP@ssw0rd123!",
    )
    async with uow:
        await uow.users.save(ana)
        await uow.oauth_accounts.save(
            UserOAuthAccount.create(
                user_id=ana.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id="g",
                provider_email="ana@example.com",
            )
        )
    orden = []
    bloqueo, busca = (
        uow.users.find_by_id_for_update,
        uow.oauth_accounts.find_by_user_id_and_provider,
    )

    async def espia_bloqueo(user_id):
        orden.append("bloqueo")
        return await bloqueo(user_id)

    async def espia_busca(*a):
        orden.append("busca")
        return await busca(*a)

    uow.users.find_by_id_for_update = espia_bloqueo
    uow.oauth_accounts.find_by_user_id_and_provider = espia_busca

    await UnlinkGoogleAccountUseCase(
        uow, email_service=AsyncMock(), security_audit=MagicMock()
    ).execute(UnlinkGoogleAccountRequestDTO(user_id=str(ana.id.value)), reautenticado=True)

    assert orden == ["bloqueo", "busca"]


@pytest.mark.asyncio
class TestUnlinkGoesToTheSecurityLog:
    """Desvincular Google deja rastro en el log de seguridad, como vincularlo."""

    async def test_unlink_with_google_linked_logs_the_network(
        self, use_case, user_with_password, auditoria
    ):
        """
        Given: Un usuario con contraseña y Google vinculado
        When: Desvincula Google, con la IP y el navegador de la petición
        Then: Una sola entrada en el log, con su id y su red
        """
        await use_case.execute(
            UnlinkGoogleAccountRequestDTO(
                user_id=str(user_with_password.id.value),
                ip_address="203.0.113.7",
                user_agent="Safari",
            ),
            reautenticado=True,
        )

        auditoria.log_google_account_unlinked.assert_called_once_with(
            user_id=str(user_with_password.id.value),
            ip_address="203.0.113.7",
            user_agent="Safari",
        )

    async def test_unlink_successful_logs_after_the_commit(
        self, use_case, uow, user_with_password, auditoria
    ):
        """
        Given: Un usuario con contraseña y Google vinculado
        When: Desvincula Google
        Then: El log se escribe después del commit, con el Google ya borrado
        """

        async def sigue_vinculado():
            async with uow:
                return await uow.oauth_accounts.find_by_user_id_and_provider(
                    user_with_password.id, OAuthProvider.GOOGLE
                )

        estados = []
        auditoria.log_google_account_unlinked.side_effect = lambda **_kw: estados.append("log")
        borrar = uow.oauth_accounts.delete
        confirmar = uow.commit

        async def espia_borrar(cuenta):
            estados.append("borra")
            return await borrar(cuenta)

        async def espia_confirmar():
            estados.append("commit")
            return await confirmar()

        uow.oauth_accounts.delete = espia_borrar
        uow.commit = espia_confirmar

        await use_case.execute(
            UnlinkGoogleAccountRequestDTO(user_id=str(user_with_password.id.value)),
            reautenticado=True,
        )

        # Tras el commit, no solo tras el borrado: un log dentro de la transacción
        # apuntaría una desvinculación que aún podría deshacerse
        assert estados.index("borra") < estados.index("commit") < estados.index("log")
        assert await sigue_vinculado() is None

    async def test_unlink_without_network_data_logs_unknown(
        self, use_case, user_with_password, auditoria
    ):
        """
        Given: Un uso del caso de uso sin IP ni navegador
        When: Desvincula Google
        Then: Al log igual, con «unknown» en la red
        """
        await use_case.execute(
            UnlinkGoogleAccountRequestDTO(user_id=str(user_with_password.id.value)),
            reautenticado=True,
        )

        auditoria.log_google_account_unlinked.assert_called_once_with(
            user_id=str(user_with_password.id.value),
            ip_address="unknown",
            user_agent="unknown",
        )

    async def test_unlink_without_google_linked_logs_nothing(self, use_case, uow, auditoria):
        """
        Given: Un usuario sin Google vinculado
        When: Intenta desvincular
        Then: Rechazado, y nada de «desvinculado» en el log
        """
        user = User.create(
            first_name="No",
            last_name="Google",
            email_str="nogoogle.log@example.com",
            plain_password="V@l1dP@ss123!",
        )
        async with uow:
            await uow.users.save(user)

        with pytest.raises(ValueError, match="No Google account linked"):
            await use_case.execute(
                UnlinkGoogleAccountRequestDTO(user_id=str(user.id.value), ip_address="203.0.113.7"),
                reautenticado=True,
            )

        auditoria.log_google_account_unlinked.assert_not_called()

    async def test_unlink_with_google_as_only_login_logs_nothing(
        self, use_case, oauth_only_user, auditoria
    ):
        """
        Given: Un usuario sin contraseña (Google es su única forma de entrar)
        When: Intenta desvincular
        Then: Rechazado, y nada de «desvinculado» en el log
        """
        with pytest.raises(ValueError, match="only authentication method"):
            await use_case.execute(
                UnlinkGoogleAccountRequestDTO(user_id=str(oauth_only_user.id.value)),
                reautenticado=True,
            )

        auditoria.log_google_account_unlinked.assert_not_called()

    async def test_unlink_with_broken_log_still_unlinks_and_notifies(
        self, use_case, uow, user_with_password, auditoria, correos
    ):
        """
        Given: Una cuenta verificada (a esa le sale el aviso) y un log de seguridad que falla
        When: Desvincula Google
        Then: Desvinculado igual, con su respuesta y el correo de aviso
        """
        user_with_password.confirm_email_ownership()
        async with uow:
            await uow.users.save(user_with_password)
        auditoria.log_google_account_unlinked.side_effect = RuntimeError("log caído")

        respuesta = await use_case.execute(
            UnlinkGoogleAccountRequestDTO(user_id=str(user_with_password.id.value)),
            reautenticado=True,
        )

        assert respuesta.message == "Google account unlinked successfully"
        async with uow:
            assert (
                await uow.oauth_accounts.find_by_user_id_and_provider(
                    user_with_password.id, OAuthProvider.GOOGLE
                )
                is None
            )
        correos.send_google_account_notice.assert_awaited_once()


@pytest.mark.asyncio
async def test_unlink_with_none_network_data_writes_the_real_line(
    uow, correos, user_with_password, tmp_path, monkeypatch
):
    """
    Given: Una petición sin User-Agent válido ni IP (la ruta recibe None de sus helpers,
           como con curl sin cabecera) y el log de seguridad DE VERDAD, no un doble
    When: Desvincula Google
    Then: La línea GOOGLE UNLINKED se escribe, con «unknown» en la red: un None no
          puede tumbar el evento y dejar la desvinculación sin rastro (revisión)
    """
    from src.modules.user.infrastructure.security import security_audit_logger as adaptador
    from src.modules.user.infrastructure.security.security_audit_logger import (
        SecurityAuditLogger,
    )
    from src.shared.infrastructure.logging.security_logger import SecurityLogger

    log = SecurityLogger(log_dir=tmp_path, log_file="unlink.log")
    monkeypatch.setattr(adaptador, "get_security_logger", lambda: log)
    caso = UnlinkGoogleAccountUseCase(
        uow=uow, email_service=correos, security_audit=SecurityAuditLogger()
    )

    await caso.execute(
        UnlinkGoogleAccountRequestDTO(
            user_id=str(user_with_password.id.value), ip_address=None, user_agent=None
        ),
        reautenticado=True,
    )

    import json

    log.vacia()  # lo escribe el hilo del log
    escrito = (tmp_path / "unlink.log").read_text()
    assert f"GOOGLE UNLINKED | User {user_with_password.id.value}" in escrito
    evento = json.loads(escrito.strip().split("\n")[-1])["extra"]["security_event"]
    assert evento["user_agent"] == "unknown"
    assert evento["ip_address"] == "unknown"


@pytest.mark.asyncio
async def test_unlink_without_reauthentication_is_refused_before_reading_anything(
    uow, auditoria, correos, user_with_password
):
    """
    Given: Un usuario con contraseña y Google vinculado, sin la marca de contraseña
    When: Intenta desvincular Google
    Then: ReauthenticationRequiredError antes de leer nada (D4: el 403 no dice si hay
          Google), el Google sigue, sin log de desvinculado ni correo
    """
    from src.modules.user.application.use_cases.link_google_account_use_case import (
        ReauthenticationRequiredError,
    )

    leidas = []
    bloqueo = uow.users.find_by_id_for_update

    async def espia(user_id):
        leidas.append(user_id)
        return await bloqueo(user_id)

    uow.users.find_by_id_for_update = espia
    caso = UnlinkGoogleAccountUseCase(uow=uow, email_service=correos, security_audit=auditoria)

    with pytest.raises(ReauthenticationRequiredError):
        await caso.execute(UnlinkGoogleAccountRequestDTO(user_id=str(user_with_password.id.value)))

    assert leidas == []
    async with uow:
        assert (
            await uow.oauth_accounts.find_by_user_id_and_provider(
                user_with_password.id, OAuthProvider.GOOGLE
            )
            is not None
        )
    auditoria.log_google_account_unlinked.assert_not_called()
    correos.send_google_account_notice.assert_not_awaited()

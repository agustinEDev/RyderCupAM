"""
El cambio de correo, pendiente hasta confirmarlo desde la dirección nueva (#749).

  #   Caso                                         | Resultado
  ----|----------------------------------------------|----------------------------------
  E1  pedirlo en Seguridad                         | sigue el correo de antes; el nuevo,
                                                   |   pendiente; enlace al nuevo y aviso
                                                   |   al viejo; la fila, bloqueada
  E2  confirmar con su token                       | el correo es el nuevo, verificado
  E3  confirmar pasadas las 24 h                   | EmailChangeExpiredError y el
                                                   |   pendiente anulado (guardado)
  E4  el nuevo ya lo tiene otra cuenta al confirmar| EmailChangeEmailInUseError, sin cambio
  E6  anular                                       | sin pendiente
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import UpdateSecurityRequestDTO
from src.modules.user.application.use_cases.cancel_email_change_use_case import (
    CancelEmailChangeUseCase,
)
from src.modules.user.application.use_cases.confirm_email_change_use_case import (
    ConfirmEmailChangeUseCase,
)
from src.modules.user.application.use_cases.update_security_use_case import (
    UpdateSecurityUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions import (
    EmailChangeEmailInUseError,
    EmailChangeExpiredError,
    EmailChangeInvalidError,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

CLAVE = "SecureP@ssw0rd123!"


async def _ana(uow) -> User:
    ana = User.create(
        first_name="Ana", last_name="Dueña", email_str="ana@gmail.com", plain_password=CLAVE
    )
    ana.confirm_email_ownership()
    async with uow:
        await uow.users.save(ana)
    return ana


async def _pide(uow, ana, correos=None):
    correos = correos or AsyncMock()
    respuesta = await UpdateSecurityUseCase(uow, correos).execute(
        str(ana.id.value),
        UpdateSecurityRequestDTO(current_password=CLAVE, new_email="ana@trabajo.com"),
    )
    return respuesta, correos


async def test_e1_asking_keeps_the_old_email_and_sends_both_mails():
    """
    Given: Ana, verificada, con ana@gmail.com
    When: Pide en Seguridad cambiarlo a ana@trabajo.com
    Then: La respuesta y la cuenta siguen con ana@gmail.com (verificada) y el nuevo
          pendiente; el enlace va al nuevo y el aviso al viejo
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)

    respuesta, correos = await _pide(uow, ana)

    assert respuesta.user.email == "ana@gmail.com"
    assert respuesta.user.email_verified is True
    assert respuesta.user.pending_email == "ana@trabajo.com"
    confirmacion = correos.send_email_change_confirmation.await_args.kwargs
    assert confirmacion["to_email"] == "ana@trabajo.com"
    async with uow:
        guardada = await uow.users.find_by_id(ana.id)
    assert guardada.pending_email_token_matches(confirmacion["token"])
    aviso = correos.send_email_change_requested_notice.await_args.kwargs
    assert aviso["to_email"] == "ana@gmail.com"
    assert aviso["new_email"] == "ana@trabajo.com"
    correos.send_verification_email.assert_not_called()


async def test_e1_the_request_checks_the_password_on_the_locked_row():
    """B1: la contraseña actual se comprueba sobre la fila bloqueada (tabla de caminos)."""
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    pedidos = []
    original = uow.users.find_by_id_for_update

    async def espia(user_id):
        pedidos.append(user_id)
        return await original(user_id)

    uow.users.find_by_id_for_update = espia

    await _pide(uow, ana)

    assert pedidos == [ana.id]


async def test_e2_confirming_switches_the_email():
    """Con su token: el correo de la cuenta es el nuevo, verificado, sin pendiente."""
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    _r, correos = await _pide(uow, ana)
    token = correos.send_email_change_confirmation.await_args.kwargs["token"]

    usuario = await ConfirmEmailChangeUseCase(uow).execute(str(ana.id.value), token)

    assert usuario.email == "ana@trabajo.com"
    assert usuario.email_verified is True
    assert usuario.pending_email is None


async def test_e3_a_late_confirmation_cancels_the_change_and_saves_it():
    """
    Given: Un cambio pedido hace 25 horas
    When: Se confirma
    Then: EmailChangeExpiredError, y el pendiente queda anulado en la BD (no solo en
          memoria: un error dentro de la transacción la desharía)
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    _r, correos = await _pide(uow, ana)
    token = correos.send_email_change_confirmation.await_args.kwargs["token"]
    caso = ConfirmEmailChangeUseCase(uow, reloj=lambda: datetime.now() + timedelta(hours=25))

    with pytest.raises(EmailChangeExpiredError):
        await caso.execute(str(ana.id.value), token)

    async with uow:
        assert (await uow.users.find_by_id(ana.id)).pending_email_token is None


async def test_e4_an_address_taken_meanwhile_is_refused():
    """
    Given: Un cambio pendiente a ana@trabajo.com, y otra cuenta que se registra con él
    When: Ana confirma
    Then: EmailChangeEmailInUseError, sigue con ana@gmail.com y sin pendiente
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    _r, correos = await _pide(uow, ana)
    token = correos.send_email_change_confirmation.await_args.kwargs["token"]
    otra = User.create(
        first_name="Otra", last_name="Persona", email_str="ana@trabajo.com", plain_password=CLAVE
    )
    async with uow:
        await uow.users.save(otra)

    with pytest.raises(EmailChangeEmailInUseError):
        await ConfirmEmailChangeUseCase(uow).execute(str(ana.id.value), token)

    async with uow:
        guardada = await uow.users.find_by_id(ana.id)
    assert str(guardada.email.value) == "ana@gmail.com"
    assert guardada.pending_email_token is None


async def test_a_wrong_token_is_refused():
    """Otro token: EmailChangeInvalidError y el pendiente sigue."""
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    await _pide(uow, ana)

    with pytest.raises(EmailChangeInvalidError):
        await ConfirmEmailChangeUseCase(uow).execute(str(ana.id.value), "otro")

    assert (await uow.users.find_by_id(ana.id)).pending_email_token is not None


async def test_e6_cancelling_leaves_nothing_pending():
    """Anular: sin pendiente, y el enlace ya no vale."""
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    _r, correos = await _pide(uow, ana)
    token = correos.send_email_change_confirmation.await_args.kwargs["token"]

    usuario = await CancelEmailChangeUseCase(uow).execute(str(ana.id.value))

    assert usuario.pending_email is None
    with pytest.raises(EmailChangeInvalidError):
        await ConfirmEmailChangeUseCase(uow).execute(str(ana.id.value), token)


async def test_a_wrong_token_with_a_taken_address_is_invalid_and_keeps_the_change():
    """
    Given: Un pendiente a una dirección que otra cuenta ocupó después
    When: Se confirma con OTRO token
    Then: EmailChangeInvalidError (no 409) y el pendiente sigue: el token se mira antes
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    await _pide(uow, ana)
    otra = User.create(
        first_name="Otra", last_name="Persona", email_str="ana@trabajo.com", plain_password=CLAVE
    )
    async with uow:
        await uow.users.save(otra)

    with pytest.raises(EmailChangeInvalidError):
        await ConfirmEmailChangeUseCase(uow).execute(str(ana.id.value), "otro")

    assert (await uow.users.find_by_id(ana.id)).pending_email_token is not None


async def test_the_notice_skips_an_unverified_old_address():
    """
    Given: Una cuenta con el correo SIN verificar
    When: Pide un correo nuevo
    Then: El enlace va al nuevo, pero no hay aviso al viejo: nunca a un correo sin
          confirmar (como el aviso de nuevo inicio)
    """
    uow = InMemoryUnitOfWork()
    ana = User.create(
        first_name="Ana", last_name="Dueña", email_str="ana@gmail.com", plain_password=CLAVE
    )
    async with uow:
        await uow.users.save(ana)

    _respuesta, correos = await _pide(uow, ana)

    correos.send_email_change_confirmation.assert_awaited_once()
    correos.send_email_change_requested_notice.assert_not_awaited()


async def test_the_confirmed_change_goes_to_the_security_log(monkeypatch):
    """
    Given: Un cambio pendiente
    When: Se confirma desde una IP y un navegador
    Then: El log apunta el cambio YA hecho (sin verificación pendiente), con la red
    """
    from src.shared.infrastructure.logging import security_logger as modulo

    apuntes = []
    monkeypatch.setattr(
        modulo.SecurityLogger, "log_email_changed", lambda self, **kw: apuntes.append(kw)
    )
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    _r, correos = await _pide(uow, ana)
    apuntes.clear()
    token = correos.send_email_change_confirmation.await_args.kwargs["token"]

    await ConfirmEmailChangeUseCase(uow).execute(
        str(ana.id.value), token, ip_address="203.0.113.7", user_agent="Navegador"
    )

    assert apuntes == [
        {
            "user_id": str(ana.id.value),
            "ip_address": "203.0.113.7",
            "user_agent": "Navegador",
            "email_verification_required": False,
        }
    ]

"""
El reenvío del enlace de verificación (fase 3, revisión; decidido por Agustín).

Sin sesión solo se reenvía presentando el enlace CADUCADO (prueba de tener el buzón):
nadie provoca el correo con una dirección ajena ni anula enlaces. Con sesión (el aviso de
la app), por el correo de la propia cuenta, como hoy. En los dos, el correo sale y
DESPUÉS se guarda el enlace nuevo: si el envío falla, el de antes sigue valiendo.

  #   Caso                                         | Resultado
  ----|---------------------------------------------|----------------------------------
  R1  enlace caducado de cuenta sin verificar      | sale uno nuevo; se guarda su hash
                                                   |   al salir; el viejo deja de valer
  R2  el proveedor falla                           | nada guardado: el enlace de antes
                                                   |   sigue siendo el de la cuenta
  R3  enlace aún vigente                           | no se envía (que lo use)
  R4  token que no es                              | no se envía
  R5  en segundo plano                             | la respuesta no espera al correo
  R6  la cuenta se verifica entre envío y guardado | no se guarda nada
  S1  con sesión, su correo, falla el proveedor    | error y el enlace de antes intacto
"""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.ports.reenvio_de_verificacion_port import (
    IReenvioDeVerificacion,
)
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
    ResendVerificationError,
    ResendVerificationFromLinkUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

CORREO = "ana@example.com"


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _ana(uow, hace=timedelta(hours=49)) -> tuple[User, str]:
    ana = User.create("Ana", "Lopez", CORREO, "SecureP@ssw0rd123!")
    token = ana.generate_verification_token(ahora=datetime.now() - hace)
    async with uow:
        await uow.users.save(ana)
    return ana, token


def _correo(sale: bool = True) -> MagicMock:
    correo = MagicMock()
    correo.send_verification_email = AsyncMock(return_value=sale)
    return correo


class ReenvioEnCola(IReenvioDeVerificacion):
    """Guarda los reenvíos; el test los lanza cuando quiere, con su propia UoW."""

    def __init__(self, uow, correo):
        self.pendientes: list = []
        self._uow, self._correo = uow, correo

    def lanza(self, datos) -> None:
        self.pendientes.append(datos)

    async def envia_todo(self) -> None:
        from src.modules.user.application.services.envio_de_la_verificacion import (
            EnvioDeLaVerificacion,
        )

        pendientes, self.pendientes = self.pendientes, []
        for datos in pendientes:
            await EnvioDeLaVerificacion(self._uow, self._correo).envia_y_guarda(datos)


def _enviado(correo) -> str:
    return correo.send_verification_email.await_args.kwargs["verification_token"]


async def test_r1_an_expired_link_brings_a_new_one_saved_after_sending():
    """
    Given: Una cuenta sin verificar con su enlace caducado
    When: Se pide otro con ese enlace
    Then: Sale uno nuevo; la cuenta guarda su hash; el viejo ya no sirve
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana, viejo = await _ana(uow)

    await ResendVerificationFromLinkUseCase(uow, correo).execute(viejo)

    nuevo = _enviado(correo)
    assert ana.verification_token == _sha(nuevo)
    assert ana.verification_token_expires_at > datetime.now() + timedelta(hours=47)
    correo.send_verification_email.assert_awaited_once()
    assert correo.send_verification_email.await_args.kwargs["to_email"] == CORREO


async def test_r2_a_failing_provider_keeps_the_previous_link():
    """
    Given: Una cuenta con el enlace caducado y el proveedor de correo fallando
    When: Se pide otro con ese enlace
    Then: No se guarda nada: el de antes sigue siendo el de la cuenta (y se puede
          volver a pedir con él)
    """
    uow, correo = InMemoryUnitOfWork(), _correo(sale=False)
    ana, viejo = await _ana(uow)
    antes = ana.verification_token

    await ResendVerificationFromLinkUseCase(uow, correo).execute(viejo)

    correo.send_verification_email.assert_awaited_once()
    assert ana.verification_token == antes


@pytest.mark.parametrize("cual", ["vigente", "otro"])
async def test_r3_r4_a_current_or_wrong_link_sends_nothing(cual):
    """
    Given: Una cuenta con su enlace aún vigente
    When: Se pide otro con ese enlace, o con un token que no es
    Then: No se envía nada ni cambia el enlace
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana, token = await _ana(uow, hace=timedelta(hours=1))
    antes = ana.verification_token

    await ResendVerificationFromLinkUseCase(uow, correo).execute(
        token if cual == "vigente" else "token-que-no-es-0123456789abcdef0123456"
    )

    correo.send_verification_email.assert_not_awaited()
    assert ana.verification_token == antes


async def test_r5_the_response_does_not_wait_for_the_email():
    """
    Given: El reenvío en segundo plano
    When: Se pide otro con el enlace caducado
    Then: Vuelve sin enviar ni guardar; al lanzarlo, envía y guarda
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana, viejo = await _ana(uow)
    antes = ana.verification_token
    cola = ReenvioEnCola(uow, correo)

    await ResendVerificationFromLinkUseCase(uow, correo, reenvio=cola).execute(viejo)

    correo.send_verification_email.assert_not_awaited()
    assert ana.verification_token == antes and len(cola.pendientes) == 1
    await cola.envia_todo()
    assert ana.verification_token == _sha(_enviado(correo))


async def test_r6_verified_between_sending_and_saving_saves_nothing():
    """
    Given: Un reenvío en marcha
    When: La cuenta se verifica antes de guardar el enlace nuevo
    Then: No se guarda (sigue verificada y sin enlace)
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana, viejo = await _ana(uow)
    cola = ReenvioEnCola(uow, correo)
    await ResendVerificationFromLinkUseCase(uow, correo, reenvio=cola).execute(viejo)

    ana.confirm_email_ownership()
    await cola.envia_todo()

    assert ana.email_verified and ana.verification_token is None


async def test_s1_with_session_a_failing_provider_keeps_the_previous_link():
    """
    Given: La cuenta con sesión pide reenviar (su correo) y el proveedor falla
    When: Se ejecuta sin segundo plano
    Then: ResendVerificationError y el enlace de antes, intacto
    """
    uow, correo = InMemoryUnitOfWork(), _correo(sale=False)
    ana, _ = await _ana(uow, hace=timedelta(hours=1))
    antes = ana.verification_token

    with pytest.raises(ResendVerificationError):
        await ResendVerificationEmailUseCase(uow, correo).execute(CORREO)

    assert ana.verification_token == antes


async def test_s1_with_session_the_new_link_is_saved_after_sending():
    """
    Given: La cuenta con sesión pide reenviar en segundo plano
    When: Se ejecuta y luego se lanza
    Then: Antes de lanzarlo nada cambia; después, el hash del enviado
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana, _ = await _ana(uow, hace=timedelta(hours=1))
    antes = ana.verification_token
    cola = ReenvioEnCola(uow, correo)

    await ResendVerificationEmailUseCase(uow, correo, reenvio=cola).execute(CORREO)

    assert ana.verification_token == antes
    await cola.envia_todo()
    assert ana.verification_token == _sha(_enviado(correo))

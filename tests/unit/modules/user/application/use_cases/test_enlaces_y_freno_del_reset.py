"""
Los enlaces de verificación y de restablecer en los casos de uso (fase 3, F-04/F-05/F-13).

  #   Caso                                          | Resultado
  ----|----------------------------------------------|-----------------------------------
  C1  verificar con un enlace caducado              | VerificationTokenExpiredError
  C1  verificar con el enlace vigente               | verificada
  C3  verificar con el token en claro de antes      | enlace no válido (ValueError), no
                                                    |   «caducado»
  C1  reenviar la verificación                      | guarda el hash del token enviado
  C2  validar el enlace de restablecer vigente      | valid=True; caducado o anulado, no
  C2  restablecer dos veces con el mismo enlace     | la segunda, InvalidResetTokenError
  C3  el enlace enviado por correo                  | lleva el token; la BD, su hash
  H2  11.º correo de restablecer en el día          | no se envía, el token de antes sigue
                                                    |   valiendo, y la respuesta es igual
  H3  correo sin cuenta / con cuenta / sin cupo     | el mismo mensaje
"""

import asyncio
import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.user_dto import (
    RequestPasswordResetRequestDTO,
    ResetPasswordRequestDTO,
    ValidateResetTokenRequestDTO,
)
from src.modules.user.application.ports.correo_en_segundo_plano_port import (
    ICorreoEnSegundoPlano,
)
from src.modules.user.application.use_cases.request_password_reset_use_case import (
    RequestPasswordResetUseCase,
)
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
)
from src.modules.user.application.use_cases.reset_password_use_case import ResetPasswordUseCase
from src.modules.user.application.use_cases.validate_reset_token_use_case import (
    ValidateResetTokenUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import VerifyEmailUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.exceptions.verification_token_expired_error import (
    VerificationTokenExpiredError,
)
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

CORREO = "ana@example.com"
NUEVA = "N3wS3cur3P@ss!"


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _ana(uow: InMemoryUnitOfWork, verificada: bool = False) -> User:
    ana = User.create(
        first_name="Ana",
        last_name="Lopez",
        email_str=CORREO,
        plain_password="SecureP@ssw0rd123!",
    )
    if verificada:
        ana.confirm_email_ownership()
    async with uow:
        await uow.users.save(ana)
    return ana


def _pedir(uow, correo) -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(
        uow, correo, frontend_url="https://app.example", security_audit=MagicMock()
    )


def _correo() -> MagicMock:
    correo = MagicMock()
    correo.send_password_reset_email = AsyncMock(return_value=True)
    correo.send_verification_email = AsyncMock(return_value=True)
    correo.send_password_changed_notification = AsyncMock(return_value=True)
    correo.send_account_secured_notice = AsyncMock(return_value=True)
    return correo


def _token_del_enlace(correo: MagicMock) -> str:
    return correo.send_password_reset_email.await_args.kwargs["reset_link"].rsplit("/", 1)[1]


# --- C1: verificar ---------------------------------------------------------------------


async def test_c1_an_expired_verification_link_raises_its_own_error():
    """
    Given: Una cuenta con un enlace de verificación de hace 49 h
    When: Se verifica con él
    Then: VerificationTokenExpiredError, y la cuenta sigue sin verificar
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    token = ana.generate_verification_token(ahora=datetime.now() - timedelta(hours=49))

    with pytest.raises(VerificationTokenExpiredError):
        await VerifyEmailUseCase(uow).execute(token)

    assert not ana.email_verified


async def test_c1_a_current_verification_link_verifies():
    """
    Given: Una cuenta con un enlace de verificación de hace una hora
    When: Se verifica con él
    Then: Verificada
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    token = ana.generate_verification_token(ahora=datetime.now() - timedelta(hours=1))

    await VerifyEmailUseCase(uow).execute(token)

    assert ana.email_verified


async def test_c3_a_plaintext_verification_token_from_before_is_invalid():
    """
    Given: Una cuenta con el token de verificación guardado en claro (de antes)
    When: Se verifica con ese token
    Then: Enlace no válido, no «caducado»
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    ana._verification_token = "token-en-claro-de-antes-0123456789abcdef0123"

    with pytest.raises(ValueError) as error:
        await VerifyEmailUseCase(uow).execute("token-en-claro-de-antes-0123456789abcdef0123")

    assert not isinstance(error.value, VerificationTokenExpiredError)


async def test_c1_resending_stores_the_hash_of_the_token_it_sent():
    """
    Given: Una cuenta sin verificar
    When: Se reenvía la verificación
    Then: Se guarda el hash del token enviado, con 48 h, y ese token verifica
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana = await _ana(uow)

    await ResendVerificationEmailUseCase(uow, correo).execute(CORREO)

    enviado = correo.send_verification_email.await_args.kwargs["verification_token"]
    assert ana.verification_token == _sha(enviado)
    assert ana.verification_token_expires_at > datetime.now() + timedelta(hours=47)
    await VerifyEmailUseCase(uow).execute(enviado)
    assert ana.email_verified


# --- C2 / C3: restablecer --------------------------------------------------------------


async def test_c3_the_mailed_link_has_the_token_and_the_account_its_hash():
    """
    Given: Una cuenta
    When: Pide restablecer
    Then: El enlace del correo lleva el token; la cuenta guarda su SHA-256, 1 h
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana = await _ana(uow)

    await _pedir(uow, correo).execute(RequestPasswordResetRequestDTO(email=CORREO))

    token = _token_del_enlace(correo)
    assert ana.password_reset_token == _sha(token)
    assert ana.reset_token_expires_at <= datetime.now() + timedelta(hours=1)


async def test_c2_validate_says_valid_then_not_after_a_new_link():
    """
    Given: Un enlace de restablecer
    When: Se valida; se pide otro y se valida el primero
    Then: Primero vale; anulado por el nuevo, no
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    await _ana(uow)
    await _pedir(uow, correo).execute(RequestPasswordResetRequestDTO(email=CORREO))
    primero = _token_del_enlace(correo)
    valida = ValidateResetTokenUseCase(uow)

    assert (await valida.execute(ValidateResetTokenRequestDTO(token=primero))).valid is True

    await _pedir(uow, correo).execute(RequestPasswordResetRequestDTO(email=CORREO))
    segundo = _token_del_enlace(correo)

    assert (await valida.execute(ValidateResetTokenRequestDTO(token=primero))).valid is False
    assert (await valida.execute(ValidateResetTokenRequestDTO(token=segundo))).valid is True


async def test_c2_validate_says_not_valid_after_one_hour():
    """
    Given: Un enlace de restablecer de hace 61 minutos
    When: Se valida
    Then: valid=False
    """
    uow = InMemoryUnitOfWork()
    ana = await _ana(uow)
    token = ana.generate_password_reset_token(ahora=datetime.now() - timedelta(minutes=61))

    respuesta = await ValidateResetTokenUseCase(uow).execute(
        ValidateResetTokenRequestDTO(token=token)
    )

    assert respuesta.valid is False


async def test_c2_a_reset_link_works_once():
    """
    Given: Un enlace de restablecer
    When: Se usa dos veces
    Then: La primera cambia la contraseña; la segunda, InvalidResetTokenError
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana = await _ana(uow, verificada=True)
    token = ana.generate_password_reset_token()
    caso = ResetPasswordUseCase(uow, correo, security_audit=MagicMock())

    await caso.execute(ResetPasswordRequestDTO(token=token, new_password=NUEVA))
    assert ana.verify_password(NUEVA)

    with pytest.raises(InvalidResetTokenError):
        await caso.execute(ResetPasswordRequestDTO(token=token, new_password="Otr4S3cur3P@ss!"))


# --- H2 / H3: el tope por cuenta y la misma respuesta ---------------------------------


async def test_h2_the_eleventh_reset_email_of_the_day_is_not_sent():
    """
    Given: Una cuenta que ya recibió 10 correos de restablecer hoy
    When: Se pide otro
    Then: No se envía; el enlace de antes sigue valiendo; la respuesta, la misma
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    ana = await _ana(uow)
    caso = _pedir(uow, correo)
    for _ in range(10):
        normal = await caso.execute(RequestPasswordResetRequestDTO(email=CORREO))
    ultimo = _token_del_enlace(correo)
    hash_antes = ana.password_reset_token

    respuesta = await caso.execute(RequestPasswordResetRequestDTO(email=CORREO))

    assert correo.send_password_reset_email.await_count == 10
    assert ana.password_reset_token == hash_antes
    assert ana.can_reset_password(ultimo) is True
    assert respuesta == normal


async def test_h3_same_message_with_and_without_account():
    """
    Given: Un correo sin cuenta y otro con cuenta
    When: Se pide restablecer con cada uno
    Then: El mismo mensaje
    """
    uow, correo = InMemoryUnitOfWork(), _correo()
    await _ana(uow)

    con = await _pedir(uow, correo).execute(RequestPasswordResetRequestDTO(email=CORREO))
    sin = await _pedir(uow, correo).execute(
        RequestPasswordResetRequestDTO(email="nadie@example.com")
    )

    assert con.message == sin.message


# --- B-2: los correos de restablecer y de reenvío, en segundo plano --------------------


class CorreoEnCola(ICorreoEnSegundoPlano):
    """Guarda los envíos en vez de lanzarlos: el test decide cuándo salen."""

    def __init__(self):
        self.pendientes: list = []

    def lanza(self, nombre, envio) -> None:
        self.pendientes.append(envio)

    async def envia_todo(self) -> None:
        pendientes, self.pendientes = self.pendientes, []
        for envio in pendientes:
            await envio()


def _pedir_en_cola(uow, correo, cola) -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(
        uow,
        correo,
        frontend_url="https://app.example",
        security_audit=MagicMock(),
        correo_en_segundo_plano=cola,
    )


async def test_b2_forgot_password_answers_without_waiting_for_the_email():
    """
    Given: Una cuenta y el envío en segundo plano
    When: Pide restablecer
    Then: La respuesta vuelve sin haber enviado nada; el enlace guardado es el del
          correo que sale después
    """
    uow, correo, cola = InMemoryUnitOfWork(), _correo(), CorreoEnCola()
    ana = await _ana(uow)

    await _pedir_en_cola(uow, correo, cola).execute(RequestPasswordResetRequestDTO(email=CORREO))

    correo.send_password_reset_email.assert_not_awaited()
    assert len(cola.pendientes) == 1
    await cola.envia_todo()
    assert ana.password_reset_token == _sha(_token_del_enlace(correo))


@pytest.mark.parametrize("caso", ["sin cuenta", "sin cupo"])
async def test_b2_forgot_password_without_email_does_not_wait_either(monkeypatch, caso):
    """
    Given: Un correo sin cuenta, o una cuenta sin cupo
    When: Pide restablecer
    Then: Nada en la cola y ninguna espera artificial (ya no hay correo que imitar)
    """
    uow, correo, cola = InMemoryUnitOfWork(), _correo(), CorreoEnCola()
    ana = await _ana(uow)
    if caso == "sin cupo":
        for _ in range(10):
            ana.cuenta_un_correo_de_reset(datetime.now())
    esperas = []

    async def espera(segundos):
        esperas.append(segundos)

    monkeypatch.setattr(asyncio, "sleep", espera)
    email = CORREO if caso == "sin cupo" else "nadie@example.com"

    await _pedir_en_cola(uow, correo, cola).execute(RequestPasswordResetRequestDTO(email=email))

    assert cola.pendientes == []
    assert esperas == []


async def test_b2_resend_answers_without_waiting_for_the_email():
    """
    Given: Una cuenta sin verificar y el envío en segundo plano
    When: Pide reenviar la verificación
    Then: Vuelve sin haber enviado nada, con el hash del nuevo token ya guardado; el
          correo que sale después lleva ese token
    """
    uow, correo, cola = InMemoryUnitOfWork(), _correo(), CorreoEnCola()
    ana = await _ana(uow)

    await ResendVerificationEmailUseCase(uow, correo, correo_en_segundo_plano=cola).execute(CORREO)

    correo.send_verification_email.assert_not_awaited()
    assert len(cola.pendientes) == 1
    await cola.envia_todo()
    enviado = correo.send_verification_email.await_args.kwargs["verification_token"]
    assert ana.verification_token == _sha(enviado)

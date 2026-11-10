"""
El registro no dice si el correo ya tiene cuenta (fase 3, F-01; tabla aprobada).

  #   Caso                                         | Resultado
  ----|---------------------------------------------|------------------------------------
  B1  correo nuevo                                 | alta + correo de verificación
  B2  correo de una cuenta verificada              | la MISMA respuesta (forma y datos
                                                   |   enviados), bcrypt igual, la cuenta
                                                   |   sin tocar, aviso al dueño
  B2  otro intento dentro de las 24 h              | igual, sin segundo aviso
  B2  pasadas las 24 h                             | otro aviso
  B2  el aviso falla                               | la respuesta no cambia
  B3  correo de una cuenta sin verificar           | la misma respuesta; el mismo aviso
                                                   |   (1 cada 24 h), sin reenviar la
                                                   |   verificación (Agustín, 10 nov)
  --  cuenta verificada pero desactivada           | la misma respuesta; sin aviso
  --  dos altas a la vez (la BD para a la segunda) | la segunda, la misma respuesta
  --  los correos van en segundo plano             | la respuesta no los espera
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO, UserResponseDTO
from src.modules.user.application.ports.correo_en_segundo_plano_port import (
    ICorreoEnSegundoPlano,
)
from src.modules.user.application.use_cases import register_user_use_case
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import EmailTakenConcurrentlyError
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

CLAVE_DEL_DUENO = "Du3n0$ecureP@ss"
CLAVE_DEL_OTRO = "V@l1dP@ss123!"
CORREO = "ana@example.com"


class CorreoEnCola(ICorreoEnSegundoPlano):
    """Guarda los envíos en vez de lanzarlos: el test decide cuándo salen."""

    def __init__(self):
        self.pendientes: list[tuple[str, object]] = []

    def lanza(self, nombre, envio) -> None:
        self.pendientes.append((nombre, envio))

    async def envia_todo(self) -> None:
        pendientes, self.pendientes = self.pendientes, []
        for _, envio in pendientes:
            await envio()


def _alta(email: str = CORREO, **mas) -> RegisterUserRequestDTO:
    return RegisterUserRequestDTO(
        accept_terms=True,
        email=email,
        password=CLAVE_DEL_OTRO,
        first_name="Otro",
        last_name="Nombre",
        **mas,
    )


def _email_service() -> MagicMock:
    servicio = MagicMock()
    servicio.send_verification_email = AsyncMock(return_value=True)
    servicio.send_register_attempt_notice = AsyncMock(return_value=True)
    return servicio


def _caso(uow, email_service, cola=None) -> RegisterUserUseCase:
    paises = AsyncMock()
    paises.exists.return_value = True
    return RegisterUserUseCase(
        uow,
        paises,
        email_service=email_service,
        security_audit=MagicMock(),
        correo_en_segundo_plano=cola,
    )


async def _dueno(uow, verificada=True, activa=True) -> User:
    dueno = User.create(
        first_name="Ana",
        last_name="Duena",
        email_str=CORREO,
        plain_password=CLAVE_DEL_DUENO,
    )
    if verificada:
        dueno.confirm_email_ownership()
    if not activa:
        dueno.deactivate("admin-id")
    async with uow:
        await uow.users.save(dueno)
    return dueno


def _forma(respuesta: UserResponseDTO) -> dict:
    """Lo que se ve de una respuesta, sin lo que cambia en cada alta (id y fechas)."""
    datos = respuesta.model_dump(mode="json")
    for campo in ("id", "created_at", "updated_at"):
        datos.pop(campo)
    return datos


async def test_b1_a_new_email_registers_and_sends_the_verification_email():
    """
    Given: Un correo sin cuenta
    When: Se registra
    Then: La cuenta se guarda y sale su correo de verificación (con el token en claro,
          que es el que lleva el enlace)
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()

    respuesta = await _caso(uow, correo).execute(_alta())

    async with uow:
        guardada = await uow.users.find_by_email(Email(CORREO))
    assert guardada is not None and str(guardada.id.value) == str(respuesta.id)
    correo.send_verification_email.assert_awaited_once()
    token = correo.send_verification_email.await_args.kwargs["verification_token"]
    assert guardada.verification_token != token
    correo.send_register_attempt_notice.assert_not_awaited()


async def test_b2_a_verified_email_gets_the_same_response_and_the_owner_a_notice():
    """
    Given: Una cuenta verificada con ese correo
    When: Otro se registra con él
    Then: La misma respuesta que un alta nueva (los datos enviados, con un id que no se
          guarda); la cuenta, intacta; sin correo de verificación; aviso al dueño
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()
    dueno = await _dueno(uow)
    antes = (dueno.first_name, dueno.password.hashed_value, dueno.email_verified)

    respuesta = await _caso(uow, correo).execute(_alta())

    nueva = await _caso(InMemoryUnitOfWork(), _email_service()).execute(_alta())
    assert _forma(respuesta) == _forma(nueva)
    assert str(respuesta.id) != str(dueno.id.value)
    async with uow:
        assert await uow.users.find_by_id(dueno.id) is dueno
        assert len(uow.users._users) == 1
    assert (dueno.first_name, dueno.password.hashed_value, dueno.email_verified) == antes
    assert dueno.verify_password(CLAVE_DEL_DUENO)
    correo.send_verification_email.assert_not_awaited()
    correo.send_register_attempt_notice.assert_awaited_once_with(to_email=CORREO, user_name="Ana")


async def test_b2_the_password_is_hashed_anyway(monkeypatch):
    """
    Given: Una cuenta verificada con ese correo
    When: Otro se registra con él
    Then: El bcrypt de su contraseña se calcula igual que en un alta nueva (el tiempo)
    """
    uow = InMemoryUnitOfWork()
    await _dueno(uow)
    llamadas = []
    real = register_user_use_case.run_bcrypt

    async def contada(func, *args, **kwargs):
        llamadas.append(func)
        return await real(func, *args, **kwargs)

    monkeypatch.setattr(register_user_use_case, "run_bcrypt", contada)

    await _caso(uow, _email_service()).execute(_alta())

    assert llamadas == [User.create]


async def test_b2_only_one_notice_every_24_hours_per_account():
    """
    Given: Una cuenta verificada que ya recibió el aviso hace 23 h
    When: Otro vuelve a registrarse con su correo
    Then: La misma respuesta, sin segundo aviso; pasado el día, sí
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()
    dueno = await _dueno(uow)
    dueno.reserva_el_aviso_de_registro(datetime.now() - timedelta(hours=23))

    await _caso(uow, correo).execute(_alta())
    correo.send_register_attempt_notice.assert_not_awaited()

    # Pasa el día: el aviso apuntado, de hace 25 h
    dueno._register_attempt_notice_at = datetime.now() - timedelta(hours=25)
    await _caso(uow, correo).execute(_alta())
    correo.send_register_attempt_notice.assert_awaited_once()


async def test_b2_two_attempts_in_a_row_send_one_notice():
    """
    Given: Una cuenta verificada sin avisos
    When: Otro se registra dos veces seguidas con su correo
    Then: Un solo aviso: el primero lo apunta en la cuenta
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()
    dueno = await _dueno(uow)

    await _caso(uow, correo).execute(_alta())
    await _caso(uow, correo).execute(_alta())

    correo.send_register_attempt_notice.assert_awaited_once()
    assert dueno.register_attempt_notice_at is not None


@pytest.mark.parametrize("fallo", ["devuelve False", "lanza"])
async def test_b2_a_failing_notice_does_not_change_the_response(fallo):
    """
    Given: Una cuenta verificada y el envío del aviso fallando
    When: Otro se registra con su correo
    Then: La misma respuesta, sin error
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()
    await _dueno(uow)
    if fallo == "lanza":
        correo.send_register_attempt_notice = AsyncMock(side_effect=ConnectionError("smtp"))
    else:
        correo.send_register_attempt_notice = AsyncMock(return_value=False)

    respuesta = await _caso(uow, correo).execute(_alta())

    assert respuesta.email == CORREO


async def test_b3_an_unverified_email_gets_the_same_response_and_the_notice():
    """
    Given: Una cuenta SIN verificar con ese correo
    When: Otro se registra con él dos veces
    Then: La misma respuesta; la cuenta, intacta (su enlace de verificación, el mismo);
          sin verificación nueva; un solo aviso al buzón (ADR-045: restablecer la reclama)
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()
    dueno = await _dueno(uow, verificada=False)
    dueno.generate_verification_token()
    token_antes = dueno.verification_token

    respuesta = await _caso(uow, correo).execute(_alta())
    await _caso(uow, correo).execute(_alta())

    assert respuesta.email == CORREO and respuesta.first_name == "Otro"
    assert dueno.verify_password(CLAVE_DEL_DUENO)
    assert not dueno.email_verified
    assert dueno.verification_token == token_antes
    correo.send_verification_email.assert_not_awaited()
    correo.send_register_attempt_notice.assert_awaited_once_with(to_email=CORREO, user_name="Ana")


@pytest.mark.parametrize("verificada", [True, False])
async def test_a_deactivated_account_gets_no_notice(verificada):
    """
    Given: Una cuenta desactivada (verificada o no)
    When: Otro se registra con su correo
    Then: La misma respuesta y ningún aviso (no puede iniciar sesión)
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()
    await _dueno(uow, verificada=verificada, activa=False)

    respuesta = await _caso(uow, correo).execute(_alta())

    assert respuesta.email == CORREO
    correo.send_register_attempt_notice.assert_not_awaited()


@pytest.mark.parametrize("la_otra", ["sin verificar", "verificada"])
async def test_the_second_of_two_simultaneous_sign_ups_gets_the_same_response(monkeypatch, la_otra):
    """
    Given: Dos altas a la vez: la otra guarda el correo justo antes y la base de datos
           para a esta al guardar (la violación de unicidad, ya como error del dominio)
    When: Esta guarda
    Then: La misma respuesta que cualquier correo ya registrado, sin verificación; y lo
          mismo que el camino de siempre: el aviso al buzón, con su tope de 24 h
    """
    uow, correo = InMemoryUnitOfWork(), _email_service()
    guarda = uow.users.save
    otras = []

    async def la_otra_gana(_user):
        otra = User.create(
            first_name="Ana", last_name="Duena", email_str=CORREO, plain_password=CLAVE_DEL_DUENO
        )
        if la_otra == "verificada":
            otra.confirm_email_ownership()
        otras.append(otra)
        await guarda(otra)
        monkeypatch.setattr(uow.users, "save", guarda)
        raise EmailTakenConcurrentlyError("El correo ya está en uso.")

    monkeypatch.setattr(uow.users, "save", la_otra_gana)

    respuesta = await _caso(uow, correo).execute(_alta())

    # El aviso sale ya en el alta que perdió la carrera
    assert respuesta.email == CORREO and respuesta.first_name == "Otro"
    correo.send_verification_email.assert_not_awaited()
    correo.send_register_attempt_notice.assert_awaited_once_with(to_email=CORREO, user_name="Ana")
    assert otras[0].register_attempt_notice_at is not None
    # Y con su tope de 24 h: otra alta después, sin segundo aviso
    await _caso(uow, correo).execute(_alta())
    correo.send_register_attempt_notice.assert_awaited_once()


async def test_a_failure_that_is_not_the_email_is_not_hidden(monkeypatch):
    """
    Given: Un fallo al guardar con el correo aún libre (otra restricción, la BD caída)
    When: Se registra
    Then: El fallo sube tal cual: no se esconde bajo la respuesta de siempre
    """
    uow = InMemoryUnitOfWork()

    async def falla(_user):
        raise RuntimeError("otra restricción")

    monkeypatch.setattr(uow.users, "save", falla)

    with pytest.raises(RuntimeError, match="otra restricción"):
        await _caso(uow, _email_service()).execute(_alta())


@pytest.mark.parametrize("verificada", [None, True])
async def test_the_emails_go_in_the_background(verificada):
    """
    Given: El envío en segundo plano conectado
    When: Se registra un correo nuevo (B1) o el de una cuenta verificada (B2)
    Then: La respuesta vuelve sin haber enviado nada; el correo sale al lanzarlo
    """
    uow, correo, cola = InMemoryUnitOfWork(), _email_service(), CorreoEnCola()
    if verificada:
        await _dueno(uow)

    await _caso(uow, correo, cola).execute(_alta())

    correo.send_verification_email.assert_not_awaited()
    correo.send_register_attempt_notice.assert_not_awaited()
    assert len(cola.pendientes) == 1
    await cola.envia_todo()
    enviado = correo.send_register_attempt_notice if verificada else correo.send_verification_email
    enviado.assert_awaited_once()

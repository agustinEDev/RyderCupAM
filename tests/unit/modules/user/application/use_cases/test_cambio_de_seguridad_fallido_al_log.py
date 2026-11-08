"""
Los fallos de /users/security, al log de auditoría (L1-L3, 7 nov 2026).

Antes solo se registraba el cambio que salía bien: con una sesión robada se podían probar
contraseñas sin dejar rastro.

  L1 contraseña actual equivocada        → wrong_current_password, severidad alta
  L2 la contraseña cambió entretanto     → changed_during_request, media
  L3 correo nuevo ocupado                → email_in_use, media
     contraseña repetida                 → password_reused, media
     contraseña que no cumple la política→ weak_password, media
  Nunca la contraseña ni el correo pedido en el registro.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.dto.user_dto import UpdateSecurityRequestDTO
from src.modules.user.application.use_cases import update_security_use_case
from src.modules.user.application.use_cases.update_security_use_case import UpdateSecurityUseCase
from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
)
from src.modules.user.domain.value_objects.password import InvalidPasswordError, Password
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.domain.events.security_events import (
    SecurityChangeFailedAuditEvent,
    SecuritySeverity,
)

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"
NUEVA = "N3w$ecureP@ss99"
OTRA = "Otr4$ecureP@ss77"


@pytest.fixture
def registro():
    return MagicMock()


async def _con_usuario(uow, email="ana@example.com") -> User:
    user = User.create(first_name="Ana", last_name="Lopez", email_str=email, plain_password=CLAVE)
    async with uow:
        await uow.users.save(user)
    return user


async def _pide(uow, user, registro=None, **cambios):
    datos = {"current_password": CLAVE, "ip_address": "203.0.113.9", "user_agent": "Safari"}
    datos.update(cambios)
    return await UpdateSecurityUseCase(
        uow, AsyncMock(), security_audit=registro if registro is not None else MagicMock()
    ).execute(str(user.id.value), UpdateSecurityRequestDTO(**datos))


def _motivo(registro) -> str:
    registro.log_security_change_failed.assert_called_once()
    kwargs = registro.log_security_change_failed.call_args.kwargs
    assert kwargs["ip_address"] == "203.0.113.9"
    assert kwargs["user_agent"] == "Safari"
    # Nunca la contraseña ni el correo pedido
    assert not (
        {CLAVE, NUEVA, "Mal4$Clave000", "ocupado@example.com"} & set(map(str, kwargs.values()))
    )
    return kwargs["reason"]


async def test_l1_a_wrong_current_password_is_recorded(registro):
    """
    Given: Un usuario con sesión
    When: Teclea mal la contraseña actual
    Then: El error de siempre, y al log wrong_current_password con su usuario, IP y navegador
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)

    with pytest.raises(InvalidCredentialsError):
        await _pide(
            uow,
            user,
            registro,
            current_password="Mal4$Clave000",
            new_password=NUEVA,
            confirm_password=NUEVA,
        )

    assert _motivo(registro) == "wrong_current_password"
    assert registro.log_security_change_failed.call_args.kwargs["user_id"] == str(user.id.value)


async def test_l2_a_password_changed_during_the_request_is_recorded(registro, monkeypatch):
    """
    Given: Un cambio con la actual bien tecleada
    When: Otro cambia la contraseña mientras se calculan los bcrypt
    Then: «contraseña actual incorrecta», y al log changed_during_request
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)
    real = update_security_use_case.run_bcrypt
    hecho = {"ya": False}

    async def con_cambio_entremedias(func, *args, **kwargs):
        resultado = await real(func, *args, **kwargs)
        if not hecho["ya"]:
            hecho["ya"] = True
            async with uow:
                otro = await uow.users.find_by_id(user.id)
                otro.change_password(Password.from_plain_text(OTRA))
                await uow.users.save(otro)
        return resultado

    monkeypatch.setattr(update_security_use_case, "run_bcrypt", con_cambio_entremedias)

    with pytest.raises(InvalidCredentialsError):
        await _pide(uow, user, registro, new_password=NUEVA, confirm_password=NUEVA)

    assert _motivo(registro) == "changed_during_request"


async def test_l3_an_email_in_use_is_recorded(registro):
    """
    Given: Un correo nuevo que ya usa otra cuenta
    When: Se pide el cambio
    Then: El error de siempre, y al log email_in_use
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)
    await _con_usuario(uow, "ocupado@example.com")

    with pytest.raises(DuplicateEmailError):
        await _pide(uow, user, registro, new_email="ocupado@example.com")

    assert _motivo(registro) == "email_in_use"


async def test_l3_a_reused_password_is_recorded(registro):
    """
    Given: Una contraseña nueva que está en el historial
    When: Se pide el cambio
    Then: El error de siempre, y al log password_reused
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)
    async with uow:
        await uow.password_history.save(
            PasswordHistory.create(
                user_id=user.id,
                password_hash=Password.from_plain_text(NUEVA).hashed_value,
                total_history_count=1,
            )
        )

    with pytest.raises(InvalidPasswordError):
        await _pide(uow, user, registro, new_password=NUEVA, confirm_password=NUEVA)

    assert _motivo(registro) == "password_reused"


async def test_l3_a_weak_password_is_recorded(registro):
    """
    Given: Una contraseña nueva que no cumple la política
    When: Se pide el cambio
    Then: El error de siempre, y al log weak_password
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)

    with pytest.raises(InvalidPasswordError):
        await _pide(
            uow, user, registro, new_password="solamenteletras", confirm_password="solamenteletras"
        )

    assert _motivo(registro) == "weak_password"


async def test_a_change_that_works_records_no_failure(registro):
    """
    Given: Un cambio válido
    When: Se hace
    Then: Ningún fallo en el log; solo el cambio de contraseña
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)

    await _pide(uow, user, registro, new_password=NUEVA, confirm_password=NUEVA)

    registro.log_security_change_failed.assert_not_called()
    registro.log_password_changed.assert_called_once()


@pytest.mark.parametrize(
    ("motivo", "severidad"),
    [
        ("wrong_current_password", SecuritySeverity.HIGH),
        ("changed_during_request", SecuritySeverity.MEDIUM),
        ("email_in_use", SecuritySeverity.MEDIUM),
        ("password_reused", SecuritySeverity.MEDIUM),
        ("weak_password", SecuritySeverity.MEDIUM),
    ],
)
def test_the_event_severity_and_its_log_line(motivo, severidad):
    """
    Given: El evento con cada motivo
    When: Se construye
    Then: Alta solo con la contraseña actual mal, siempre fallo, y su línea de log con el motivo
    """
    evento = SecurityChangeFailedAuditEvent(
        user_id="u-1", ip_address="203.0.113.9", user_agent="Safari", reason=motivo
    )

    assert evento.severity is severidad
    assert evento.is_failure is True
    assert (
        evento.resumen("User u-1")
        == f"SECURITY CHANGE FAILED | User u-1 | Reason: {motivo} | IP: 203.0.113.9"
    )
    assert evento.to_dict()["reason"] == motivo

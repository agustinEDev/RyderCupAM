"""
Las acciones de administrador quedan en el log de seguridad (F-20, auditoría OWASP del
9 nov 2026).

Desactivar y reactivar ya quedaban (BE #744). Faltaban dar o quitar el rol de
administrador, borrar una cuenta y cambiarle el correo: ahora cada una deja un evento
CRITICAL con quién lo hizo, a qué cuenta y desde qué IP. Una acción rechazada no deja
nada, y un fallo del log no cambia la respuesta.

  A1 dar el rol de administrador        -> log_admin_role_changed(is_admin=True)
  A2 quitarlo                           -> log_admin_role_changed(is_admin=False)
  A3 el rol que ya tenía                -> nada
  A4 pedir un correo nuevo para la cuenta -> log_admin_email_change_requested
  A5 el mismo correo                    -> nada
  A6 correo ocupado (rechazado)         -> nada
  A7 cuenta que no existe (rechazado)   -> nada
  A8 borrar una cuenta                  -> log_account_deleted_by_admin
  A9 borrar una cuenta con actividad (rechazado) -> nada
  A10 borrar una que no existe (rechazado)       -> nada
  A11 el log falla                      -> el cambio vale igual
  A12 sin IP ni navegador               -> «unknown»
"""

from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from src.modules.user.application.dto.admin_dto import AdminUpdateUserRequestDTO
from src.modules.user.application.use_cases.admin_delete_user_use_case import (
    AdminDeleteUserUseCase,
)
from src.modules.user.application.use_cases.admin_update_user_use_case import (
    AdminUpdateUserUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import DuplicateEmailError, UserNotFoundError
from src.modules.user.domain.exceptions import UserHasActivityException
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

ADMIN = "admin-0000"
IP = "203.0.113.9"
NAVEGADOR = "Mozilla/5.0"


@pytest.fixture
def uow():
    """Un Unit of Work en memoria."""
    return InMemoryUnitOfWork()


@pytest.fixture
async def cuenta(uow):
    """Una cuenta normal, con su correo."""
    user = User.create(
        first_name="Carlos",
        last_name="Ruiz",
        email_str="carlos@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with uow:
        await uow.users.save(user)
    return user


def _editar(uow, auditoria):
    """El caso de uso de editar, con el log espiado."""
    return AdminUpdateUserUseCase(uow, email_service=AsyncMock(), security_audit=auditoria)


async def _edita(uow, auditoria, user_id: str, **cambios):
    """Edita la cuenta como el administrador, desde su IP."""
    return await _editar(uow, auditoria).execute(
        user_id,
        AdminUpdateUserRequestDTO(**cambios),
        actor_user_id=ADMIN,
        ip_address=IP,
        user_agent=NAVEGADOR,
    )


def _sin_auditoria(auditoria: Mock) -> None:
    """No se apuntó ninguna acción de administrador."""
    auditoria.log_admin_role_changed.assert_not_called()
    auditoria.log_admin_email_change_requested.assert_not_called()
    auditoria.log_account_deleted_by_admin.assert_not_called()


@pytest.mark.parametrize("is_admin", [True, False])
async def test_a1_a2_changing_the_admin_role_is_audited(uow, cuenta, is_admin):
    """
    Given: Una cuenta con el rol contrario al que se le pone
    When: El administrador le da (o le quita) el rol
    Then: Queda en el log quién, a qué cuenta, el rol nuevo y desde qué IP
    """
    if not is_admin:
        cuenta.set_is_admin(True)
        async with uow:
            await uow.users.save(cuenta)
    auditoria = Mock()

    await _edita(uow, auditoria, str(cuenta.id.value), is_admin=is_admin)

    auditoria.log_admin_role_changed.assert_called_once_with(
        user_id=ADMIN,
        target_user_id=str(cuenta.id.value),
        is_admin=is_admin,
        ip_address=IP,
        user_agent=NAVEGADOR,
    )


async def test_a3_the_same_role_is_not_audited(uow, cuenta):
    """
    Given: Una cuenta que no es administradora
    When: Se guarda con is_admin=False (sin cambio)
    Then: No se apunta nada
    """
    auditoria = Mock()

    await _edita(uow, auditoria, str(cuenta.id.value), is_admin=False)

    _sin_auditoria(auditoria)


async def test_a4_an_email_change_requested_by_the_admin_is_audited(uow, cuenta):
    """
    Given: Una cuenta
    When: El administrador le pone otro correo (queda pendiente)
    Then: Queda en el log quién, a qué cuenta y desde qué IP, sin ninguno de los correos
    """
    auditoria = Mock()

    await _edita(uow, auditoria, str(cuenta.id.value), email="nuevo@test.com")

    auditoria.log_admin_email_change_requested.assert_called_once_with(
        user_id=ADMIN,
        target_user_id=str(cuenta.id.value),
        ip_address=IP,
        user_agent=NAVEGADOR,
    )
    auditoria.log_admin_role_changed.assert_not_called()


async def test_a5_the_same_email_is_not_audited(uow, cuenta):
    """
    Given: Una cuenta
    When: Se guarda con su mismo correo, escrito de otra forma
    Then: No se apunta nada
    """
    auditoria = Mock()

    await _edita(uow, auditoria, str(cuenta.id.value), email="Carlos@Test.com")

    _sin_auditoria(auditoria)


async def test_a6_a_rejected_email_change_writes_nothing(uow, cuenta):
    """
    Given: Otra cuenta que ya usa el correo, y el rol de admin pedido a la vez
    When: El administrador intenta poner ese correo
    Then: Se rechaza y no queda nada en el log (ni el rol, que tampoco se guarda)
    """
    otra = User.create(
        first_name="Otra",
        last_name="Cuenta",
        email_str="ocupado@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with uow:
        await uow.users.save(otra)
    auditoria = Mock()

    with pytest.raises(DuplicateEmailError):
        await _edita(uow, auditoria, str(cuenta.id.value), email="ocupado@test.com", is_admin=True)

    _sin_auditoria(auditoria)


async def test_a7_editing_an_account_that_does_not_exist_writes_nothing(uow):
    """
    Given: Un id sin cuenta
    When: El administrador intenta darle el rol
    Then: UserNotFoundError y nada en el log
    """
    auditoria = Mock()

    with pytest.raises(UserNotFoundError):
        await _edita(uow, auditoria, str(uuid4()), is_admin=True)

    _sin_auditoria(auditoria)


def _uow_falso(**repos):
    """Un UoW de otro módulo, con sus repositorios simulados."""
    falso = MagicMock()
    falso.__aenter__ = AsyncMock(return_value=falso)
    falso.__aexit__ = AsyncMock(return_value=False)
    for nombre, repo in repos.items():
        setattr(falso, nombre, repo)
    return falso


def _borrar(uow, auditoria, *, competiciones: int = 0):
    """El caso de uso de borrar, con el log espiado y la actividad que se diga."""
    competitions = AsyncMock()
    competitions.count_by_creator = AsyncMock(return_value=competiciones)
    hole_scores = AsyncMock()
    hole_scores.exists_by_player = AsyncMock(return_value=False)
    drafts = AsyncMock()
    drafts.exists_by_captain = AsyncMock(return_value=False)
    partidas = AsyncMock()
    partidas.existe_con_jugador = AsyncMock(return_value=False)
    quick_matches = AsyncMock()
    quick_matches.exists_created_by = AsyncMock(return_value=False)
    golf_courses = AsyncMock()
    golf_courses.count_by_creator = AsyncMock(return_value=0)
    return AdminDeleteUserUseCase(
        uow,
        _uow_falso(
            competitions=competitions, hole_scores=hole_scores, drafts=drafts, partidas=partidas
        ),
        _uow_falso(quick_matches=quick_matches),
        _uow_falso(golf_courses=golf_courses),
        security_audit=auditoria,
    )


async def test_a8_deleting_an_account_is_audited(uow, cuenta):
    """
    Given: Una cuenta sin actividad
    When: El administrador la borra
    Then: Queda en el log quién, qué cuenta y desde qué IP
    """
    auditoria = Mock()

    await _borrar(uow, auditoria).execute(
        str(cuenta.id.value), actor_user_id=ADMIN, ip_address=IP, user_agent=NAVEGADOR
    )

    auditoria.log_account_deleted_by_admin.assert_called_once_with(
        user_id=ADMIN,
        deleted_user_id=str(cuenta.id.value),
        ip_address=IP,
        user_agent=NAVEGADOR,
    )


async def test_a9_a_rejected_delete_writes_nothing(uow, cuenta):
    """
    Given: Una cuenta que ha creado una competición
    When: El administrador intenta borrarla
    Then: Se rechaza y no queda nada en el log
    """
    auditoria = Mock()

    with pytest.raises(UserHasActivityException):
        await _borrar(uow, auditoria, competiciones=1).execute(
            str(cuenta.id.value), actor_user_id=ADMIN, ip_address=IP, user_agent=NAVEGADOR
        )

    _sin_auditoria(auditoria)


async def test_a10_deleting_an_account_that_does_not_exist_writes_nothing(uow):
    """
    Given: Un id sin cuenta
    When: El administrador intenta borrarla
    Then: UserNotFoundError y nada en el log
    """
    auditoria = Mock()

    with pytest.raises(UserNotFoundError):
        await _borrar(uow, auditoria).execute(str(uuid4()), actor_user_id=ADMIN)

    _sin_auditoria(auditoria)


async def test_a11_a_failing_log_does_not_undo_the_change(uow, cuenta):
    """
    Given: Un log de seguridad que falla
    When: El administrador da el rol y borra otra cuenta
    Then: Los dos cambios valen igual y no sale ninguna excepción
    """
    auditoria = Mock()
    auditoria.log_admin_role_changed.side_effect = RuntimeError("log caído")
    auditoria.log_account_deleted_by_admin.side_effect = RuntimeError("log caído")

    resultado = await _edita(uow, auditoria, str(cuenta.id.value), is_admin=True)
    await _borrar(uow, auditoria).execute(str(cuenta.id.value), actor_user_id=ADMIN)

    assert resultado.is_admin is True
    async with uow:
        assert await uow.users.find_by_id(cuenta.id) is None


async def test_a12_without_ip_or_browser_it_says_unknown(uow, cuenta):
    """
    Given: Una petición sin IP ni navegador conocidos
    When: El administrador da el rol
    Then: El log dice «unknown», como en la desactivación
    """
    auditoria = Mock()

    await _editar(uow, auditoria).execute(
        str(cuenta.id.value), AdminUpdateUserRequestDTO(is_admin=True), actor_user_id=ADMIN
    )

    datos = auditoria.log_admin_role_changed.call_args.kwargs
    assert (datos["ip_address"], datos["user_agent"]) == ("unknown", "unknown")

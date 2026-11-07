"""
Lo que pasa ENTRE la lectura y la escritura, ahora que el bcrypt va fuera de la
transacción (BE #283, tabla aprobada por Agustín el 7 nov 2026).

  B2-1 alta: otro se registra con el mismo correo durante el bcrypt → «ya registrado»
  B2-3 cambio de seguridad:
       - la contraseña cambia durante el bcrypt (un restablecimiento) → «contraseña
         actual incorrecta», y no se escribe la nueva
       - el correo nuevo lo coge otro durante el bcrypt → «correo en uso»
       - errores en el orden de siempre: la actual mal y el correo ocupado → la actual
  B2-4 restablecer: otro gasta el token durante el bcrypt → «enlace no válido», y la
       contraseña no cambia
  B2-5 cuenta de sistema: otro proceso la crea durante el bcrypt → vale la suya
  B2-6 una contraseña nueva que no cumple la política no llega a ningún bcrypt
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.user.application.dto.user_dto import (
    RegisterUserRequestDTO,
    ResetPasswordRequestDTO,
    UpdateSecurityRequestDTO,
)
from src.modules.user.application.use_cases import (
    ensure_system_user_use_case,
    register_user_use_case,
    reset_password_use_case,
    update_security_use_case,
)
from src.modules.user.application.use_cases.ensure_system_user_use_case import (
    EnsureSystemUserUseCase,
)
from src.modules.user.application.use_cases.register_user_use_case import RegisterUserUseCase
from src.modules.user.application.use_cases.reset_password_use_case import ResetPasswordUseCase
from src.modules.user.application.use_cases.update_security_use_case import UpdateSecurityUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from src.modules.user.domain.exceptions.invalid_reset_token_error import InvalidResetTokenError
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import InvalidPasswordError, Password
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"
NUEVA = "N3w$ecureP@ss99"
OTRA = "Otr4$ecureP@ss77"
# Doce caracteres (lo que pide el DTO) pero sin números ni símbolos: no cumple la política
DEBIL = "solamenteletras"


def _entretanto(monkeypatch, modulo, accion):
    """`run_bcrypt` que, tras el primer bcrypt, hace `accion`: lo que otro haría mientras."""
    real = modulo.run_bcrypt
    hecho = {"ya": False}

    async def con_algo_entre_medias(func, *args, **kwargs):
        resultado = await real(func, *args, **kwargs)
        if not hecho["ya"]:
            hecho["ya"] = True
            await accion()
        return resultado

    monkeypatch.setattr(modulo, "run_bcrypt", con_algo_entre_medias)


async def _con_usuario(uow: InMemoryUnitOfWork, email="ana@example.com") -> User:
    user = User.create(first_name="Ana", last_name="Lopez", email_str=email, plain_password=CLAVE)
    async with uow:
        await uow.users.save(user)
    return user


# --- B2-1 alta ---------------------------------------------------------------------


async def test_b2_1_someone_takes_the_email_during_the_bcrypt(monkeypatch):
    """
    Given: Un alta con un correo libre
    When: Otro se registra con ese correo mientras se calcula el bcrypt
    Then: «ya registrado», y solo queda la cuenta del otro
    """
    uow = InMemoryUnitOfWork()
    paises = AsyncMock()
    paises.exists.return_value = True
    use_case = RegisterUserUseCase(uow, paises, security_audit=MagicMock())

    async def otro_se_registra():
        await _con_usuario(uow, "b21@example.com")

    _entretanto(monkeypatch, register_user_use_case, otro_se_registra)

    with pytest.raises(UserAlreadyExistsError):
        await use_case.execute(
            RegisterUserRequestDTO(
                accept_terms=True,
                email="b21@example.com",
                password=NUEVA,
                first_name="Bea",
                last_name="Ruiz",
            )
        )

    guardado = await uow.users.find_by_email(Email("b21@example.com"))
    assert guardado is not None and guardado.first_name == "Ana"


# --- B2-3 cambio de seguridad --------------------------------------------------------


async def test_b2_3_the_password_changes_during_the_bcrypt(monkeypatch):
    """
    Given: Un cambio de contraseña con la actual bien tecleada
    When: Un restablecimiento la cambia mientras se calculan los bcrypt
    Then: «contraseña actual incorrecta» (ya no es la actual) y queda la del otro
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)

    async def la_restablecen():
        async with uow:
            otro = await uow.users.find_by_id(user.id)
            otro.change_password(Password.from_plain_text(OTRA))
            await uow.users.save(otro)

    _entretanto(monkeypatch, update_security_use_case, la_restablecen)

    with pytest.raises(InvalidCredentialsError):
        await UpdateSecurityUseCase(uow).execute(
            str(user.id.value),
            UpdateSecurityRequestDTO(
                current_password=CLAVE, new_password=NUEVA, confirm_password=NUEVA
            ),
        )

    final = await uow.users.find_by_id(user.id)
    assert final.verify_password(OTRA)
    assert not final.verify_password(NUEVA)


async def test_b2_3_the_new_email_is_taken_during_the_bcrypt(monkeypatch):
    """
    Given: Un cambio de correo a uno libre
    When: Otro se registra con ese correo mientras se calcula el bcrypt
    Then: «correo en uso», y no queda pendiente
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)

    async def otro_lo_coge():
        await _con_usuario(uow, "nuevo@example.com")

    _entretanto(monkeypatch, update_security_use_case, otro_lo_coge)

    with pytest.raises(DuplicateEmailError):
        await UpdateSecurityUseCase(uow, AsyncMock()).execute(
            str(user.id.value),
            UpdateSecurityRequestDTO(current_password=CLAVE, new_email="nuevo@example.com"),
        )

    final = await uow.users.find_by_id(user.id)
    assert final.pending_email is None


async def test_b2_3_errors_in_the_usual_order_wrong_password_first():
    """
    Given: La actual mal tecleada Y un correo nuevo ocupado
    When: Se pide el cambio
    Then: «contraseña actual incorrecta», como antes (sin desvelar que el correo existe)
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)
    await _con_usuario(uow, "ocupado@example.com")

    with pytest.raises(InvalidCredentialsError):
        await UpdateSecurityUseCase(uow).execute(
            str(user.id.value),
            UpdateSecurityRequestDTO(
                current_password="Mal4$Clave000", new_email="ocupado@example.com"
            ),
        )


async def test_b2_6_a_weak_new_password_costs_no_bcrypt_of_its_own():
    """
    Given: Una contraseña nueva que no cumple la política
    When: Se pide el cambio
    Then: Error de política, y solo el bcrypt de la actual: ninguno con la nueva
    """
    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)

    with (
        patch.object(Password, "_hash_password", wraps=Password._hash_password) as hashes,
        pytest.raises(InvalidPasswordError),
    ):
        await UpdateSecurityUseCase(uow).execute(
            str(user.id.value),
            UpdateSecurityRequestDTO(
                current_password=CLAVE, new_password=DEBIL, confirm_password=DEBIL
            ),
        )

    assert hashes.call_count == 0


# --- B2-4 restablecer ----------------------------------------------------------------


async def _con_token(uow: InMemoryUnitOfWork) -> tuple[User, str]:
    user = await _con_usuario(uow)
    token = user.generate_password_reset_token()
    async with uow:
        await uow.users.save(user)
    return user, token


async def test_b2_4_someone_spends_the_token_during_the_bcrypt(monkeypatch):
    """
    Given: Un enlace de restablecer válido
    When: Otro lo gasta mientras se calcula el bcrypt
    Then: «enlace no válido», y la contraseña es la que puso el otro
    """
    uow = InMemoryUnitOfWork()
    user, token = await _con_token(uow)

    async def otro_lo_gasta():
        async with uow:
            otro = await uow.users.find_by_id(user.id)
            otro.reset_password(token, Password.from_plain_text(OTRA))
            await uow.users.save(otro)

    _entretanto(monkeypatch, reset_password_use_case, otro_lo_gasta)

    with pytest.raises(InvalidResetTokenError):
        await ResetPasswordUseCase(uow, AsyncMock()).execute(
            ResetPasswordRequestDTO(token=token, new_password=NUEVA)
        )

    final = await uow.users.find_by_id(user.id)
    assert final.verify_password(OTRA)


async def test_b2_4_an_expired_or_wrong_token_costs_no_bcrypt():
    """
    Given: Un usuario con un enlace que ya no vale (caducado)
    When: Se intenta restablecer
    Then: «enlace no válido» sin calcular ningún bcrypt
    """
    from datetime import datetime, timedelta

    uow = InMemoryUnitOfWork()
    user, token = await _con_token(uow)
    user._reset_token_expires_at = datetime.now() - timedelta(minutes=1)

    with (
        patch.object(Password, "_hash_password", wraps=Password._hash_password) as hashes,
        pytest.raises(InvalidResetTokenError),
    ):
        await ResetPasswordUseCase(uow, AsyncMock()).execute(
            ResetPasswordRequestDTO(token=token, new_password=NUEVA)
        )

    assert hashes.call_count == 0


async def test_b2_6_a_weak_password_on_reset_costs_no_bcrypt():
    uow = InMemoryUnitOfWork()
    _user, token = await _con_token(uow)

    with (
        patch.object(Password, "_hash_password", wraps=Password._hash_password) as hashes,
        pytest.raises(ValueError),
    ):
        await ResetPasswordUseCase(uow, AsyncMock()).execute(
            ResetPasswordRequestDTO(token=token, new_password=DEBIL)
        )

    assert hashes.call_count == 0


# --- B2-5 cuenta de sistema ----------------------------------------------------------


async def test_b2_5_another_process_creates_it_during_the_bcrypt(monkeypatch):
    """
    Given: La cuenta de sistema no existe
    When: Otro proceso la crea mientras se calcula el bcrypt
    Then: Vale la suya: devuelve su id y no hay dos
    """
    uow = InMemoryUnitOfWork()
    correo = "course.import@rydercupfriends.com"
    creada = {}

    async def otro_proceso():
        creada["id"] = await EnsureSystemUserUseCase(InMemoryUnitOfWorkCompartida(uow)).execute(
            correo
        )

    _entretanto(monkeypatch, ensure_system_user_use_case, otro_proceso)

    devuelto = await EnsureSystemUserUseCase(uow).execute(correo)

    assert devuelto == creada["id"]


class InMemoryUnitOfWorkCompartida:
    """La misma memoria que otra unidad de trabajo: dos procesos, una BD."""

    def __init__(self, base: InMemoryUnitOfWork):
        self._base = base

    def __getattr__(self, nombre):
        return getattr(self._base, nombre)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_b2_3_a_reused_password_is_reported_before_hashing_it():
    """
    Given: Un usuario cuya contraseña nueva ya está en su historial
    When: La pide
    Then: «repetida» (el orden de antes) y sin gastar el bcrypt de la nueva: solo los
          de comprobar (la actual y el historial)
    """
    from src.modules.user.domain.entities.password_history import PasswordHistory

    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)
    vieja = Password.from_plain_text(NUEVA)
    async with uow:
        await uow.password_history.save(
            PasswordHistory.create(
                user_id=user.id, password_hash=vieja.hashed_value, total_history_count=1
            )
        )

    with (
        patch.object(Password, "_hash_password", wraps=Password._hash_password) as hashes,
        pytest.raises(InvalidPasswordError) as error,
    ):
        await UpdateSecurityUseCase(uow).execute(
            str(user.id.value),
            UpdateSecurityRequestDTO(
                current_password=CLAVE, new_password=NUEVA, confirm_password=NUEVA
            ),
        )

    assert error.value.error_code == "PASSWORD_REUSED"
    assert hashes.call_count == 0


async def test_b2_6_a_weak_new_password_skips_the_history_bcrypts():
    """
    Given: Un usuario con historial y una contraseña nueva débil
    When: La pide
    Then: Error de política sin comparar con el historial: solo el bcrypt de la actual
    """
    from src.modules.user.domain.entities.password_history import PasswordHistory

    uow = InMemoryUnitOfWork()
    user = await _con_usuario(uow)
    async with uow:
        for clave in (NUEVA, OTRA):
            await uow.password_history.save(
                PasswordHistory.create(
                    user_id=user.id,
                    password_hash=Password.from_plain_text(clave).hashed_value,
                    total_history_count=1,
                )
            )

    with (
        patch.object(Password, "verify", autospec=True, side_effect=Password.verify) as verifica,
        pytest.raises(InvalidPasswordError),
    ):
        await UpdateSecurityUseCase(uow).execute(
            str(user.id.value),
            UpdateSecurityRequestDTO(
                current_password=CLAVE, new_password=DEBIL, confirm_password=DEBIL
            ),
        )

    assert verifica.call_count == 1

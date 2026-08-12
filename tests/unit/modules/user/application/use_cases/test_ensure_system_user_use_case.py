"""
Tests de la cuenta de sistema que figura como autora de los datos importados.

Lo que se protege: que nazca desactivada (no puede iniciar sesión ni salir en
la búsqueda de jugadores) y que reimportar no cree una segunda cuenta.
"""

import pytest

from src.modules.user.application.use_cases.ensure_system_user_use_case import (
    EnsureSystemUserUseCase,
    _generate_unusable_password,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.infrastructure.persistence.in_memory.in_memory_user_repository import (
    InMemoryUserRepository,
)

SYSTEM_EMAIL = "course.import@rydercupfriends.com"


class FakeUserUnitOfWork:
    """Unit of Work mínimo sobre el repositorio en memoria."""

    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.committed = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.committed += 1

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        pass


@pytest.mark.asyncio
async def test_creates_the_account_when_it_does_not_exist():
    """
    GIVEN: Ninguna cuenta de sistema
    WHEN: Se pide asegurarla
    THEN: Se crea y se devuelve su id
    """
    uow = FakeUserUnitOfWork()
    use_case = EnsureSystemUserUseCase(uow)

    user_id = await use_case.execute(SYSTEM_EMAIL)

    created = await uow.users.find_by_email(Email(SYSTEM_EMAIL))
    assert created is not None
    assert created.id == user_id


@pytest.mark.asyncio
async def test_the_account_is_created_deactivated():
    """
    GIVEN: Una cuenta de sistema recién creada
    WHEN: Se consulta
    THEN: Está desactivada, así que no puede iniciar sesión ni aparecer en la
          búsqueda de jugadores
    """
    uow = FakeUserUnitOfWork()
    use_case = EnsureSystemUserUseCase(uow)

    await use_case.execute(SYSTEM_EMAIL)

    created = await uow.users.find_by_email(Email(SYSTEM_EMAIL))
    assert created is not None
    assert created.is_active is False


@pytest.mark.asyncio
async def test_the_account_is_not_an_admin():
    """
    GIVEN: Una cuenta de sistema recién creada
    WHEN: Se consulta
    THEN: No tiene privilegios de administración: solo figura como autora
    """
    uow = FakeUserUnitOfWork()
    use_case = EnsureSystemUserUseCase(uow)

    await use_case.execute(SYSTEM_EMAIL)

    created = await uow.users.find_by_email(Email(SYSTEM_EMAIL))
    assert created is not None
    assert created.is_admin is False


@pytest.mark.asyncio
async def test_it_does_not_appear_in_player_search():
    """
    GIVEN: Una cuenta de sistema creada
    WHEN: Alguien busca jugadores por su nombre
    THEN: No aparece
    """
    uow = FakeUserUnitOfWork()
    use_case = EnsureSystemUserUseCase(uow)

    await use_case.execute(SYSTEM_EMAIL, first_name="Importador", last_name="Automatico")

    results = await uow.users.search_by_partial_name("Importador")

    assert results == []


@pytest.mark.asyncio
async def test_running_it_twice_reuses_the_same_account():
    """
    GIVEN: Una cuenta de sistema que ya existe
    WHEN: Se vuelve a pedir, como haría una reimportación
    THEN: Devuelve la misma y no crea otra
    """
    uow = FakeUserUnitOfWork()
    use_case = EnsureSystemUserUseCase(uow)

    first = await use_case.execute(SYSTEM_EMAIL)
    second = await use_case.execute(SYSTEM_EMAIL)

    assert first == second
    assert len(await uow.users.find_all()) == 1


@pytest.mark.asyncio
async def test_it_refuses_an_active_account_with_that_email():
    """
    GIVEN: Una persona registrada con el correo de la cuenta de sistema
    WHEN: Se pide asegurar la cuenta
    THEN: Falla en vez de devolverla

    Seguir adelante ataría los campos importados a una cuenta personal.
    """
    uow = FakeUserUnitOfWork()
    impostor = User.create(
        first_name="Persona",
        last_name="Real",
        email_str=SYSTEM_EMAIL,
        plain_password="ValidPassword123!",
    )
    await uow.users.save(impostor)
    use_case = EnsureSystemUserUseCase(uow)

    with pytest.raises(ValueError, match="is active"):
        await use_case.execute(SYSTEM_EMAIL)


@pytest.mark.asyncio
async def test_it_refuses_an_administrator_account_with_that_email():
    """
    GIVEN: Una cuenta administradora con el correo de la cuenta de sistema
    WHEN: Se pide asegurar la cuenta
    THEN: Falla: la cuenta de sistema no debe tener privilegios
    """
    uow = FakeUserUnitOfWork()
    admin = User.create(
        first_name="Admin",
        last_name="Suplantado",
        email_str=SYSTEM_EMAIL,
        plain_password="ValidPassword123!",
        is_admin=True,
    )
    admin.deactivate(deactivated_by_user_id=str(admin.id.value))
    await uow.users.save(admin)
    use_case = EnsureSystemUserUseCase(uow)

    with pytest.raises(ValueError, match="administrator"):
        await use_case.execute(SYSTEM_EMAIL)


def test_the_generated_password_satisfies_the_policy():
    """
    GIVEN: La contraseña que se genera para la cuenta de sistema
    WHEN: Se construye el Value Object, que es quien aplica la política
    THEN: No falla, de modo que crear la cuenta nunca se cae por azar

    Se repite porque la contraseña es aleatoria: una sola pasada podría no
    destapar que falta una clase de caracteres.
    """
    for _ in range(20):
        Password.from_plain_text(_generate_unusable_password())


def test_two_generated_passwords_are_different():
    """
    GIVEN: Dos contraseñas generadas
    WHEN: Se comparan
    THEN: No coinciden: son aleatorias, no un valor fijo en el código
    """
    assert _generate_unusable_password() != _generate_unusable_password()

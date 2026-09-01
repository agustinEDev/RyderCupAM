"""
Tests de la búsqueda por nombre en el repositorio en memoria.

El doble tiene que comportarse igual que el real en lo que a visibilidad se
refiere: si diverge, los tests que lo usan darían por buena una búsqueda que en
producción devuelve cuentas desactivadas.
"""

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_user_repository import (
    InMemoryUserRepository,
)


def build_user(first_name: str, last_name: str, email: str) -> User:
    """Crea un usuario válido."""
    return User.create(
        first_name=first_name,
        last_name=last_name,
        email_str=email,
        plain_password="ValidPassword123!",
    )


@pytest.mark.asyncio
async def test_search_excludes_deactivated_accounts():
    """
    GIVEN: Una cuenta activa y otra desactivada con el mismo apellido
    WHEN: Se busca por ese apellido
    THEN: Solo aparece la activa
    """
    repository = InMemoryUserRepository()
    active = build_user("Alicia", "Buscable", "alicia@example.com")
    deactivated = build_user("Alberto", "Buscable", "alberto@example.com")
    deactivated.deactivate(deactivated_by_user_id=str(active.id.value))
    await repository.save(active)
    await repository.save(deactivated)

    results = await repository.search_by_partial_name("Buscable")

    found_ids = {user.id for user in results}
    assert active.id in found_ids
    assert deactivated.id not in found_ids


@pytest.mark.asyncio
async def test_search_finds_a_reactivated_account():
    """
    GIVEN: Una cuenta desactivada y vuelta a activar
    WHEN: Se busca por su apellido
    THEN: Aparece, porque el filtro mira el estado actual
    """
    repository = InMemoryUserRepository()
    admin = build_user("Admin", "Gestor", "admin@example.com")
    user = build_user("Regreso", "Reactivado", "regreso@example.com")
    user.deactivate(deactivated_by_user_id=str(admin.id.value))
    user.reactivate(reactivated_by_user_id=str(admin.id.value))
    await repository.save(user)

    results = await repository.search_by_partial_name("Reactivado")

    assert user.id in {found.id for found in results}


@pytest.mark.asyncio
async def test_the_limit_counts_only_visible_accounts():
    """
    GIVEN: Varias cuentas desactivadas y una activa que comparten apellido
    WHEN: Se busca con un límite de 2
    THEN: La activa sale igualmente

    Las desactivadas se descartan antes de contar; si consumieran cupo, una
    cuenta legítima podría quedar fuera de los resultados por culpa de cuentas
    que nadie debería ver.
    """
    repository = InMemoryUserRepository()
    admin = build_user("Admin", "Gestor", "admin2@example.com")
    for index in range(3):
        hidden = build_user(f"Oculto{index}", "Compartido", f"oculto{index}@example.com")
        hidden.deactivate(deactivated_by_user_id=str(admin.id.value))
        await repository.save(hidden)
    visible = build_user("Visible", "Compartido", "visible@example.com")
    await repository.save(visible)

    results = await repository.search_by_partial_name("Compartido", limit=2)

    assert visible.id in {found.id for found in results}


@pytest.mark.asyncio
async def test_search_finds_a_user_by_their_alias():
    """
    GIVEN: Una cuenta cuyo alias no se parece a su nombre
    WHEN: Se busca por el alias
    THEN: Aparece — sin esto, ponerse un apodo te haría invisible para quien
          solo te conoce por él
    """
    repository = InMemoryUserRepository()
    user = build_user("Agustin", "Estevez", "agustin@example.com")
    user.update_profile(alias="Chuchi")
    await repository.save(user)

    results = await repository.search_by_partial_name("Chuchi")

    assert [found.id for found in results] == [user.id]


@pytest.mark.asyncio
async def test_search_by_alias_matches_a_fragment_and_ignores_case():
    """
    GIVEN: Una cuenta con alias "Chuchi"
    WHEN: Se busca "chu"
    THEN: Aparece, igual que ocurre con el nombre
    """
    repository = InMemoryUserRepository()
    user = build_user("Agustin", "Estevez", "agustin2@example.com")
    user.update_profile(alias="Chuchi")
    await repository.save(user)

    results = await repository.search_by_partial_name("chu")

    assert [found.id for found in results] == [user.id]


@pytest.mark.asyncio
async def test_search_by_alias_still_excludes_deactivated_accounts():
    """
    GIVEN: Una cuenta desactivada cuyo alias casa con la búsqueda
    WHEN: Se busca por ese alias
    THEN: No aparece — el alias no es una puerta trasera a la regla de
          visibilidad que protege a quien pidió desactivarse
    """
    repository = InMemoryUserRepository()
    active = build_user("Alicia", "Activa", "alicia2@example.com")
    deactivated = build_user("Alberto", "Inactivo", "alberto2@example.com")
    deactivated.update_profile(alias="Escondido")
    deactivated.deactivate(deactivated_by_user_id=str(active.id.value))
    await repository.save(active)
    await repository.save(deactivated)

    results = await repository.search_by_partial_name("Escondido")

    assert results == []


@pytest.mark.asyncio
async def test_search_still_finds_users_without_an_alias():
    """
    GIVEN: Una cuenta sin alias
    WHEN: Se busca por su apellido
    THEN: Sigue apareciendo — la rama nueva del OR no puede tapar a nadie
    """
    repository = InMemoryUserRepository()
    user = build_user("Ana", "Sinalias", "ana@example.com")
    await repository.save(user)

    results = await repository.search_by_partial_name("Sinalias")

    assert [found.id for found in results] == [user.id]

"""
Tests del autocompletado de jugadores (SearchUsersUseCase).

Quien busca no se encuentra a sí mismo (FE #938, 26 oct 2026): el caso de uso
se lo pasa al repositorio para que lo deje fuera en la propia consulta.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.user.application.dto.user_dto import SearchUsersRequestDTO
from src.modules.user.application.use_cases.search_users_use_case import SearchUsersUseCase
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


@pytest.fixture
def uow():
    """Unidad de trabajo falsa sin resultados."""
    falsa = AsyncMock()
    falsa.users = AsyncMock()
    falsa.users.search_by_partial_name = AsyncMock(return_value=[])
    falsa.__aenter__ = AsyncMock(return_value=falsa)
    falsa.__aexit__ = AsyncMock(return_value=None)
    return falsa


async def test_search_with_a_viewer_excludes_the_viewer_in_the_repository(uow):
    """
    GIVEN: Un jugador que busca «Garc»
    WHEN: Se ejecuta la búsqueda
    THEN: El repositorio recibe a quien busca para dejarlo fuera
    """
    quien = uuid4()

    await SearchUsersUseCase(uow).execute(
        SearchUsersRequestDTO(query=" Garc ", viewer_id=str(quien))
    )

    uow.users.search_by_partial_name.assert_awaited_once_with(
        "Garc", limit=SearchUsersUseCase.MAX_RESULTS, exclude_user_id=UserId(quien)
    )


async def test_search_with_a_short_query_returns_nothing_without_asking(uow):
    """
    GIVEN: Una búsqueda de un solo carácter
    WHEN: Se ejecuta
    THEN: No hay resultados y no se consulta el repositorio
    """
    respuesta = await SearchUsersUseCase(uow).execute(
        SearchUsersRequestDTO(query="G", viewer_id=str(uuid4()))
    )

    assert respuesta.users == []
    uow.users.search_by_partial_name.assert_not_awaited()

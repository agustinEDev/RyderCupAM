"""
Sin pistas del bloqueo para quien fue bloqueado (F-09, revisión de la fase 3, 10 nov 2026).

Quien me bloqueó no existe para mí: lo que de él pida responde como una cuenta
que no está. Si lo bloqueé yo, todo como hoy (403 de «solo amigos» y 403 de
solicitud con bloqueo: soy yo quien lo sabe).

  B1 su actividad: 404 (ProfileNotVisibleError), como inexistente
  B2 las partidas juntos: 404
  B3 su galería de fotos: 404
  B4 mandarle una solicitud: el 404 de un destinatario que no existe
  B5 si lo bloqueé yo: actividad, partidas y galería, el 403 de no ser amigos;
     la solicitud, el 403 del bloqueo, como hoy
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.social.application.dto.friendship_dto import SendFriendRequestRequestDTO
from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    AddresseeNotFoundError,
    GamesTogetherNotVisibleError,
    ProfileNotVisibleError,
)
from src.modules.social.application.use_cases.get_games_together_use_case import (
    GetGamesTogetherUseCase,
)
from src.modules.social.application.use_cases.get_player_activity_use_case import (
    GetPlayerActivityUseCase,
)
from src.modules.social.application.use_cases.get_player_profile_use_case import (
    GetPlayerProfileUseCase,
)
from src.modules.social.application.use_cases.get_profile_gallery_use_case import (
    GetProfileGalleryUseCase,
)
from src.modules.social.application.use_cases.send_friend_request_use_case import (
    SendFriendRequestUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import BlockedUserViolation
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


async def _usuario(user_uow) -> User:
    user = User.create(
        first_name="Luis",
        last_name="Perez",
        email_str=f"pistas_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _bloqueo(social_uow, quien: User, a_quien: User) -> None:
    async with social_uow:
        await social_uow.friendships.add(
            Friendship.create_blocked(
                id=FriendshipId(uuid4()), blocker_id=quien.id, blocked_id=a_quien.id
            )
        )


def _actividad(social_uow, user_uow):
    caso = GetPlayerActivityUseCase(social_uow, user_uow, AsyncMock())
    return lambda yo, el: caso.execute(str(yo.id.value), str(el.id.value))


def _partidas(social_uow, user_uow):
    compartidas = AsyncMock()
    compartidas.between.return_value = []
    caso = GetGamesTogetherUseCase(social_uow, user_uow, compartidas)
    return lambda yo, el: caso.execute(str(yo.id.value), str(el.id.value))


def _galeria(social_uow, user_uow):
    caso = GetProfileGalleryUseCase(social_uow, user_uow)
    return lambda yo, el: caso.execute(str(yo.id.value), str(el.id.value))


def _solicitud(social_uow, user_uow):
    caso = SendFriendRequestUseCase(social_uow, user_uow)
    return lambda yo, el: caso.execute(
        SendFriendRequestRequestDTO(requester_id=yo.id.value, addressee_id=el.id.value)
    )


LO_SUYO = {
    "actividad": (_actividad, ActivityNotVisibleError),
    "partidas": (_partidas, GamesTogetherNotVisibleError),
    "galeria": (_galeria, ActivityNotVisibleError),
}


@pytest.mark.parametrize("que", sorted(LO_SUYO))
async def test_b1_b3_si_me_bloqueo_lo_suyo_no_existe_para_mi(social_uow, user_uow, que):
    """
    Given: Él me bloqueó
    When: Pido su actividad, nuestras partidas juntos o su galería
    Then: ProfileNotVisibleError («Profile not found»), lo mismo que una cuenta que no está
    """
    yo, el = await _usuario(user_uow), await _usuario(user_uow)
    await _bloqueo(social_uow, el, yo)
    pide = LO_SUYO[que][0](social_uow, user_uow)

    with pytest.raises(ProfileNotVisibleError, match="^Profile not found$"):
        await pide(yo, el)


@pytest.mark.parametrize("que", sorted(LO_SUYO))
async def test_b5_si_lo_bloquee_yo_es_el_403_de_siempre(social_uow, user_uow, que):
    """
    Given: Lo bloqueé yo
    When: Pido su actividad, nuestras partidas juntos o su galería
    Then: El 403 de no ser amigos, como hoy
    """
    yo, el = await _usuario(user_uow), await _usuario(user_uow)
    await _bloqueo(social_uow, yo, el)
    crea, error_de_siempre = LO_SUYO[que]

    with pytest.raises(error_de_siempre):
        await crea(social_uow, user_uow)(yo, el)


async def test_b4_si_me_bloqueo_la_solicitud_es_la_de_alguien_que_no_existe(social_uow, user_uow):
    """
    Given: Él me bloqueó
    When: Le mando una solicitud de amistad
    Then: AddresseeNotFoundError con el texto de un destinatario que no existe
    """
    yo, el = await _usuario(user_uow), await _usuario(user_uow)
    await _bloqueo(social_uow, el, yo)

    with pytest.raises(AddresseeNotFoundError, match=f"^User not found: {el.id.value}$"):
        await _solicitud(social_uow, user_uow)(yo, el)


async def test_b5_si_lo_bloquee_yo_la_solicitud_dice_el_bloqueo(social_uow, user_uow):
    """
    Given: Lo bloqueé yo
    When: Le mando una solicitud
    Then: BlockedUserViolation, como hoy
    """
    yo, el = await _usuario(user_uow), await _usuario(user_uow)
    await _bloqueo(social_uow, yo, el)

    with pytest.raises(BlockedUserViolation):
        await _solicitud(social_uow, user_uow)(yo, el)


async def _bloqueo_sin_autor(social_uow, a: User, b: User) -> None:
    """Una fila BLOCKED con `blocked_by` NULL: el CHECK de la tabla la admite."""
    async with social_uow:
        await social_uow.friendships.add(
            Friendship.reconstruct(
                id=FriendshipId(uuid4()),
                requester_id=a.id,
                addressee_id=b.id,
                status=FriendshipStatus.BLOCKED,
                blocked_by=None,
            )
        )


async def test_b6_bloqueo_sin_autor_el_perfil_se_ve_como_hoy(social_uow, user_uow):
    """
    Given: Una fila BLOCKED sin `blocked_by` entre los dos
    When: Abro su perfil
    Then: Se ve (nadie me bloqueó: la misma regla que en lo demás), con el bloqueo
        y sin «lo bloqueé yo», como antes de esta release
    """
    yo, el = await _usuario(user_uow), await _usuario(user_uow)
    await _bloqueo_sin_autor(social_uow, el, yo)
    stats = AsyncMock()

    perfil = await GetPlayerProfileUseCase(social_uow, user_uow, stats).execute(
        str(yo.id.value), str(el.id.value)
    )

    assert perfil.friendship.status == "BLOCKED"
    assert perfil.blocked_by_me is False


@pytest.mark.parametrize("que", sorted(LO_SUYO))
async def test_b6_bloqueo_sin_autor_lo_demas_es_el_403_de_siempre(social_uow, user_uow, que):
    """
    Given: Una fila BLOCKED sin `blocked_by`
    When: Pido su actividad, nuestras partidas juntos o su galería
    Then: El 403 de no ser amigos: nadie me bloqueó
    """
    yo, el = await _usuario(user_uow), await _usuario(user_uow)
    await _bloqueo_sin_autor(social_uow, el, yo)
    crea, error_de_siempre = LO_SUYO[que]

    with pytest.raises(error_de_siempre):
        await crea(social_uow, user_uow)(yo, el)

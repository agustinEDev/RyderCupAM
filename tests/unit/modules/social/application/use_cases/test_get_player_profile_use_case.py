"""
Tests del perfil de un jugador (BE #176).

Lo que importa aqui es el guard: **la amistad decide si se responde, no cuanto
se responde**. Quien no es amigo recibe exactamente el mismo error que si la
cuenta no existiera, para que probar identificadores no sirva de detector de
cuentas.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.social.application.exceptions import ProfileNotVisibleError
from src.modules.social.application.use_cases.get_player_profile_use_case import (
    GetPlayerProfileUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.application.dto.player_stats_dto import PlayerStatsResponseDTO
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


@pytest.fixture
def stats():
    """Las estadisticas se prueban en su propio caso de uso; aqui solo se reutilizan."""
    fake = AsyncMock()
    fake.execute.return_value = PlayerStatsResponseDTO(handicap=12.3, rounds_played=7)
    return fake


async def _create_user(user_uow, handicap: float | None = None, active: bool = True) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"perfil_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if handicap is not None:
        user.update_handicap(handicap)
    if not active:
        user.deactivate(deactivated_by_user_id=str(user.id.value))
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _hacer_amigos(social_uow, a: User, b: User) -> Friendship:
    friendship = Friendship.create(
        id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id
    )
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)
    return friendship


def _use_case(social_uow, user_uow, stats):
    return GetPlayerProfileUseCase(social_uow, user_uow, stats)


class TestGuardDeAmistad:
    async def test_un_amigo_ve_el_perfil(self, social_uow, user_uow, stats):
        """Given dos amigos / When uno pide el perfil del otro / Then lo recibe."""
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow, handicap=8.4)
        await _hacer_amigos(social_uow, ana, luis)

        perfil = await _use_case(social_uow, user_uow, stats).execute(
            str(ana.id.value), str(luis.id.value)
        )

        assert perfil.id == str(luis.id.value)
        assert perfil.first_name == "Ana"
        assert perfil.handicap == 8.4
        assert perfil.stats.rounds_played == 7

    async def test_un_desconocido_ve_la_ficha_pero_no_lo_de_detras(
        self, social_uow, user_uow, stats
    ):
        """
        Given dos usuarios sin amistad / When uno pide el perfil / Then ve
        nombre, apellidos y foto, pero ni handicap ni estadisticas.

        La ficha minima es lo que permite reconocer a alguien encontrado por su
        nombre antes de mandarle una solicitud.
        """
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow, handicap=8.4)

        perfil = await _use_case(social_uow, user_uow, stats).execute(
            str(ana.id.value), str(luis.id.value)
        )

        assert perfil.first_name == "Ana"
        assert perfil.avatar_source is not None
        assert perfil.is_friend is False
        assert perfil.friendship.status == "NONE"
        assert perfil.handicap is None
        assert perfil.stats is None

    async def test_lo_privado_llega_en_none_y_no_a_cero(self, social_uow, user_uow, stats):
        """
        Given un perfil de alguien que no es amigo / When se pide / Then el
        handicap llega en None, no en 0: un cero se leeria como "juega fatal"
        en lugar de "esto no se puede ver".
        """
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow, handicap=8.4)

        perfil = await _use_case(social_uow, user_uow, stats).execute(
            str(ana.id.value), str(luis.id.value)
        )

        assert perfil.handicap is None
        assert perfil.stats is None

    async def test_una_solicitud_pendiente_no_da_acceso_pero_si_se_distingue(
        self, social_uow, user_uow, stats
    ):
        """
        Given una solicitud enviada sin responder / When se pide el perfil /
        Then sigue sin verse lo privado, pero el estado dice que ya se mando:
        el cliente necesita saberlo para no ofrecer "enviar solicitud" otra vez.
        """
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        pendiente = Friendship.create(
            id=FriendshipId(uuid4()), requester_id=ana.id, addressee_id=luis.id
        )
        async with social_uow:
            await social_uow.friendships.add(pendiente)

        perfil = await _use_case(social_uow, user_uow, stats).execute(
            str(ana.id.value), str(luis.id.value)
        )

        assert perfil.friendship.status == "PENDING_SENT"
        assert perfil.friendship.friendship_id == str(pendiente.id.value)
        assert perfil.stats is None

    async def test_quien_recibio_la_solicitud_la_ve_como_recibida(
        self, social_uow, user_uow, stats
    ):
        """
        Given una solicitud que me han mandado / When miro su perfil / Then el
        estado es PENDING_RECEIVED, que no lleva al mismo boton que la enviada.
        """
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        pendiente = Friendship.create(
            id=FriendshipId(uuid4()), requester_id=ana.id, addressee_id=luis.id
        )
        async with social_uow:
            await social_uow.friendships.add(pendiente)

        perfil = await _use_case(social_uow, user_uow, stats).execute(
            str(luis.id.value), str(ana.id.value)
        )

        assert perfil.friendship.status == "PENDING_RECEIVED"

    async def test_deshacer_la_amistad_retira_lo_privado_al_instante(
        self, social_uow, user_uow, stats
    ):
        """
        Given dos que eran amigos / When se deshace la amistad / Then la ficha
        sigue viendose pero las estadisticas desaparecen en la peticion
        siguiente, sin cache que las sostenga.
        """
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow, handicap=8.4)
        friendship = await _hacer_amigos(social_uow, ana, luis)
        use_case = _use_case(social_uow, user_uow, stats)
        assert (await use_case.execute(str(ana.id.value), str(luis.id.value))).stats is not None

        async with social_uow:
            await social_uow.friendships.remove(friendship)

        despues = await use_case.execute(str(ana.id.value), str(luis.id.value))
        assert despues.first_name == "Ana"
        assert despues.stats is None
        assert despues.handicap is None

    async def test_uno_siempre_puede_ver_su_propio_perfil(self, social_uow, user_uow, stats):
        """
        Given un jugador sin amigos / When pide su propio perfil / Then lo ve:
        no hace falta ser amigo de uno mismo.
        """
        ana = await _create_user(user_uow, handicap=15.0)

        perfil = await _use_case(social_uow, user_uow, stats).execute(
            str(ana.id.value), str(ana.id.value)
        )

        assert perfil.id == str(ana.id.value)


class TestLoQueDeVerdadNoEsta:
    async def test_una_cuenta_que_no_existe_no_se_ve(self, social_uow, user_uow, stats):
        """
        Given un id inventado / When se pide su perfil / Then no hay perfil.

        El 404 se reserva para lo que de verdad no esta. Ya no cubre "existe
        pero no sois amigos": desde que los jugadores se buscan por nombre, su
        existencia es publica por diseño y fingir lo contrario solo impediria
        mandarles una solicitud.
        """
        ana = await _create_user(user_uow)

        with pytest.raises(ProfileNotVisibleError):
            await _use_case(social_uow, user_uow, stats).execute(
                str(ana.id.value), str(uuid4())
            )

    async def test_una_cuenta_dada_de_baja_no_se_ve_ni_siendo_amigos(
        self, social_uow, user_uow, stats
    ):
        """Given un amigo con la cuenta desactivada / When se pide / Then no se ve."""
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow, active=False)
        await _hacer_amigos(social_uow, ana, luis)

        with pytest.raises(ProfileNotVisibleError):
            await _use_case(social_uow, user_uow, stats).execute(
                str(ana.id.value), str(luis.id.value)
            )

    async def test_el_perfil_nunca_lleva_el_correo(self, social_uow, user_uow, stats):
        """
        Given dos amigos / When uno mira el perfil del otro / Then no hay correo
        ni siquiera entre amigos: esto es su perfil de golf, no su ficha de
        usuario.
        """
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        await _hacer_amigos(social_uow, ana, luis)

        perfil = await _use_case(social_uow, user_uow, stats).execute(
            str(ana.id.value), str(luis.id.value)
        )

        assert "email" not in perfil.model_dump()

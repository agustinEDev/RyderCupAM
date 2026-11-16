"""
Bloqueo de los dos: la tabla de casos aprobada (SB-02, 16 nov 2026).

B bloqueó a A. Antes, si A bloqueaba a B, recibía la fila de B tal cual (sabía que
B le había bloqueado) y su bloqueo no se guardaba; si B desbloqueaba, A quedaba sin
protección. Ahora se guardan los dos, cada uno ve solo el suyo y el del otro sigue
en pie si uno desbloquea. Los números son los de la tabla (notas/sb02-diseno.md).
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.social.application.dto.friendship_dto import RespondFriendRequestRequestDTO
from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    FriendshipNotFoundError,
    GamesTogetherNotVisibleError,
    NotFriendshipParticipantError,
)
from src.modules.social.application.use_cases.block_user_use_case import BlockUserUseCase
from src.modules.social.application.use_cases.get_player_profile_use_case import (
    GetPlayerProfileUseCase,
)
from src.modules.social.application.use_cases.remove_friend_use_case import RemoveFriendUseCase
from src.modules.social.application.use_cases.respond_friend_request_use_case import (
    RespondFriendRequestUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import BlockedUserViolation
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.adapters.bloqueos_adapter import BloqueosAdapter
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from tests.unit.modules.social.application.use_cases.test_pistas_del_bloqueo import (
    _actividad,
    _galeria,
    _partidas,
    _solicitud,
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
        first_name="Ana",
        last_name="Lopez",
        email_str=f"dos_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _bloquea(social_uow, user_uow, quien: User, a_quien: User):
    return await BlockUserUseCase(social_uow, user_uow).execute(
        str(quien.id.value), str(a_quien.id.value)
    )


async def _desbloquea(social_uow, quien: User, friendship_id) -> None:
    await RemoveFriendUseCase(social_uow).execute(str(friendship_id), str(quien.id.value))


async def _fila(social_uow, x: User, y: User) -> Friendship | None:
    async with social_uow:
        return await social_uow.friendships.find_by_pair(x.id, y.id)


async def _perfil(social_uow, user_uow, yo: User, el: User):
    return await GetPlayerProfileUseCase(social_uow, user_uow, AsyncMock()).execute(
        str(yo.id.value), str(el.id.value)
    )


@pytest.fixture
async def los_dos(social_uow, user_uow):
    """Caso 4: B bloqueó a A y luego A bloquea a B. Devuelve (a, b, respuesta de A, de B)."""
    a, b = await _usuario(user_uow), await _usuario(user_uow)
    de_b = await _bloquea(social_uow, user_uow, b, a)
    de_a = await _bloquea(social_uow, user_uow, a, b)
    return a, b, de_a, de_b


class TestCaso4ALeBloqueaQuienYaLeBloqueo:
    async def test_se_guardan_los_dos_bloqueos(self, social_uow, los_dos):
        a, b, _, _ = los_dos

        fila = await _fila(social_uow, a, b)

        assert fila.bloqueado_por(a.id) and fila.bloqueado_por(b.id)

    async def test_la_respuesta_de_a_es_la_de_un_bloqueo_suyo_sin_nada_de_b(self, los_dos):
        """Ni `requester_id`=B ni la fecha del bloqueo de B: como si bloqueara de cero."""
        a, b, de_a, de_b = los_dos

        assert de_a.status == "BLOCKED"
        assert (de_a.requester_id, de_a.addressee_id) == (a.id.value, b.id.value)
        assert de_a.created_at == de_a.updated_at == de_a.responded_at
        assert de_a.created_at >= de_b.created_at

    async def test_las_fechas_de_a_son_las_de_su_bloqueo(self, social_uow, los_dos):
        """Las tres fechas de la respuesta de A son las de SU bloqueo, no las de la fila de B."""
        a, b, de_a, de_b = los_dos

        fila = await _fila(social_uow, a, b)

        assert de_a.created_at == de_a.updated_at == de_a.responded_at == fila.second_blocked_at
        assert (fila.created_at, fila.updated_at) == (de_b.created_at, de_b.updated_at)

    async def test_b_no_nota_nada(self, social_uow, user_uow, los_dos):
        """Caso 4 y 5: B vuelve a bloquear y recibe exactamente lo mismo que la primera vez."""
        a, b, _, de_b = los_dos

        otra_vez = await _bloquea(social_uow, user_uow, b, a)

        assert otra_vez == de_b

    async def test_a_vuelve_a_bloquear_y_recibe_lo_mismo(self, social_uow, user_uow, los_dos):
        """Caso 6."""
        a, b, de_a, _ = los_dos

        assert await _bloquea(social_uow, user_uow, a, b) == de_a


class TestCasos7a10Desbloquear:
    async def test_7_desbloquea_b_y_sigue_el_bloqueo_de_a(self, social_uow, user_uow, los_dos):
        a, b, _, de_b = los_dos

        await _desbloquea(social_uow, b, de_b.id)

        fila = await _fila(social_uow, a, b)
        assert fila.bloqueado_por(a.id) and not fila.bloqueado_por(b.id)
        assert fila.lo_oculta_a(b.id)

    async def test_8_desbloquea_a_y_sigue_el_bloqueo_de_b(self, social_uow, user_uow, los_dos):
        a, b, de_a, _ = los_dos

        await _desbloquea(social_uow, a, de_a.id)

        fila = await _fila(social_uow, a, b)
        assert fila.bloqueado_por(b.id) and not fila.bloqueado_por(a.id)
        assert fila.lo_oculta_a(a.id)

    async def test_7_y_8_desbloquean_los_dos_y_no_queda_nada(self, social_uow, user_uow, los_dos):
        a, b, de_a, de_b = los_dos

        await _desbloquea(social_uow, b, de_b.id)
        await _desbloquea(social_uow, a, de_a.id)

        assert await _fila(social_uow, a, b) is None

    async def test_9_si_solo_bloqueaba_uno_desbloquear_borra_la_fila(self, social_uow, user_uow):
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        de_a = await _bloquea(social_uow, user_uow, a, b)

        await _desbloquea(social_uow, a, de_a.id)

        assert await _fila(social_uow, a, b) is None

    async def test_10_el_bloqueado_que_conoce_el_id_recibe_un_404(self, social_uow, user_uow):
        """Antes un 403 «solo quien bloqueó…»: confirmaba el bloqueo. Ahora, como si no existiera."""
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        de_b = await _bloquea(social_uow, user_uow, b, a)

        with pytest.raises(FriendshipNotFoundError):
            await _desbloquea(social_uow, a, de_b.id)

        assert (await _fila(social_uow, a, b)).bloqueado_por(b.id)

    async def test_10_un_tercero_sigue_recibiendo_el_403_de_no_participar(
        self, social_uow, user_uow
    ):
        a, b, c = [await _usuario(user_uow) for _ in range(3)]
        de_b = await _bloquea(social_uow, user_uow, b, a)

        with pytest.raises(NotFriendshipParticipantError):
            await _desbloquea(social_uow, c, de_b.id)


class TestUnaSolicitudQueAcaboEnBloqueo:
    """
    B manda solicitud a A y luego B bloquea a A: la misma fila pasa a BLOCKED. Lo que
    A haga con el id de esa solicitud tiene que responder como si la fila no existiera,
    igual que si B la hubiera cancelado (404), no con un 409 «status BLOCKED».
    """

    async def _solicitud_que_bloquea(self, social_uow, user_uow):
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        solicitud = Friendship.create(
            id=FriendshipId.generate(), requester_id=b.id, addressee_id=a.id
        )
        async with social_uow:
            await social_uow.friendships.add(solicitud)
        await _bloquea(social_uow, user_uow, b, a)
        return a, b, solicitud.id.value

    @pytest.mark.parametrize("accion", ["ACCEPT", "DECLINE"])
    async def test_responderla_es_el_404_de_una_que_no_existe(self, social_uow, user_uow, accion):
        a, b, fila_id = await self._solicitud_que_bloquea(social_uow, user_uow)

        with pytest.raises(FriendshipNotFoundError):
            await RespondFriendRequestUseCase(social_uow, user_uow).execute(
                RespondFriendRequestRequestDTO(
                    friendship_id=fila_id, user_id=a.id.value, action=accion
                )
            )

        assert (await _fila(social_uow, a, b)).bloqueado_por(b.id)

    async def test_responderla_quien_no_es_el_destinatario_tambien_es_404(
        self, social_uow, user_uow
    ):
        """El 404 va antes de mirar quién es el destinatario: el 403 también diría que existe."""
        _a, b, fila_id = await self._solicitud_que_bloquea(social_uow, user_uow)

        with pytest.raises(FriendshipNotFoundError):
            await RespondFriendRequestUseCase(social_uow, user_uow).execute(
                RespondFriendRequestRequestDTO(
                    friendship_id=fila_id, user_id=b.id.value, action="ACCEPT"
                )
            )

    async def test_cancelar_la_suya_tras_bloquearle_el_otro_es_404(self, social_uow, user_uow):
        """A mandó la solicitud y B le bloqueó: cancelarla es el 404 de una que no existe."""
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        solicitud = Friendship.create(
            id=FriendshipId.generate(), requester_id=a.id, addressee_id=b.id
        )
        async with social_uow:
            await social_uow.friendships.add(solicitud)
        await _bloquea(social_uow, user_uow, b, a)

        with pytest.raises(FriendshipNotFoundError):
            await _desbloquea(social_uow, a, solicitud.id.value)


class TestCasos11a16LoQueVeCadaUno:
    async def test_11_la_solicitud_de_cualquiera_es_el_403_de_su_propio_bloqueo(
        self, social_uow, user_uow, los_dos
    ):
        a, b, _, _ = los_dos

        for yo, el in ((a, b), (b, a)):
            with pytest.raises(BlockedUserViolation):
                await _solicitud(social_uow, user_uow)(yo, el)

    async def test_13_cada_uno_ve_al_otro_como_bloqueado_por_mi(
        self, social_uow, user_uow, los_dos
    ):
        a, b, _, _ = los_dos

        for yo, el in ((a, b), (b, a)):
            perfil = await _perfil(social_uow, user_uow, yo, el)
            assert perfil.friendship.status == "BLOCKED"
            assert perfil.blocked_by_me is True

    async def test_14_ninguno_desaparece_en_la_busqueda_ni_en_el_avatar(self, social_uow, los_dos):
        a, b, _, _ = los_dos
        bloqueos = BloqueosAdapter(social_uow)

        for yo, el in ((a, b), (b, a)):
            assert await bloqueos.me_bloqueo(yo.id, el.id) is False
            assert el.id not in await bloqueos.quienes_me_bloquearon(yo.id)

    @pytest.mark.parametrize("pide", [_actividad, _partidas, _galeria])
    async def test_15_lo_suyo_es_el_403_de_no_ser_amigos(self, social_uow, user_uow, los_dos, pide):
        a, b, _, _ = los_dos

        for yo, el in ((a, b), (b, a)):
            with pytest.raises((ActivityNotVisibleError, GamesTogetherNotVisibleError)):
                await pide(social_uow, user_uow)(yo, el)

    async def test_16_sigue_contando_como_bloqueo_para_el_feed(self, social_uow, los_dos):
        a, b, _, _ = los_dos

        async with social_uow:
            assert b.id in await social_uow.friendships.find_blocked_ids(a.id)
            assert a.id in await social_uow.friendships.find_blocked_ids(b.id)
            assert await social_uow.friendships.are_friends(a.id, b.id) is False

    async def test_tras_desbloquear_b_vuelve_la_regla_de_f09(self, social_uow, user_uow, los_dos):
        """Caso 7: B ya no bloquea; A sí → para B, A no existe; para A, B «bloqueado por mí»."""
        a, b, _, de_b = los_dos
        await _desbloquea(social_uow, b, de_b.id)
        bloqueos = BloqueosAdapter(social_uow)

        assert await bloqueos.me_bloqueo(b.id, a.id) is True
        assert a.id in await bloqueos.quienes_me_bloquearon(b.id)
        assert (await _perfil(social_uow, user_uow, a, b)).blocked_by_me is True


class TestCarreras:
    async def test_19_los_dos_bloquean_a_la_vez_sin_fila(self, social_uow, user_uow):
        """
        Given nadie bloqueaba / When B y A bloquean a la vez y gana B el índice único
        Then A relee la fila de B y suma su bloqueo (caso 4), con su respuesta de siempre
        """
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        async with social_uow:
            await social_uow.friendships.add(
                Friendship.create_blocked(
                    id=FriendshipId.generate(), blocker_id=b.id, blocked_id=a.id
                )
            )
        original = social_uow.friendships.find_by_pair_for_update
        llamadas = 0

        async def leida_antes_de_la_de_b(x, y):
            nonlocal llamadas
            llamadas += 1
            return None if llamadas == 1 else await original(x, y)

        social_uow.friendships.find_by_pair_for_update = leida_antes_de_la_de_b

        de_a = await _bloquea(social_uow, user_uow, a, b)

        fila = await _fila(social_uow, a, b)
        assert fila.bloqueado_por(a.id) and fila.bloqueado_por(b.id)
        assert de_a.requester_id == a.id.value

    async def test_20_b_desbloquea_antes_que_a_bloquee(self, social_uow, user_uow):
        """El orden B-desbloquea → A-bloquea: la fila desapareció y A crea la suya (caso 1)."""
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        de_b = await _bloquea(social_uow, user_uow, b, a)

        await _desbloquea(social_uow, b, de_b.id)
        await _bloquea(social_uow, user_uow, a, b)

        fila = await _fila(social_uow, a, b)
        assert fila.blocked_by == a.id and fila.second_blocked_at is None

    async def test_20_a_bloquea_antes_que_b_desbloquee(self, social_uow, user_uow):
        """El orden A-bloquea → B-desbloquea: caso 4 y luego caso 7."""
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        de_b = await _bloquea(social_uow, user_uow, b, a)

        await _bloquea(social_uow, user_uow, a, b)
        await _desbloquea(social_uow, b, de_b.id)

        fila = await _fila(social_uow, a, b)
        assert fila.blocked_by == a.id and fila.second_blocked_at is None

    async def test_bloquear_y_desbloquear_leen_la_fila_bloqueada(self, social_uow, user_uow):
        """
        Lo que serializa el caso 20 en Postgres es `SELECT … FOR UPDATE` sobre la misma
        fila: bloquear y desbloquear la leen así, no con la lectura normal.
        """
        a, b = await _usuario(user_uow), await _usuario(user_uow)
        de_b = await _bloquea(social_uow, user_uow, b, a)
        repo = social_uow.friendships
        repo.find_by_pair = AsyncMock(side_effect=AssertionError("lectura sin bloquear"))
        repo.find_by_id = AsyncMock(side_effect=AssertionError("lectura sin bloquear"))

        await _bloquea(social_uow, user_uow, a, b)
        await _desbloquea(social_uow, b, de_b.id)

"""
El perfil de otro jugador, amigo o no (BE-3, tabla aprobada el 22 oct 2026).

| Caso                                                   | Resultado                              |
|--------------------------------------------------------|----------------------------------------|
| 1 No amigo                                             | Nombre, foto, nº de amigos y HÁNDICAP; |
|                                                        | lo demás en None, nunca a cero         |
| 2 No amigo sin hándicap                                | Hándicap en None                       |
| 3 Bloqueado por mí / me bloqueó                        | Sin hándicap ni nada más               |
| 4 Amigo                                                | Todo, más cara a cara y partidas juntos|
| 6 Uno mismo                                            | Sin cara a cara ni partidas juntos     |
| 8 Amigo sin partidas que contar                        | Cara a cara en None, lista vacía       |
| 11 Partidas juntos de 5 en 5, la más reciente primero  | Con cursor para «ver más»              |
| 11 Cursor corrupto                                     | Primera página                         |
| 17 «Ver más» de alguien que no es amigo                | 403 (GamesTogetherNotVisibleError)     |
| 17 «Ver más» de una cuenta que no está                 | 404 (ProfileNotVisibleError)           |
| 6 «Ver más» de uno mismo                               | Página vacía                           |
| 15 Bloquear a un amigo                                 | Deja de serlo: sin cara a cara         |
| 16 Quitar a un amigo                                   | Vuelve a NONE y se puede pedir otra vez|
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.social.application.dto.friendship_dto import SendFriendRequestRequestDTO
from src.modules.social.application.exceptions import (
    GamesTogetherNotVisibleError,
    ProfileNotVisibleError,
)
from src.modules.social.application.ports.shared_games_interface import (
    SharedGame,
    SharedGameKind,
    SharedGamesInterface,
)
from src.modules.social.application.use_cases.block_user_use_case import BlockUserUseCase
from src.modules.social.application.use_cases.get_games_together_use_case import (
    GetGamesTogetherUseCase,
)
from src.modules.social.application.use_cases.get_player_profile_use_case import (
    GetPlayerProfileUseCase,
)
from src.modules.social.application.use_cases.remove_friend_use_case import RemoveFriendUseCase
from src.modules.social.application.use_cases.send_friend_request_use_case import (
    SendFriendRequestUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.services.head_to_head import Outcome, Relation
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.application.dto.player_stats_dto import PlayerStatsResponseDTO
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

HOY = date(2026, 10, 20)


class _PartidasFijas(SharedGamesInterface):
    """Devuelve siempre las mismas partidas y apunta a quién se las pidieron."""

    def __init__(self, partidas: list[SharedGame] | None = None):
        self.partidas = partidas or []
        self.preguntas: list[tuple[UserId, UserId]] = []

    async def between(self, viewer_id: UserId, other_id: UserId) -> list[SharedGame]:
        self.preguntas.append((viewer_id, other_id))
        return list(self.partidas)


def _partida(
    dias_atras: int = 0,
    relation: Relation = Relation.AGAINST,
    outcome: Outcome | None = Outcome.WON,
    game_id: str | None = None,
) -> SharedGame:
    return SharedGame(
        kind=SharedGameKind.QUICK_MATCH,
        game_id=game_id or str(uuid4()),
        played_on=HOY - timedelta(days=dias_atras),
        golf_course_id=str(uuid4()),
        golf_course_name="El Saler",
        format="STABLEFORD",
        relation=relation,
        outcome=outcome,
    )


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def stats():
    fake = AsyncMock()
    fake.execute.return_value = PlayerStatsResponseDTO(handicap=12.3, rounds_played=7)
    return fake


async def _usuario(user_uow, handicap: float | None = None) -> User:
    user = User.create(
        first_name="Luis",
        last_name="Perez",
        email_str=f"social_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if handicap is not None:
        user.update_handicap(handicap)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _amigos(social_uow, a: User, b: User) -> Friendship:
    friendship = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)
    return friendship


async def _bloqueo(social_uow, quien: User, a_quien: User) -> None:
    friendship = Friendship.create_blocked(
        id=FriendshipId(uuid4()), blocker_id=quien.id, blocked_id=a_quien.id
    )
    async with social_uow:
        await social_uow.friendships.add(friendship)


def _perfil(social_uow, user_uow, stats, partidas: _PartidasFijas | None = None):
    return GetPlayerProfileUseCase(
        social_uow, user_uow, stats, shared_games=partidas or _PartidasFijas()
    )


def _ver_mas(social_uow, user_uow, partidas: _PartidasFijas):
    return GetGamesTogetherUseCase(social_uow, user_uow, partidas)


class TestNoAmigo:
    async def test_ve_el_handicap_pero_no_lo_de_detras(self, social_uow, user_uow, stats):
        """Caso 1: nombre, foto, amigos y hándicap; lo demás en None, nunca a cero."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow, handicap=8.4)
        await _amigos(social_uow, el, await _usuario(user_uow))
        partidas = _PartidasFijas([_partida()])

        perfil = await _perfil(social_uow, user_uow, stats, partidas).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert perfil.first_name == "Luis"
        assert perfil.handicap == 8.4
        assert perfil.friends_count == 1
        assert perfil.stats is None
        assert perfil.head_to_head is None
        assert perfil.games_together is None
        assert perfil.email is None
        # Ni se pregunta: lo que no se puede ver no se calcula
        assert partidas.preguntas == []

    async def test_sin_handicap_llega_en_none(self, social_uow, user_uow, stats):
        """Caso 2."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)

        perfil = await _perfil(social_uow, user_uow, stats).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert perfil.handicap is None

    async def test_si_lo_bloquee_no_veo_su_handicap(self, social_uow, user_uow, stats):
        """Caso 3: solo nombre y foto; el número de amigos, a 0 (no admite null)."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow, handicap=8.4)
        await _amigos(social_uow, el, await _usuario(user_uow))
        await _bloqueo(social_uow, yo, el)

        perfil = await _perfil(social_uow, user_uow, stats).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert perfil.first_name == "Luis"
        assert perfil.friendship.status == "BLOCKED"
        assert perfil.handicap is None
        assert perfil.friends_count == 0
        assert perfil.stats is None
        assert perfil.head_to_head is None
        assert perfil.games_together is None

    async def test_si_me_bloqueo_no_veo_su_handicap(self, social_uow, user_uow, stats):
        """Caso 3, del otro lado."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow, handicap=8.4)
        await _amigos(social_uow, el, await _usuario(user_uow))
        await _bloqueo(social_uow, el, yo)

        perfil = await _perfil(social_uow, user_uow, stats).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert perfil.handicap is None
        assert perfil.friends_count == 0


class TestAmigo:
    async def test_ve_todo_mas_cara_a_cara_y_partidas_juntos(self, social_uow, user_uow, stats):
        """Caso 4."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow, handicap=8.4)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas(
            [
                _partida(1, Relation.AGAINST, Outcome.WON),
                _partida(2, Relation.AGAINST, Outcome.LOST),
                _partida(3, Relation.WITH, Outcome.HALVED),
                _partida(4, Relation.AGAINST, None),
            ]
        )

        perfil = await _perfil(social_uow, user_uow, stats, partidas).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert perfil.handicap == 8.4
        assert perfil.stats is not None
        assert perfil.head_to_head is not None
        assert perfil.head_to_head.against.model_dump() == {"won": 1, "halved": 0, "lost": 1}
        assert perfil.head_to_head.alongside.model_dump() == {"won": 0, "halved": 1, "lost": 0}
        assert len(perfil.games_together.games) == 4
        assert partidas.preguntas == [(yo.id, el.id)]

    async def test_sin_partidas_que_contar_no_hay_cara_a_cara(self, social_uow, user_uow, stats):
        """Caso 8: ni un 0-0-0; la lista, vacía y no None (sí puede verla)."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)

        perfil = await _perfil(social_uow, user_uow, stats).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert perfil.head_to_head is None
        assert perfil.games_together is not None
        assert perfil.games_together.games == []
        assert perfil.games_together.next_cursor is None

    async def test_partidas_sin_resultado_salen_en_la_lista_pero_no_cuentan(
        self, social_uow, user_uow, stats
    ):
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida(outcome=None)])

        perfil = await _perfil(social_uow, user_uow, stats, partidas).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert perfil.head_to_head is None
        assert len(perfil.games_together.games) == 1
        assert perfil.games_together.games[0].result is None

    async def test_la_primera_pagina_son_las_5_mas_recientes(self, social_uow, user_uow, stats):
        """Caso 11."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida(dias) for dias in (3, 0, 6, 1, 5, 2, 4)])

        perfil = await _perfil(social_uow, user_uow, stats, partidas).execute(
            str(yo.id.value), str(el.id.value)
        )

        fechas = [g.played_on for g in perfil.games_together.games]
        assert fechas == [HOY - timedelta(days=d) for d in range(5)]
        assert perfil.games_together.next_cursor is not None

    async def test_cada_partida_lleva_su_enlace(self, social_uow, user_uow, stats):
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        rapida = _partida(0)
        torneo = SharedGame(
            kind=SharedGameKind.TOURNAMENT_MATCH,
            game_id=str(uuid4()),
            played_on=HOY - timedelta(days=1),
            golf_course_id=None,
            golf_course_name=None,
            format="FOURBALL",
            relation=Relation.WITH,
            outcome=Outcome.LOST,
            competition_id=str(uuid4()),
            competition_name="Copa",
        )
        partidas = _PartidasFijas([rapida, torneo])

        perfil = await _perfil(social_uow, user_uow, stats, partidas).execute(
            str(yo.id.value), str(el.id.value)
        )

        primera, segunda = perfil.games_together.games
        assert (primera.kind, primera.id, primera.quick_match_id) == (
            "QUICK_MATCH",
            rapida.game_id,
            rapida.game_id,
        )
        assert primera.match_id is None
        assert (primera.relation, primera.result, primera.format) == (
            "AGAINST",
            "WON",
            "STABLEFORD",
        )
        assert segunda.quick_match_id is None
        assert (segunda.competition_id, segunda.match_id) == (torneo.competition_id, torneo.game_id)
        assert (segunda.competition_name, segunda.relation, segunda.result) == (
            "Copa",
            "WITH",
            "LOST",
        )


class TestUnoMismo:
    async def test_sin_cara_a_cara_ni_partidas_juntos(self, social_uow, user_uow, stats):
        """Caso 6."""
        yo = await _usuario(user_uow, handicap=10.0)
        partidas = _PartidasFijas([_partida()])

        perfil = await _perfil(social_uow, user_uow, stats, partidas).execute(
            str(yo.id.value), str(yo.id.value)
        )

        assert perfil.handicap == 10.0
        assert perfil.head_to_head is None
        assert perfil.games_together is None
        assert partidas.preguntas == []


class TestVerMas:
    async def test_pagina_de_5_en_5_hasta_el_final(self, social_uow, user_uow):
        """Caso 11: 12 partidas, 5 + 5 + 2, sin repetir ninguna."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida(dias) for dias in range(12)])
        use_case = _ver_mas(social_uow, user_uow, partidas)

        vistas = []
        cursor = None
        paginas = 0
        while True:
            pagina = await use_case.execute(str(yo.id.value), str(el.id.value), cursor=cursor)
            paginas += 1
            vistas.extend(pagina.games)
            cursor = pagina.next_cursor
            if cursor is None:
                break

        assert paginas == 3
        assert [g.played_on for g in vistas] == [HOY - timedelta(days=d) for d in range(12)]

    async def test_mismo_dia_no_se_pierde_ninguna_entre_paginas(self, social_uow, user_uow):
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida(0) for _ in range(7)])
        use_case = _ver_mas(social_uow, user_uow, partidas)

        primera = await use_case.execute(str(yo.id.value), str(el.id.value))
        segunda = await use_case.execute(
            str(yo.id.value), str(el.id.value), cursor=primera.next_cursor
        )

        ids = [g.id for g in primera.games + segunda.games]
        assert sorted(ids) == sorted(p.game_id for p in partidas.partidas)
        assert segunda.next_cursor is None

    async def test_un_cursor_corrupto_da_la_primera_pagina(self, social_uow, user_uow):
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida(dias) for dias in range(3)])

        pagina = await _ver_mas(social_uow, user_uow, partidas).execute(
            str(yo.id.value), str(el.id.value), cursor="esto|no-vale"
        )

        assert [g.played_on for g in pagina.games] == [HOY - timedelta(days=d) for d in range(3)]

    async def test_con_justo_5_no_hay_mas(self, social_uow, user_uow):
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida(dias) for dias in range(5)])

        pagina = await _ver_mas(social_uow, user_uow, partidas).execute(
            str(yo.id.value), str(el.id.value)
        )

        assert len(pagina.games) == 5
        assert pagina.next_cursor is None

    async def test_un_cursor_con_fecha_o_id_raros_da_la_primera_pagina(self, social_uow, user_uow):
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida(dias) for dias in range(3)])
        use_case = _ver_mas(social_uow, user_uow, partidas)

        for cursor in ("0000-raro|" + str(uuid4()), "2026-10-19|no-es-un-id"):
            pagina = await use_case.execute(str(yo.id.value), str(el.id.value), cursor=cursor)
            assert len(pagina.games) == 3, cursor

    async def test_quien_no_es_amigo_no_lo_ve(self, social_uow, user_uow):
        """Caso 17."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        partidas = _PartidasFijas([_partida()])

        with pytest.raises(GamesTogetherNotVisibleError):
            await _ver_mas(social_uow, user_uow, partidas).execute(
                str(yo.id.value), str(el.id.value)
            )
        assert partidas.preguntas == []

    async def test_una_cuenta_que_no_esta_da_404(self, social_uow, user_uow):
        yo = await _usuario(user_uow)

        with pytest.raises(ProfileNotVisibleError):
            await _ver_mas(social_uow, user_uow, _PartidasFijas()).execute(
                str(yo.id.value), str(uuid4())
            )

    async def test_una_cuenta_dada_de_baja_da_404(self, social_uow, user_uow):
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        await _amigos(social_uow, yo, el)
        el.deactivate(deactivated_by_user_id=str(el.id.value))
        async with user_uow:
            await user_uow.users.save(el)

        with pytest.raises(ProfileNotVisibleError):
            await _ver_mas(social_uow, user_uow, _PartidasFijas()).execute(
                str(yo.id.value), str(el.id.value)
            )

    async def test_de_uno_mismo_no_hay_partidas_juntos(self, social_uow, user_uow):
        """Caso 6."""
        yo = await _usuario(user_uow)
        partidas = _PartidasFijas([_partida()])

        pagina = await _ver_mas(social_uow, user_uow, partidas).execute(
            str(yo.id.value), str(yo.id.value)
        )

        assert pagina.games == []
        assert pagina.next_cursor is None


class TestBloquearYQuitar:
    async def test_bloquear_a_un_amigo_rompe_la_amistad(self, social_uow, user_uow, stats):
        """Caso 15: deja de ser amigo y deja de ver el cara a cara."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow, handicap=8.4)
        await _amigos(social_uow, yo, el)
        partidas = _PartidasFijas([_partida()])

        await BlockUserUseCase(social_uow, user_uow).execute(str(yo.id.value), str(el.id.value))
        perfil = await _perfil(social_uow, user_uow, stats, partidas).execute(
            str(yo.id.value), str(el.id.value)
        )

        async with social_uow:
            assert not await social_uow.friendships.are_friends(yo.id, el.id)
        assert perfil.is_friend is False
        assert perfil.friendship.status == "BLOCKED"
        assert perfil.head_to_head is None
        assert perfil.games_together is None
        assert perfil.handicap is None

    async def test_quitar_a_un_amigo_vuelve_a_none_y_se_puede_pedir_otra_vez(
        self, social_uow, user_uow, stats
    ):
        """Caso 16."""
        yo = await _usuario(user_uow)
        el = await _usuario(user_uow)
        amistad = await _amigos(social_uow, yo, el)

        await RemoveFriendUseCase(social_uow).execute(str(amistad.id.value), str(yo.id.value))
        perfil = await _perfil(social_uow, user_uow, stats).execute(
            str(yo.id.value), str(el.id.value)
        )
        solicitud = await SendFriendRequestUseCase(social_uow, user_uow).execute(
            SendFriendRequestRequestDTO(requester_id=yo.id.value, addressee_id=el.id.value)
        )

        assert perfil.friendship.status == "NONE"
        assert perfil.head_to_head is None
        assert solicitud.status == "PENDING"

"""
Los partidos de una Ryder privada, según quién mira (tabla del 27 oct 2026; PR 2, R7).

La puerta, dentro de cada caso de uso, con lo que ya leyó:

  #   quien mira                          | anotación / detalle del partido | clasificación
  ----|-----------------------------------|----------------------------------|----------------
  1   organizador o admin                  | sí                               | todos los partidos
  2   aprobado                             | sí                               | todos
  5   juega en el partido (aunque se fuera)| el suyo                          | -
  6   de fuera, sin evento                 | 403                              | 403
  7   de fuera, con evento de un amigo     | el de su amigo                   | marcador y el de su amigo
  -   sin decir quién mira (uso interno)   | sí                               | todos
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import GetMatchDetailRequestDTO
from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    NoPuedeVerloError,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.application.use_cases.get_match_detail_use_case import (
    GetMatchDetailUseCase,
)
from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_get_leaderboard_use_case import (
    TestConLaLlaveSoloElPartidoDeSuAmigo,
    user_repo as _user_repo_leaderboard,  # noqa: F401
)
from tests.unit.modules.competition.application.use_cases.test_get_scoring_view_use_case import (
    _setup,
)

pytestmark = pytest.mark.asyncio

ORGANIZADOR = UserId(uuid4())


class _Eventos:
    def __init__(self, *amigos):
        self.amigos = frozenset(amigos)

    async def amigos_con_evento_en(self, user_id, competition_id):
        return self.amigos


def _privada(uow) -> MagicMock:
    """La competición del montaje, privada y con su organizador (un MagicMock diría «sí» a todo)."""
    (comp,) = uow._competitions._competitions.values()
    comp.visibility = Visibility.PRIVATE
    comp.is_creator = lambda quien: quien == ORGANIZADOR
    return comp


@pytest.fixture
def user_repo():
    repo = MagicMock()

    async def _por_ids(ids):
        return []

    repo.find_by_ids = _por_ids
    return repo


class TestLaAnotacionDeUnPartido:
    @pytest.fixture(autouse=True)
    def _usuarios(self):
        # Sin usuarios: sus nombres salen vacíos, que aquí no importa
        self.user_repo = AsyncMock(find_by_id=AsyncMock(return_value=None))

    async def _vista(self, quien, eventos, es_admin=False):
        uow = InMemoryUnitOfWork()
        match, amarillo, rojo, gc_repo = await _setup(uow, None)
        _privada(uow)
        uc = GetScoringViewUseCase(
            uow, self.user_repo, ScoringService(), gc_repo, eventos=_Eventos(*eventos)
        )
        jugador = {"amarillo": amarillo.user_id, "rojo": rojo.user_id}.get(quien, quien)
        amigos = [{"amarillo": amarillo.user_id}.get(a, a) for a in eventos]
        uc._eventos = _Eventos(*amigos)
        return await uc.execute(str(match.id), quien=jugador, es_admin=es_admin)

    async def test_6_de_fuera_sin_llave_no(self):
        with pytest.raises(NoPuedeVerloError):
            await self._vista(UserId(uuid4()), [])

    async def test_7_con_la_llave_el_de_su_amigo(self):
        assert await self._vista(UserId(uuid4()), ["amarillo"]) is not None

    async def test_7_la_llave_de_otro_no_abre_este(self):
        with pytest.raises(NoPuedeVerloError):
            await self._vista(UserId(uuid4()), [UserId(uuid4())])

    async def test_5_quien_juega_en_el_lo_ve(self):
        assert await self._vista("rojo", []) is not None

    async def test_1_el_organizador_y_un_admin(self):
        assert await self._vista(ORGANIZADOR, []) is not None
        assert await self._vista(UserId(uuid4()), [], es_admin=True) is not None


class TestElDetalleDeUnPartido:
    async def _detalle(self, quien, amigos=(), es_admin=False):
        uow = InMemoryUnitOfWork()
        match, amarillo, _, _ = await _setup(uow, None)
        _privada(uow)
        amigos = [amarillo.user_id if a == "amarillo" else a for a in amigos]
        uc = GetMatchDetailUseCase(uow, eventos=_Eventos(*amigos))
        return await uc.execute(
            GetMatchDetailRequestDTO(match_id=str(match.id.value)), quien=quien, es_admin=es_admin
        )

    async def test_6_de_fuera_sin_llave_no(self):
        with pytest.raises(NoPuedeVerloError):
            await self._detalle(UserId(uuid4()))

    async def test_7_con_la_llave_el_de_su_amigo(self):
        assert await self._detalle(UserId(uuid4()), ["amarillo"]) is not None

    async def test_1_el_organizador_y_un_admin(self):
        assert await self._detalle(ORGANIZADOR) is not None
        assert await self._detalle(UserId(uuid4()), es_admin=True) is not None

    async def test_sin_decir_quien_mira(self):
        assert await self._detalle(None) is not None


class TestLaClasificacion:
    async def _clasificacion(
        self, user_repo, quien, amigos=None, es_admin=False, visitante=False, publica=False
    ):
        uow = InMemoryUnitOfWork()
        competition_id, _, rival = await TestConLaLlaveSoloElPartidoDeSuAmigo()._dos_partidos(uow)
        comp = _privada(uow)
        if publica:
            comp.visibility = Visibility.PUBLIC
        uc = GetLeaderboardUseCase(
            uow,
            user_repo,
            ScoringService(),
            eventos=_Eventos(*([rival.user_id] if amigos == "rival" else [])),
        )
        if visitante:
            return await uc.execute(str(competition_id), quien=None, visitante=True)
        return await uc.execute(str(competition_id), quien=quien, es_admin=es_admin)

    async def test_l1_sin_sesion_una_publica_todos(self, user_repo):
        vista = await self._clasificacion(user_repo, None, visitante=True, publica=True)

        assert sorted(m.match_number for m in vista.matches) == [1, 2]

    async def test_sin_sesion_sin_id_de_jugador(self, user_repo):
        vista = await self._clasificacion(user_repo, None, visitante=True, publica=True)

        jugadores = [p for m in vista.matches for p in (*m.team_a_players, *m.team_b_players)]
        assert jugadores
        assert all(p.user_id is None for p in jugadores)

    async def test_l3_sin_sesion_una_privada_no_aunque_haya_llave(self, user_repo):
        with pytest.raises(NoPuedeVerloError):
            await self._clasificacion(user_repo, None, "rival", visitante=True)

    async def test_6_de_fuera_sin_llave_no(self, user_repo):
        with pytest.raises(NoPuedeVerloError):
            await self._clasificacion(user_repo, UserId(uuid4()))

    async def test_7_con_la_llave_el_marcador_y_el_de_su_amigo(self, user_repo):
        vista = await self._clasificacion(user_repo, UserId(uuid4()), "rival")

        assert [m.match_number for m in vista.matches] == [2]

    async def test_1_dentro_todos(self, user_repo):
        organizador = await self._clasificacion(user_repo, ORGANIZADOR)
        admin = await self._clasificacion(user_repo, UserId(uuid4()), es_admin=True)

        assert sorted(m.match_number for m in organizador.matches) == [1, 2]
        assert sorted(m.match_number for m in admin.matches) == [1, 2]

    async def test_sin_decir_quien_mira_todos(self, user_repo):
        vista = await self._clasificacion(user_repo, None)

        assert sorted(m.match_number for m in vista.matches) == [1, 2]


class TestQuienJuegaNoCuestaSuInscripcion:
    """/code-review: cada anotación devuelve la vista; quien juega ya está dentro."""

    async def _contando(self):
        uow = InMemoryUnitOfWork()
        match, _, rojo, gc_repo = await _setup(uow, None)
        _privada(uow)
        preguntas = []
        original = uow.enrollments.find_by_user_and_competition

        async def _apunta(*args):
            preguntas.append(args)
            return await original(*args)

        uow.enrollments.find_by_user_and_competition = _apunta
        return uow, match, rojo, gc_repo, preguntas

    async def test_la_anotacion_de_su_partido(self):
        uow, match, rojo, gc_repo, preguntas = await self._contando()
        uc = GetScoringViewUseCase(
            uow,
            AsyncMock(find_by_id=AsyncMock(return_value=None)),
            ScoringService(),
            gc_repo,
            eventos=_Eventos(),
        )

        await uc.execute(str(match.id), quien=rojo.user_id)

        assert preguntas == []

    async def test_el_detalle_de_su_partido(self):
        uow, match, rojo, _, preguntas = await self._contando()

        await GetMatchDetailUseCase(uow, eventos=_Eventos()).execute(
            GetMatchDetailRequestDTO(match_id=str(match.id.value)), quien=rojo.user_id
        )

        assert preguntas == []

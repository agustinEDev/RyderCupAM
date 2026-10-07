"""El hándicap de cada inscrito, con una sola consulta (RyderCupAM#251).

El draft ya lo hacía así y los sobres preguntaban jugador a jugador. La regla de
cuál cuenta es de la inscripción; aquí solo se trae el del perfil de quien no
tiene uno propio.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.services.handicaps_de_la_competicion import (
    HandicapsDeLaCompeticion,
    para_jugar_la_ryder,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId

COMPETICION = CompetitionId.generate()


def _inscripcion(personalizado: Decimal | None = None) -> Enrollment:
    return Enrollment.direct_enroll(
        id=EnrollmentId.generate(),
        competition_id=COMPETICION,
        user_id=UserId.generate(),
        custom_handicap=personalizado,
    )


def _usuario(user_id: UserId, handicap: float | None):
    usuario = MagicMock()
    usuario.id = user_id
    usuario.handicap = None if handicap is None else MagicMock(value=handicap)
    return usuario


def _repositorio(*usuarios):
    repo = MagicMock()
    repo.find_by_ids = AsyncMock(return_value=list(usuarios))
    return repo


@pytest.mark.asyncio
class TestHandicapsDeLaCompeticion:
    async def test_cada_inscrito_con_el_que_le_cuenta(self):
        propio = _inscripcion(Decimal("8.0"))
        del_perfil = _inscripcion()
        repo = _repositorio(_usuario(propio.user_id, 20.0), _usuario(del_perfil.user_id, 14.2))

        handicaps = await HandicapsDeLaCompeticion.de([propio, del_perfil], repo)

        assert handicaps == {propio.user_id: Decimal("8.0"), del_perfil.user_id: Decimal("14.2")}

    async def test_una_sola_consulta_y_solo_de_quien_no_tiene_propio(self):
        propio = _inscripcion(Decimal("8.0"))
        sin_propio_1 = _inscripcion()
        sin_propio_2 = _inscripcion()
        repo = _repositorio(
            _usuario(sin_propio_1.user_id, 1.0), _usuario(sin_propio_2.user_id, 2.0)
        )

        await HandicapsDeLaCompeticion.de([propio, sin_propio_1, sin_propio_2], repo)

        repo.find_by_ids.assert_awaited_once()
        (pedidos,) = repo.find_by_ids.await_args.args
        assert set(pedidos) == {sin_propio_1.user_id, sin_propio_2.user_id}

    async def test_si_todos_tienen_propio_no_consulta(self):
        repo = _repositorio()

        await HandicapsDeLaCompeticion.de([_inscripcion(Decimal("8.0"))], repo)

        repo.find_by_ids.assert_not_awaited()

    async def test_quien_no_esta_o_no_tiene_handicap_se_queda_sin_el(self):
        sin_handicap = _inscripcion()
        desaparecido = _inscripcion()
        repo = _repositorio(_usuario(sin_handicap.user_id, None))

        handicaps = await HandicapsDeLaCompeticion.de([sin_handicap, desaparecido], repo)

        assert handicaps == {sin_handicap.user_id: None, desaparecido.user_id: None}

    async def test_sin_inscritos_no_hay_nada_que_buscar(self):
        repo = _repositorio()

        assert await HandicapsDeLaCompeticion.de([], repo) == {}
        repo.find_by_ids.assert_not_awaited()


class TestParaJugarLaRyder:
    """La Ryder juega con cero a quien no tiene hándicap: una regla, no tres copias."""

    def test_sin_handicap_juega_con_cero(self):
        assert para_jugar_la_ryder(None) == Decimal("0")

    @pytest.mark.parametrize("handicap", [Decimal("14.2"), Decimal("0.0"), Decimal("-2.0")])
    def test_con_handicap_juega_con_el_suyo(self, handicap):
        assert para_jugar_la_ryder(handicap) == handicap

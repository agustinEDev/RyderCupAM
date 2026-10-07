"""El hándicap con el que los sobres ordenan a los jugadores de un equipo.

Preguntaba jugador a jugador dentro de la lectura de la pantalla, con la
competición bloqueada. Ahora trae los perfiles de una vez, como el draft.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
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


def _usuario(user_id: UserId, handicap: float):
    usuario = MagicMock()
    usuario.id = user_id
    usuario.handicap = MagicMock(value=handicap)
    return usuario


@pytest.mark.asyncio
class TestHandicapsDeLosSobres:
    async def test_una_sola_consulta_y_cero_para_quien_no_tiene(self):
        propio, del_perfil, sin_nada = _inscripcion(Decimal("8.0")), _inscripcion(), _inscripcion()
        uow = MagicMock()
        uow.enrollments.find_by_competition_and_status = AsyncMock(
            return_value=[propio, del_perfil, sin_nada]
        )
        repo = MagicMock()
        repo.find_by_ids = AsyncMock(return_value=[_usuario(del_perfil.user_id, 14.2)])
        repo.find_by_id = AsyncMock()
        competicion = MagicMock(id=COMPETICION)

        handicaps = await EnvelopeDesk(uow, repo).handicaps_de(
            competicion, [sin_nada.user_id, propio.user_id, del_perfil.user_id]
        )

        assert handicaps == [
            (sin_nada.user_id, Decimal("0")),
            (propio.user_id, Decimal("8.0")),
            (del_perfil.user_id, Decimal("14.2")),
        ]
        repo.find_by_ids.assert_awaited_once()
        repo.find_by_id.assert_not_awaited()

    async def test_quien_no_esta_inscrito_no_entra(self):
        inscrito = _inscripcion(Decimal("8.0"))
        uow = MagicMock()
        uow.enrollments.find_by_competition_and_status = AsyncMock(return_value=[inscrito])
        repo = MagicMock()
        repo.find_by_ids = AsyncMock(return_value=[])

        handicaps = await EnvelopeDesk(uow, repo).handicaps_de(
            MagicMock(id=COMPETICION), [UserId.generate(), inscrito.user_id]
        )

        assert handicaps == [(inscrito.user_id, Decimal("8.0"))]

"""
La vista de una competición, que antes armaba cada ruta por su cuenta (fase 5, PR 3a).

Tras una transición, un alta o una edición, la ruta volvía a leer la competición con
el repositorio y la pasaba por el mapper. La ficha además buscaba la invitación
pendiente de quien mira y hasta dónde ve los inscritos. Ahora lo hace este caso de
uso; la respuesta es la misma (V1-V6).
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.application.use_cases.vista_de_competicion_use_case import (
    VistaDeCompeticionUseCase,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.invitacion_pendiente import (
    InvitacionPendiente,
)
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio

YO = UserId(uuid4())
CREADOR = UserId(uuid4())
PENDIENTE = InvitacionPendiente(InvitationId.generate(), datetime.now() + timedelta(days=3))


def _competicion(estado=CompetitionStatus.ACTIVE):
    """Lo que leen la ficha y la regla de los inscritos, de una pública sin publicar."""
    return SimpleNamespace(
        id=CompetitionId(uuid4()),
        status=estado,
        visibility=Visibility.PUBLIC,
        stroke_play=None,
        is_creator=lambda quien: quien == CREADOR,
    )


def _uows(competicion, pendiente=None):
    """Las dos unidades de trabajo, la de competiciones con lo que la ficha pregunta."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.competitions.find_by_id = AsyncMock(return_value=competicion)
    uow.invitations.pendiente_de = AsyncMock(return_value=pendiente)
    uow.invitations.competiciones_con_invitacion_pendiente = AsyncMock(return_value=set())
    uow.enrollments.find_by_competition_and_status = AsyncMock(return_value=[])
    uow.team_assignments.find_by_competition = AsyncMock(return_value=None)
    user_uow = MagicMock()
    user_uow.__aenter__ = AsyncMock(return_value=user_uow)
    user_uow.__aexit__ = AsyncMock(return_value=False)
    return uow, user_uow


@pytest.fixture
def mapper(monkeypatch):
    """El mapper de siempre, sustituido: apunta con qué se le llama y devuelve un DTO."""
    llamadas = []

    async def _to_response_dto(competition, current_user_id, uow, user_uow=None, is_admin=False):
        llamadas.append((competition, current_user_id, uow, user_uow, is_admin))
        return SimpleNamespace(
            id=competition.id,
            user_enrollment_status=None,
            my_pending_invitation=None,
            enrolled_visibility=None,
        )

    monkeypatch.setattr(CompetitionDTOMapper, "to_response_dto", staticmethod(_to_response_dto))
    return llamadas


class TestDe:
    async def test_v1_de_una_competicion_da_el_dto_del_mapper(self, mapper):
        """Given una competición, When se pide su vista, Then es la del mapper con quien mira."""
        comp = _competicion()
        uow, user_uow = _uows(comp)

        dto = await VistaDeCompeticionUseCase(uow, user_uow).de(comp.id, YO, es_admin=True)

        assert dto.id == comp.id
        assert mapper == [(comp, YO, uow, user_uow, True)]
        uow.competitions.find_by_id.assert_awaited_once_with(comp.id)

    async def test_v2_de_una_que_no_existe_lanza_no_encontrada(self, mapper):
        """Given ninguna competición con ese id, When se pide su vista, Then CompetitionNotFoundError."""
        uow, user_uow = _uows(None)
        cid = CompetitionId(uuid4())

        with pytest.raises(CompetitionNotFoundError) as error:
            await VistaDeCompeticionUseCase(uow, user_uow).de(cid, YO)

        assert str(error.value) == f"No existe competición con ID {cid.value}"
        assert mapper == []


class TestFicha:
    async def test_v3_con_invitacion_que_se_puede_aceptar_la_ofrece(self, mapper):
        """Given una invitación pendiente en una ACTIVE, When mira la ficha, Then se le ofrece."""
        comp = _competicion()
        uow, user_uow = _uows(comp, pendiente=PENDIENTE)

        dto = await VistaDeCompeticionUseCase(uow, user_uow).ficha(comp.id, YO, email="yo@t.com")

        assert dto.my_pending_invitation.id == PENDIENTE.id.value
        assert dto.my_pending_invitation.expires_at == PENDIENTE.expires_at
        assert uow.invitations.pendiente_de.await_args.args[:3] == (YO, "yo@t.com", comp.id)

    async def test_v4_sin_invitacion_no_ofrece_nada(self, mapper):
        """Given sin invitación pendiente, When mira la ficha, Then no se le ofrece ninguna."""
        comp = _competicion()
        uow, user_uow = _uows(comp, pendiente=None)

        dto = await VistaDeCompeticionUseCase(uow, user_uow).ficha(comp.id, YO)

        assert dto.my_pending_invitation is None

    async def test_v4_ya_inscrito_no_se_le_ofrece_aceptar(self, mapper, monkeypatch):
        """Given una invitación pero ya inscrito, When mira la ficha, Then no se le ofrece."""
        comp = _competicion()
        uow, user_uow = _uows(comp, pendiente=PENDIENTE)
        original = CompetitionDTOMapper.to_response_dto

        async def _inscrito(*args, **kwargs):
            dto = await original(*args, **kwargs)
            dto.user_enrollment_status = "PENDING"
            return dto

        monkeypatch.setattr(CompetitionDTOMapper, "to_response_dto", staticmethod(_inscrito))

        dto = await VistaDeCompeticionUseCase(uow, user_uow).ficha(comp.id, YO)

        assert dto.my_pending_invitation is None

    @pytest.mark.parametrize(
        ("quien", "es_admin", "esperado"),
        [(CREADOR, False, "ALL"), (YO, True, "ALL"), (YO, False, "FRIENDS")],
        ids=["creador", "admin", "ajeno"],
    )
    async def test_v5_lo_que_ve_de_los_inscritos(self, mapper, quien, es_admin, esperado):
        """Given quien mira una pública sin publicar, When abre la ficha, Then ve lo de la regla."""
        comp = _competicion()
        uow, user_uow = _uows(comp)

        dto = await VistaDeCompeticionUseCase(uow, user_uow).ficha(
            comp.id, quien, es_admin=es_admin
        )

        assert dto.enrolled_visibility == esperado

    async def test_v5_ajeno_con_invitacion_no_vuelve_a_preguntar_por_ella(self, mapper):
        """Given la invitación ya leída, When se calcula el alcance, Then no se pregunta otra vez."""
        comp = _competicion(estado=CompetitionStatus.CLOSED)
        uow, user_uow = _uows(comp, pendiente=PENDIENTE)

        await VistaDeCompeticionUseCase(uow, user_uow).ficha(comp.id, YO)

        uow.invitations.competiciones_con_invitacion_pendiente.assert_not_called()

    async def test_v6_ficha_de_una_que_no_existe_lanza_no_encontrada(self, mapper):
        """Given ninguna competición con ese id, When se pide la ficha, Then CompetitionNotFoundError."""
        uow, user_uow = _uows(None)

        with pytest.raises(CompetitionNotFoundError):
            await VistaDeCompeticionUseCase(uow, user_uow).ficha(CompetitionId(uuid4()), YO)

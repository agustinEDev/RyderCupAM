"""
La invitación que la ficha ofrece aceptar (tabla del 27 oct 2026, filas 13-16; /code-review).

  quien mira                                   | la ficha
  ---------------------------------------------|---------------------------------
  organiza                                     | ninguna (ni se pregunta)
  invitado, sin inscripción, competición ACTIVE| la ofrece
  invitado con inscripción (cualquier estado)  | no: aceptar daría 400
  invitado, competición no ACTIVE              | no: la política no deja aceptar
  sin invitación                               | ninguna
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.services.invitacion_de_la_ficha import (
    invitacion_pendiente,
    se_le_ofrece_aceptar,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.invitacion_pendiente import (
    InvitacionPendiente,
)
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.user.domain.value_objects.user_id import UserId

YO = UserId(uuid4())
CREADOR = UserId(uuid4())
AHORA = datetime(2026, 10, 27, 12, 0)
PENDIENTE = InvitacionPendiente(InvitationId.generate(), AHORA + timedelta(days=3))


def _competicion(estado=CompetitionStatus.ACTIVE):
    return SimpleNamespace(
        id=CompetitionId(uuid4()), status=estado, is_creator=lambda quien: quien == CREADOR
    )


def _uow(pendiente=PENDIENTE):
    return SimpleNamespace(
        invitations=SimpleNamespace(pendiente_de=AsyncMock(return_value=pendiente))
    )


async def test_la_de_quien_mira_por_su_usuario_o_su_correo():
    uow, comp = _uow(), _competicion()

    assert await invitacion_pendiente(uow, comp, YO, "yo@t.com", AHORA) == PENDIENTE
    uow.invitations.pendiente_de.assert_awaited_once_with(YO, "yo@t.com", comp.id, AHORA)


async def test_quien_organiza_no_tiene_ni_se_pregunta():
    uow = _uow()

    assert await invitacion_pendiente(uow, _competicion(), CREADOR, None, AHORA) is None
    uow.invitations.pendiente_de.assert_not_called()


def test_sin_inscripcion_y_activa_se_ofrece():
    assert se_le_ofrece_aceptar(_competicion(), PENDIENTE, inscrito=False) is True


def test_con_inscripcion_no_se_ofrece():
    assert se_le_ofrece_aceptar(_competicion(), PENDIENTE, inscrito=True) is False


def test_sin_invitacion_no_se_ofrece():
    assert se_le_ofrece_aceptar(_competicion(), None, inscrito=False) is False


@pytest.mark.parametrize(
    "estado",
    [
        CompetitionStatus.DRAFT,
        CompetitionStatus.CLOSED,
        CompetitionStatus.IN_PROGRESS,
        CompetitionStatus.COMPLETED,
        CompetitionStatus.CANCELLED,
    ],
)
def test_si_la_politica_no_deja_aceptar_no_se_ofrece(estado):
    assert se_le_ofrece_aceptar(_competicion(estado), PENDIENTE, inscrito=False) is False

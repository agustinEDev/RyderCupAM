"""
Los partidos de la agenda de una privada, según quién mira (tabla del 27 oct 2026).

  #   quien mira una privada                    | partidos             | equipos y descansos
  ----|----------------------------------------|----------------------|--------------------
  1   organizador o admin                        | todos                | sí
  2   aprobado                                   | todos                | sí
  6   de fuera, sin evento                       | ninguno              | no
  7   de fuera, con evento de un amigo           | solo los de su amigo | no
  -   en una pública, o sin decir quién mira     | todos                | sí
"""

from uuid import uuid4

from src.modules.competition.application.dto.round_match_dto import GetScheduleRequestDTO
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_quien_descansa import (
    _dos_contra_tres,
)


class _Eventos:
    def __init__(self, *amigos):
        self.amigos = frozenset(amigos)

    async def amigos_con_evento_en(self, user_id, competition_id):
        return self.amigos


async def _privada(visibilidad=Visibility.PRIVATE):
    uow, comp_id, a, b = await _dos_contra_tres()
    async with uow:
        comp = await uow.competitions.find_by_id(comp_id)
        comp._visibility = visibilidad
        await uow.competitions.update(comp)
    return uow, comp, a, b


async def _agenda(uow, comp, eventos=None, **quien):
    return await GetScheduleUseCase(uow, eventos=eventos or _Eventos()).execute(
        GetScheduleRequestDTO(competition_id=str(comp.id.value)), **quien
    )


def _partidos(agenda) -> list[int]:
    return [m.match_number for d in agenda.days for r in d.rounds for m in r.matches]


def _descansan(agenda) -> list:
    return [u for d in agenda.days for r in d.rounds for u in r.resting_player_ids]


async def test_6_de_fuera_sin_evento_ni_partidos_ni_equipos():
    uow, comp, _, _ = await _privada()

    agenda = await _agenda(uow, comp, viewer_id=UserId(uuid4()))

    assert _partidos(agenda) == []
    assert agenda.total_matches == 0
    assert agenda.team_assignment is None
    assert _descansan(agenda) == []


async def test_7_con_la_llave_solo_el_partido_de_su_amigo():
    uow, comp, _, b = await _privada()

    agenda = await _agenda(uow, comp, _Eventos(b[1]), viewer_id=UserId(uuid4()))

    assert _partidos(agenda) == [2]
    assert agenda.total_matches == 1
    assert agenda.team_assignment is None
    assert _descansan(agenda) == []


async def test_2_el_aprobado_lo_ve_todo():
    uow, comp, a, b = await _privada()

    agenda = await _agenda(uow, comp, viewer_id=a[0])

    assert _partidos(agenda) == [1, 2]
    assert agenda.team_assignment is not None
    assert _descansan(agenda) == [b[2].value]


async def test_1_el_organizador_lo_ve_todo():
    uow, comp, _, _ = await _privada()

    agenda = await _agenda(uow, comp, viewer_id=comp.creator_id)

    assert _partidos(agenda) == [1, 2]
    assert agenda.team_assignment is not None


async def test_1_un_admin_lo_ve_todo():
    uow, comp, _, _ = await _privada()

    agenda = await _agenda(uow, comp, viewer_id=UserId(uuid4()), viewer_is_admin=True)

    assert _partidos(agenda) == [1, 2]


async def test_en_una_publica_cualquiera_lo_ve_todo():
    uow, comp, _, _ = await _privada(Visibility.PUBLIC)

    agenda = await _agenda(uow, comp, viewer_id=UserId(uuid4()))

    assert _partidos(agenda) == [1, 2]
    assert agenda.team_assignment is not None


async def test_sin_decir_quien_mira_va_entera():
    """Los usos internos (avisos, próximos partidos) leen la agenda entera."""
    uow, comp, _, _ = await _privada()

    agenda = await _agenda(uow, comp)

    assert _partidos(agenda) == [1, 2]
    assert agenda.team_assignment is not None

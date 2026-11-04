"""
Se autoriza ANTES de bloquear el partido (BE #309).

`PUT /matches/{id}/status` cogía el bloqueo de la fila y DESPUÉS miraba si quien
llama es el creador o un admin: cualquiera con sesión que supiera el id de un
partido podía retener ese bloqueo hasta que la transacción se deshacía, y
cruzarse con la actualización legítima de los jugadores.

El bloqueo no se quita: START y la apertura automática por hora (BE #305) hacen
lo mismo y, si se cruzan, los dos pre-crean los 18 hoyos (PR #307). Se lee sin
bloqueo, se autoriza, y entonces se bloquea y se RELEE: el estado se decide sobre
lo releído, o la carrera vuelve por el hueco entre las dos lecturas.

  #  caso                                          | bloqueo | resultado
  ---|------------------------------------------|---------|------------------------------
  1  no es el creador ni admin                   | NO      | NotCompetitionCreatorError
  2  la competición no está en curso             | NO      | CompetitionNotInProgressError
  3  el partido no existe                        | NO      | MatchNotFoundError
  4  el creador                                  | SÍ, tras autorizar | arranca
  5  un admin que no es el creador               | SÍ      | arranca
  6  entre leer y bloquear, otro lo abrió         | SÍ      | se decide con lo releído:
                                                             START ya no vale
  7  entre leer y bloquear, se borró              | SÍ      | MatchNotFoundError
  8  la ronda                                     | SÍ      | se relee FRESCA tras el bloqueo
                                                             y es la que se guarda: la leída
                                                             para autorizar pudo cambiar
                                                             (code-review)
"""

from copy import deepcopy
from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    UpdateMatchStatusRequestDTO,
)
from src.modules.competition.application.exceptions import (
    MatchNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    CompetitionNotInProgressError,
    InvalidActionError,
    UpdateMatchStatusUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

CREADOR = UserId(uuid4())


def _jugador():
    return MatchPlayer.create(
        user_id=UserId(uuid4()),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
        tee_gender=Gender.MALE,
    )


async def _escena(en_curso: bool = True):
    """Una competición (en curso o no) con una ronda y un partido programado."""
    uow = InMemoryUnitOfWork()
    competicion = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=CREADOR,
        name=CompetitionName("Bloqueo"),
        dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        max_players=24,
        team_assignment=TeamAssignment.MANUAL,
        team_1_name="A",
        team_2_name="B",
    )
    competicion.activate()
    competicion.close_enrollments()
    if en_curso:
        competicion.start()
    ronda = Round.create(
        competition_id=competicion.id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=date(2026, 6, 1),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    ronda.mark_teams_assigned()
    ronda.mark_matches_generated()
    partido = Match.create(
        round_id=ronda.id, match_number=1, team_a_players=[_jugador()], team_b_players=[_jugador()]
    )
    async with uow:
        await uow.competitions.add(competicion)
        await uow.rounds.add(ronda)
        await uow.matches.add(partido)
    return uow, partido


def _espia_el_bloqueo(uow, registro, releido="igual"):
    """Apunta cuándo se bloquea; `releido` simula lo que otro cambió entre medias."""
    original = uow.matches.find_by_id_for_update
    original_competicion = uow.competitions.find_by_id

    async def competicion(competition_id):
        registro.append("autoriza")
        return await original_competicion(competition_id)

    async def bloqueo(match_id):
        registro.append("bloqueo")
        partido = await original(match_id)
        if releido == "borrado":
            return None
        if releido == "ya abierto":
            copia = deepcopy(partido)
            copia.start()
            return copia
        return partido

    uow.competitions.find_by_id = competicion
    uow.matches.find_by_id_for_update = bloqueo


def _start(partido_id) -> UpdateMatchStatusRequestDTO:
    return UpdateMatchStatusRequestDTO(match_id=str(partido_id), action="START")


async def test_1_quien_no_es_el_creador_no_bloquea_nada():
    uow, partido = await _escena()
    registro = []
    _espia_el_bloqueo(uow, registro)

    with pytest.raises(NotCompetitionCreatorError):
        await UpdateMatchStatusUseCase(uow).execute(_start(partido.id), UserId(uuid4()))

    assert "bloqueo" not in registro


async def test_2_con_la_competicion_sin_empezar_no_bloquea_nada():
    uow, partido = await _escena(en_curso=False)
    registro = []
    _espia_el_bloqueo(uow, registro)

    with pytest.raises(CompetitionNotInProgressError):
        await UpdateMatchStatusUseCase(uow).execute(_start(partido.id), CREADOR)

    assert "bloqueo" not in registro


async def test_3_un_partido_que_no_existe_no_bloquea_nada():
    uow, _ = await _escena()
    registro = []
    _espia_el_bloqueo(uow, registro)

    with pytest.raises(MatchNotFoundError):
        await UpdateMatchStatusUseCase(uow).execute(_start(MatchId(uuid4())), CREADOR)

    assert "bloqueo" not in registro


async def test_4_el_creador_bloquea_una_vez_y_despues_de_autorizar():
    uow, partido = await _escena()
    registro = []
    _espia_el_bloqueo(uow, registro)

    respuesta = await UpdateMatchStatusUseCase(uow).execute(_start(partido.id), CREADOR)

    assert respuesta.new_status == "IN_PROGRESS"
    assert registro.count("bloqueo") == 1
    assert registro.index("autoriza") < registro.index("bloqueo")


async def test_5_un_admin_que_no_es_el_creador_tambien():
    uow, partido = await _escena()
    registro = []
    _espia_el_bloqueo(uow, registro)

    respuesta = await UpdateMatchStatusUseCase(uow).execute(
        _start(partido.id), UserId(uuid4()), is_admin=True
    )

    assert respuesta.new_status == "IN_PROGRESS"
    assert registro.count("bloqueo") == 1


async def test_6_si_otro_lo_abrio_entre_medias_se_decide_con_lo_releido():
    uow, partido = await _escena()
    _espia_el_bloqueo(uow, [], releido="ya abierto")

    with pytest.raises(InvalidActionError):
        await UpdateMatchStatusUseCase(uow).execute(_start(partido.id), CREADOR)


async def test_7_si_se_borro_entre_medias_no_existe():
    uow, partido = await _escena()
    _espia_el_bloqueo(uow, [], releido="borrado")

    with pytest.raises(MatchNotFoundError):
        await UpdateMatchStatusUseCase(uow).execute(_start(partido.id), CREADOR)


async def test_8_la_ronda_se_relee_fresca_tras_el_bloqueo_y_es_la_que_se_usa():
    uow, partido = await _escena()
    registro = []
    _espia_el_bloqueo(uow, registro)
    original = uow.rounds.find_by_id_fresh
    frescas = []

    async def fresca(round_id):
        registro.append("ronda fresca")
        ronda = deepcopy(await original(round_id))
        frescas.append(ronda)
        return ronda

    uow.rounds.find_by_id_fresh = fresca
    guardadas = []
    actualiza = uow.rounds.update

    async def espia_update(ronda):
        guardadas.append(ronda)
        return await actualiza(ronda)

    uow.rounds.update = espia_update

    await UpdateMatchStatusUseCase(uow).execute(_start(partido.id), CREADOR)

    assert registro.index("bloqueo") < registro.index("ronda fresca")
    # Si el START cambia la ronda, se guarda la releída, no la de autorizar
    assert all(r is frescas[0] for r in guardadas)

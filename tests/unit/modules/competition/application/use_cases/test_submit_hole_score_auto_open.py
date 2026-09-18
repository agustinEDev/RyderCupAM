"""
Tests de la apertura automatica de la anotacion (BE #305).

Un partido solo se podia anotar despues de que su creador pulsara START, con
cobertura. Ahora se abre solo a una hora fija segun la sesion de su ronda —06:00,
12:00 o 18:00 en la zona de la competicion— cuando llega el primer golpe.

LA TABLA (los numeros son los de la issue):

    #   situacion                                   | debe
    ----|-------------------------------------------|--------------------------------
    1   programado, ya es la hora                   | se abre y se guarda el golpe
    2   programado, aun no es la hora               | ScoringNotOpenYetError, con la hora
    3   tarde a las 12:00 / noche a las 18:00       | se abre
    4   competicion no en curso                     | rechazo definitivo, como hoy
    5   dos primeros golpes a la vez                | una sola apertura, los dos golpes
    6   ya en curso por START                       | camino de siempre
    7   terminado / concedido / walkover            | no se reabre nunca
    9   ronda sin fecha o sin sesion                | no abre sola; solo START
    11  ronda de mañana, golpe el dia antes         | rechazo: no es su dia
    12  golpe rezagado de hace dias                 | se abre igual (sin tope)
    13  al abrirse                                  | quedan los 18 hoyos por jugador
"""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import (
    MatchNotScoringError,
    NotMatchPlayerError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.services.match_opener import MatchOpener
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

# La ronda es del 20 de septiembre de 2026; la sesion de mañana abre a las 06:00
# de Madrid, que son las 04:00 UTC
DIA = date(2026, 9, 20)
ANTES = datetime(2026, 9, 20, 3, 59, tzinfo=UTC)
JUSTO = datetime(2026, 9, 20, 4, 0, tzinfo=UTC)
DESPUES = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)


def _campo(timezone: str | None) -> GolfCourse:
    """Un campo de verdad: la vista de anotacion le pide tarjeta, tees y nombre."""
    return GolfCourse.create(
        name="Campo de prueba",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId(uuid4()),
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            )
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
        timezone=timezone,
    )


class _ReposDeCampos:
    """Devuelve siempre el mismo campo, con la zona que le pongan."""

    def __init__(self):
        self.campo = _campo("Europe/Madrid")

    async def find_by_id(self, _golf_course_id):
        return self.campo


@pytest.fixture
def campos():
    return _ReposDeCampos()


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def scoring_service():
    return ScoringService()


@pytest.fixture
def user_repo():
    def _usuario(uid):
        user = MagicMock()
        user.first_name = "Player"
        user.last_name = str(uid)[:8]
        user.display_name = f"Player {str(uid)[:8]}"
        user.display_name_or_legal = MagicMock(return_value=f"Player {str(uid)[:8]}")
        return user

    repo = AsyncMock()
    repo.find_by_id = AsyncMock(side_effect=_usuario)
    return repo


def _jugador() -> MatchPlayer:
    return MatchPlayer.create(
        user_id=UserId(uuid4()),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
    )


async def _monta(
    uow: InMemoryUnitOfWork,
    *,
    estado_partido: MatchStatus = MatchStatus.SCHEDULED,
    round_date: date | None = DIA,
    session_type: SessionType | None = SessionType.MORNING,
    competicion_en_curso: bool = True,
):
    """Deja en el UoW una competicion, su ronda y un partido de dos jugadores."""
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=UserId(uuid4()),
        name=CompetitionName("Torneo de prueba"),
        dates=DateRange(start_date=DIA, end_date=DIA),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_assignment=TeamAssignment.MANUAL,
        team_1_name="Equipo A",
        team_2_name="Equipo B",
    )
    competition.activate()
    competition.close_enrollments()
    if competicion_en_curso:
        competition.start()

    round_entity = Round.create(
        competition_id=competition.id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=round_date or DIA,
        session_type=session_type or SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    # Como en la vida real: cuando hay partidos, la ronda ya paso por asignar
    # equipos y generarlos, asi que esta programada
    round_entity.mark_teams_assigned()
    round_entity.mark_matches_generated()

    # Rondas viejas: la fecha o la sesion pueden faltar (caso 9)
    if round_date is None:
        round_entity._round_date = None
    if session_type is None:
        round_entity._session_type = None

    a, b = _jugador(), _jugador()
    match = Match.create(
        round_id=round_entity.id,
        match_number=1,
        team_a_players=[a],
        team_b_players=[b],
    )
    if estado_partido != MatchStatus.SCHEDULED:
        match.start()
    if estado_partido == MatchStatus.COMPLETED:
        match.complete(result={"winner": "A", "score": "2&1"})

    async with uow:
        await uow.competitions.add(competition)
        await uow.rounds.add(round_entity)
        await uow.matches.add(match)

    return competition, round_entity, match, a, b


def _body(marcado: MatchPlayer, own: int = 5, marked: int = 4) -> SubmitHoleScoreBodyDTO:
    return SubmitHoleScoreBodyDTO(
        own_score=own, marked_player_id=str(marcado.user_id), marked_score=marked
    )


def _caso_de_uso(uow, user_repo, scoring_service, ahora=None, campos=None):
    return SubmitHoleScoreUseCase(
        uow, user_repo, scoring_service, campos, now=lambda: ahora or DESPUES
    )


class TestSeAbreSola:
    @pytest.mark.asyncio
    async def test_1_ya_es_la_hora_se_abre_y_guarda_el_golpe(self, uow, user_repo, scoring_service, campos):
        _c, _r, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)

        async with uow:
            guardado = await uow.matches.find_by_id(match.id)
            assert guardado.status == MatchStatus.IN_PROGRESS
            hoyo = await uow.hole_scores.find_one(match.id, 1, a.user_id)
            assert hoyo is not None, "el golpe tiene que quedar guardado, no caer en la nada"
            assert hoyo.own_score == 5

    @pytest.mark.asyncio
    async def test_13_al_abrirse_quedan_los_18_hoyos_por_jugador(
        self, uow, user_repo, scoring_service, campos
    ):
        """Sin esto el POST devuelve 200 y no guarda nada: perdida silenciosa."""
        _c, _r, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)

        async with uow:
            hoyos = await uow.hole_scores.find_by_match(match.id)
        assert len(hoyos) == 36, "18 hoyos por cada uno de los dos jugadores"

    @pytest.mark.asyncio
    async def test_la_ronda_tambien_arranca(self, uow, user_repo, scoring_service, campos):
        _c, round_entity, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)

        async with uow:
            guardada = await uow.rounds.find_by_id(round_entity.id)
        assert guardada.status == RoundStatus.IN_PROGRESS

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("session_type", "ahora"),
        [
            (SessionType.AFTERNOON, datetime(2026, 9, 20, 10, 0, tzinfo=UTC)),
            (SessionType.EVENING, datetime(2026, 9, 20, 16, 0, tzinfo=UTC)),
        ],
    )
    async def test_3_tarde_y_noche_tienen_su_hora(
        self, uow, user_repo, scoring_service, campos, session_type, ahora
    ):
        _c, _r, match, a, b = await _monta(uow, session_type=session_type)

        uc = _caso_de_uso(uow, user_repo, scoring_service, ahora, campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)

        async with uow:
            assert (await uow.matches.find_by_id(match.id)).status == MatchStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_12_un_golpe_de_hace_dias_abre_igual(self, uow, user_repo, scoring_service, campos):
        """Sin tope por arriba: un golpe atascado en un movil sin cobertura entra."""
        _c, _r, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, DESPUES + timedelta(days=5), campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)

        async with uow:
            assert (await uow.matches.find_by_id(match.id)).status == MatchStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_8_la_hora_es_la_del_campo(self, uow, user_repo, scoring_service, campos):
        """En Canarias las 06:00 locales son las 05:00 UTC: a las 04:00 aun no."""
        _c, _r, match, a, b = await _monta(uow)
        campos.campo = _campo("Atlantic/Canary")

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        with pytest.raises(ScoringNotOpenYetError):
            await uc.execute(str(match.id), 1, _body(b), a.user_id)

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO + timedelta(hours=1), campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)
        async with uow:
            assert (await uow.matches.find_by_id(match.id)).status == MatchStatus.IN_PROGRESS


class TestNoSeAbre:
    @pytest.mark.asyncio
    async def test_2_antes_de_la_hora_se_rechaza_y_no_abre_nada(
        self, uow, user_repo, scoring_service, campos
    ):
        _c, _r, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, ANTES, campos)
        with pytest.raises(ScoringNotOpenYetError) as e:
            await uc.execute(str(match.id), 1, _body(b), a.user_id)

        assert e.value.opens_at == datetime(2026, 9, 20, 4, 0, tzinfo=UTC).astimezone(
            e.value.opens_at.tzinfo
        ), "el error dice a que hora abre, para que el movil pueda reintentar"
        async with uow:
            assert (await uow.matches.find_by_id(match.id)).status == MatchStatus.SCHEDULED
            assert await uow.hole_scores.find_by_match(match.id) == []

    @pytest.mark.asyncio
    async def test_11_el_dia_anterior_tampoco(self, uow, user_repo, scoring_service, campos):
        _c, _r, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, datetime(2026, 9, 19, 9, 0, tzinfo=UTC), campos)
        with pytest.raises(ScoringNotOpenYetError):
            await uc.execute(str(match.id), 1, _body(b), a.user_id)

    @pytest.mark.asyncio
    async def test_4_competicion_no_en_curso_es_rechazo_definitivo(
        self, uow, user_repo, scoring_service, campos
    ):
        """No es «aun no»: reintentarlo no lo va a salvar hasta que alguien la arranque."""
        _c, _r, match, a, b = await _monta(uow, competicion_en_curso=False)

        uc = _caso_de_uso(uow, user_repo, scoring_service, DESPUES, campos)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), 1, _body(b), a.user_id)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("round_date", "session_type"),
        [(None, SessionType.MORNING), (DIA, None)],
    )
    async def test_9_ronda_sin_fecha_o_sin_sesion_solo_abre_con_start(
        self, uow, user_repo, scoring_service, campos, round_date, session_type
    ):
        _c, _r, match, a, b = await _monta(uow, round_date=round_date, session_type=session_type)

        uc = _caso_de_uso(uow, user_repo, scoring_service, DESPUES, campos)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), 1, _body(b), a.user_id)

    @pytest.mark.asyncio
    async def test_7_un_partido_terminado_no_se_reabre(self, uow, user_repo, scoring_service, campos):
        _c, _r, match, a, b = await _monta(uow, estado_partido=MatchStatus.COMPLETED)

        uc = _caso_de_uso(uow, user_repo, scoring_service, DESPUES, campos)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), 1, _body(b), a.user_id)


class TestYaAbierto:
    @pytest.mark.asyncio
    async def test_6_un_partido_ya_en_curso_sigue_el_camino_de_siempre(
        self, uow, user_repo, scoring_service, campos
    ):
        """START manual se queda: abre antes de la hora y se anota igual."""
        _c, _r, match, a, b = await _monta(uow, estado_partido=MatchStatus.IN_PROGRESS)
        async with uow:
            from src.modules.competition.domain.entities.hole_score import HoleScore

            await uow.hole_scores.add_many(
                [
                    HoleScore.create(
                        match_id=match.id,
                        hole_number=h,
                        player_user_id=j.user_id,
                        team=equipo,
                        strokes_received=0,
                    )
                    for equipo, j in (("A", a), ("B", b))
                    for h in range(1, 19)
                ]
            )

        uc = _caso_de_uso(uow, user_repo, scoring_service, ANTES, campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)

        async with uow:
            hoyo = await uow.hole_scores.find_one(match.id, 1, a.user_id)
            hoyos = await uow.hole_scores.find_by_match(match.id)
        assert hoyo.own_score == 5
        assert len(hoyos) == 36, "no se vuelven a crear"


class TestElHusoSaleDelCampo:
    """El huso vive en el campo, que es donde esta la verdad (BE #305)."""

    @pytest.mark.asyncio
    async def test_3y5_un_campo_sin_coordenadas_no_tiene_huso_y_no_abre_sola(
        self, uow, user_repo, scoring_service, campos
    ):
        """
        Trece de los 805 campos no traen coordenadas. Ahi no se adivina: ese
        partido solo se abre con START, y la pantalla de la competicion lo avisa
        para que nadie se entere en el campo y sin cobertura.
        """
        _c, _r, match, a, b = await _monta(uow)
        campos.campo = _campo(None)

        uc = _caso_de_uso(uow, user_repo, scoring_service, DESPUES, campos)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), 1, _body(b), a.user_id)

        async with uow:
            assert (await uow.matches.find_by_id(match.id)).status == MatchStatus.SCHEDULED

    @pytest.mark.asyncio
    async def test_9b_sin_campo_tampoco_se_inventa_una_hora(
        self, uow, user_repo, scoring_service
    ):
        """Sin repositorio de campos —no deberia pasar— no se abre nada."""
        _c, _r, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, DESPUES, None)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), 1, _body(b), a.user_id)

    @pytest.mark.asyncio
    async def test_6_cada_ronda_usa_el_huso_de_su_propio_campo(self, uow):
        """
        Una competicion puede jugarse en campos de husos distintos —peninsula y
        Canarias el mismo fin de semana—, y por eso el huso no puede vivir en la
        competicion.
        """
        from src.modules.competition.application.dto.round_match_dto import GetScheduleRequestDTO
        from src.modules.competition.application.use_cases.get_schedule_use_case import (
            GetScheduleUseCase,
        )

        competition, ronda_peninsula, _m, _a, _b = await _monta(uow)
        ronda_canarias = Round.create(
            competition_id=competition.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=DIA,
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with uow:
            await uow.rounds.add(ronda_canarias)

        class _DosCampos:
            async def find_by_id(self, golf_course_id):
                if golf_course_id == ronda_canarias.golf_course_id:
                    return _campo("Atlantic/Canary")
                return _campo("Europe/Madrid")

        respuesta = await GetScheduleUseCase(uow, _DosCampos()).execute(
            GetScheduleRequestDTO(competition_id=str(competition.id))
        )

        horas = {
            r.id: r.scoring_opens_at.astimezone(UTC)
            for dia in respuesta.days
            for r in dia.rounds
        }
        assert horas[ronda_peninsula.id.value] == datetime(2026, 9, 20, 4, 0, tzinfo=UTC)
        assert horas[ronda_canarias.id.value] == datetime(2026, 9, 20, 5, 0, tzinfo=UTC)


class TestNoSeAbreDosVeces:
    @pytest.mark.asyncio
    async def test_5_dos_primeros_golpes_seguidos_abren_una_sola_vez(
        self, uow, user_repo, scoring_service, campos
    ):
        """
        Los dos jugadores anotan su primer golpe casi a la vez.

        La carrera de verdad la corta el bloqueo de fila del repositorio SQL; lo
        que se comprueba aqui es que el segundo se encuentra el partido ya
        abierto y NO vuelve a crear los 18 hoyos de cada jugador, que `add_many`
        no deduplica.
        """
        _c, _r, match, a, b = await _monta(uow)
        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)

        await uc.execute(str(match.id), 1, _body(b), a.user_id)
        await uc.execute(str(match.id), 1, _body(a, own=4, marked=6), b.user_id)

        async with uow:
            hoyos = await uow.hole_scores.find_by_match(match.id)
            mio = await uow.hole_scores.find_one(match.id, 1, a.user_id)
            suyo = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert len(hoyos) == 36, "una sola apertura"
        assert mio.own_score == 5
        assert suyo.own_score == 4, "el segundo golpe tambien se guarda"

    @pytest.mark.asyncio
    async def test_5b_si_otro_lo_abrio_entre_medias_no_se_abre_otra_vez(
        self, uow, user_repo, scoring_service, campos
    ):
        """
        La carrera de verdad: leo el partido programado y, antes de que yo lo
        abra, lo abre el golpe del otro jugador. Al tomar el bloqueo hay que
        RELEER el estado; si no, se abre dos veces y cada jugador acaba con 36
        hoyos suyos en vez de 18.
        """
        _c, round_entity, match, _a, _b = await _monta(uow)
        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)

        # El partido que yo leí, todavía programado
        copia_vieja = deepcopy(await uow.matches.find_by_id(match.id))
        assert copia_vieja.status == MatchStatus.SCHEDULED

        # Mientras tanto, el otro jugador lo abre
        async with uow:
            await MatchOpener.open(match, round_entity, uow)
            await uow.matches.update(match)

        async with uow:
            abierto = await uc._abre_si_toca(copia_vieja)
            hoyos = await uow.hole_scores.find_by_match(match.id)

        assert abierto.status == MatchStatus.IN_PROGRESS
        assert len(hoyos) == 36, "no se vuelven a crear los hoyos"

    @pytest.mark.asyncio
    async def test_5c_para_abrirlo_se_bloquea_su_fila(self, uow, user_repo, scoring_service, campos):
        """
        El bloqueo es lo unico que corta la carrera de dos primeros golpes: en
        memoria no se nota, asi que lo que se comprueba es que el camino de
        apertura pide el partido CON bloqueo y no con una lectura normal.
        """
        _c, _r, match, a, b = await _monta(uow)
        pedidos = []
        original = uow.matches.find_by_id_for_update

        async def espia(match_id):
            pedidos.append(match_id)
            return await original(match_id)

        uow.matches.find_by_id_for_update = espia

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        await uc.execute(str(match.id), 1, _body(b), a.user_id)

        assert pedidos == [match.id]

    @pytest.mark.asyncio
    async def test_5d_si_lo_conceden_entre_medias_es_rechazo_no_un_500(
        self, uow, user_repo, scoring_service, campos
    ):
        """
        Conceder el partido es un camino concurrente de verdad. Si pasa entre mi
        lectura y el bloqueo, arrancarlo revienta en el dominio: hay que volver a
        mirar el estado y contestar el 409 de siempre (`/code-review`).
        """
        _c, round_entity, match, _a, _b = await _monta(uow)
        copia_vieja = deepcopy(await uow.matches.find_by_id(match.id))

        # Otro golpe lo abre y, acto seguido, alguien concede
        async with uow:
            await MatchOpener.open(match, round_entity, uow)
            match.concede(conceding_team="A", reason="Lesion")
            await uow.matches.update(match)

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        async with uow:
            with pytest.raises(MatchNotScoringError):
                await uc._abre_si_toca(copia_vieja)

    @pytest.mark.asyncio
    async def test_quien_no_juega_el_partido_no_lo_abre(self, uow, user_repo, scoring_service, campos):
        """
        Abrir bloquea la fila, crea 36 filas y arranca la ronda: eso no lo
        dispara alguien que solo acerto el identificador, y el rechazo de «aun no
        ha abierto» lleva una hora que tampoco es suya (`/code-review`).
        """
        _c, _r, match, _a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        with pytest.raises(NotMatchPlayerError):
            await uc.execute(str(match.id), 1, _body(b), UserId(uuid4()))

        async with uow:
            assert (await uow.matches.find_by_id(match.id)).status == MatchStatus.SCHEDULED
            assert await uow.hole_scores.find_by_match(match.id) == []


class TestLoQueSeLeDiceAlCliente:
    @pytest.mark.asyncio
    async def test_10_la_vista_trae_la_hora_de_apertura(self, uow, user_repo, scoring_service, campos):
        """Para poder ofrecer «Anotar» sin adivinar si alguien pulso START."""
        _c, _r, match, a, b = await _monta(uow)

        uc = _caso_de_uso(uow, user_repo, scoring_service, JUSTO, campos)
        vista = await uc.execute(str(match.id), 1, _body(b), a.user_id)

        assert vista.scoring_opens_at is not None
        assert vista.scoring_opens_at.astimezone(UTC) == JUSTO

    @pytest.mark.asyncio
    async def test_15_el_calendario_tambien(self, uow, campos):
        """La lista de proximos partidos del movil se compone del calendario."""
        from src.modules.competition.application.dto.round_match_dto import GetScheduleRequestDTO
        from src.modules.competition.application.use_cases.get_schedule_use_case import (
            GetScheduleUseCase,
        )

        competition, _r, _m, _a, _b = await _monta(uow)

        respuesta = await GetScheduleUseCase(uow, campos).execute(
            GetScheduleRequestDTO(competition_id=str(competition.id))
        )

        rondas = [r for dia in respuesta.days for r in dia.rounds]
        assert rondas, "la competicion tiene una ronda"
        assert rondas[0].scoring_opens_at.astimezone(UTC) == JUSTO

    @pytest.mark.asyncio
    async def test_9_sin_fecha_la_vista_no_inventa_una_hora(self, uow, user_repo, scoring_service, campos):
        _c, _r, match, a, b = await _monta(uow, estado_partido=MatchStatus.IN_PROGRESS)
        async with uow:
            round_entity = await uow.rounds.find_by_id(match.round_id)
            round_entity._round_date = None
            from src.modules.competition.domain.entities.hole_score import HoleScore

            await uow.hole_scores.add_many(
                [
                    HoleScore.create(
                        match_id=match.id,
                        hole_number=h,
                        player_user_id=j.user_id,
                        team=equipo,
                        strokes_received=0,
                    )
                    for equipo, j in (("A", a), ("B", b))
                    for h in range(1, 19)
                ]
            )

        uc = _caso_de_uso(uow, user_repo, scoring_service, DESPUES, campos)
        vista = await uc.execute(str(match.id), 1, _body(b), a.user_id)

        assert vista.scoring_opens_at is None

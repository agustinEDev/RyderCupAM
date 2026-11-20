"""
Cambiar las barras de una inscripción (BE #912, decidido el 20 nov 2026).

Una jugadora invitada se quedaba en unas barras que el campo no tenía valoradas
para ella, y nadie podía cambiárselas: la generación se bloqueaba para siempre.

Quién y cuándo:

| Competición           | Puede cambiarlas                                              |
|-----------------------|---------------------------------------------------------------|
| DRAFT / ACTIVE / CLOSED | el propio jugador, el capitán de SU equipo, el organizador, un admin |
| IN_PROGRESS           | el capitán de su equipo, el organizador, un admin (no el jugador) |
| COMPLETED / CANCELLED | nadie: 409 TEE_CHANGE_CLOSED a quien podría, 403 a los demás   |

Con la inscripción aprobada. Un capitán de otro equipo o un jugador cualquiera:
403, sin decir antes nada del estado. Sin equipos formados (stroke play, o antes
del reparto) no hay capitanes. El subcapitán no cuenta.

Lo ya jugado no se cambia, pero sí lo que queda por jugar: sus partidos y
partidas generados que aún no han empezado se rehacen con las barras nuevas (en
fourball y foursomes, el partido entero). Si en el campo de alguno no están
valoradas, se rechaza todo con 422 y no cambia nada.

Qué barras: valoradas para su género o sin género en alguno de los campos; en
SCRATCH también las que solo tienen tarjeta (sin golpes no hace falta
valoración). Sin género en el perfil (o sin usuario), solo las mixtas. Sin
barras (null) vuelve a las habituales de su género.
"""

import copy
import logging
from datetime import UTC, date, datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentTeeRequestDTO,
)
from src.modules.competition.application.exceptions import (
    EnrollmentNotApprovedError,
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
    PendingGameNotRecalculableError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)
from src.modules.competition.application.use_cases.change_enrollment_tee_use_case import (
    ChangeEnrollmentTeeUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import TeamAssignmentMode
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
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
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
)

pytestmark = pytest.mark.asyncio

VALORADA = "valorada"
SOLO_TARJETA = "solo tarjeta"
NI_UNA_NI_OTRA = "ni valorada ni con tarjeta"


SLOPES = {TeeColor.YELLOW: 128, TeeColor.RED: 113, TeeColor.BLUE: 145, TeeColor.WHITE: 130}


def _tarjeta(par=4):
    hoyos = []
    for i in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = i
        hoyo.par = par
        hoyo.stroke_index = i
        hoyos.append(hoyo)
    return hoyos


def _campo(barras):
    """
    Un campo con esas barras —(color, sexo) o (color, sexo, cómo)— y 18 hoyos.

    `cómo`: valorada (por defecto), solo tarjeta (un Slope que no se puede
    valorar, con su tarjeta propia) o ni una ni otra.
    """
    tees = []
    for color, sexo, *resto in barras:
        como = resto[0] if resto else VALORADA
        tee = MagicMock()
        tee.color = color
        tee.gender = sexo
        tee.course_rating = Decimal("71.2")
        # Un Slope por color: así cambiar de barras cambia el hándicap de juego
        tee.slope_rating = SLOPES.get(color, 128) if como == VALORADA else 0
        # La tarjeta propia, con pares de 5: así se ve si una foto usa los suyos
        tee.holes = _tarjeta(par=5) if como == SOLO_TARJETA else []
        tee.par_total = 72
        tees.append(tee)
    campo = MagicMock()
    campo.name = "Campo de prueba"
    campo.tees = tees
    campo.reference_card = _tarjeta()
    return campo


class _Campos:
    """Los campos por su id."""

    def __init__(self):
        self.por_id: dict = {}

    async def find_by_id(self, golf_course_id):
        return self.por_id.get(golf_course_id)


class _Usuarios:
    """Los jugadores con su género."""

    def __init__(self):
        self.por_id: dict = {}

    def poner(self, user_id, genero, handicap=Decimal("18.0")):
        usuario = MagicMock()
        usuario.id = user_id
        usuario.gender = genero
        usuario.handicap = MagicMock(value=float(handicap))
        self.por_id[user_id] = usuario

    def quitar(self, user_id):
        self.por_id.pop(user_id)

    async def find_by_id(self, user_id):
        return self.por_id.get(user_id)

    async def find_by_ids(self, user_ids):
        return [self.por_id[u] for u in user_ids if u in self.por_id]


class _Zonas:
    """Todos los campos en Madrid."""

    async def for_course(self, golf_course_id):
        return "Europe/Madrid"


# Aldeamayor: amarillas de hombre y azules y rojas de mujer
ALDEAMAYOR = [
    (TeeColor.YELLOW, Gender.MALE),
    (TeeColor.BLUE, Gender.FEMALE),
    (TeeColor.RED, Gender.FEMALE),
]


class _Mundo:
    """
    Una competición en Aldeamayor con su organizador y cuatro inscritos.

    Con `con_equipos()`: equipo A = capitana y jugadora; equipo B = capitán y otro.
    """

    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        # Antes del día de las rondas de prueba (1 jun 2026): ninguna salió por la hora
        self.ahora = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)
        self.horas: list[datetime] = []
        self.campos = _Campos()
        self.usuarios = _Usuarios()
        self.organizador = UserId(uuid4())
        self.jugadora = UserId(uuid4())
        self.capitana = UserId(uuid4())
        self.capitan_b = UserId(uuid4())
        self.otro = UserId(uuid4())
        self.usuarios.poner(self.organizador, Gender.MALE)
        for mujer in (self.jugadora, self.capitana):
            self.usuarios.poner(mujer, Gender.FEMALE)
        for hombre in (self.capitan_b, self.otro):
            self.usuarios.poner(hombre, Gender.MALE)

    async def montar(self, campos=(ALDEAMAYOR,), play_mode="HANDICAP", tipo=None):
        """Una Ryder por defecto; con `tipo` (STABLEFORD o MEDAL), un stroke play abierto."""
        if tipo is None:
            creada = await create_competition(self.uow, self.organizador, play_mode=play_mode)
            self.competition_id = CompetitionId(creada.id)
        else:
            self.competition_id = CompetitionId(uuid4())
            async with self.uow:
                await self.uow.competitions.add(
                    Competition(
                        id=self.competition_id,
                        creator_id=self.organizador,
                        name=CompetitionName("Stableford de prueba"),
                        dates=DateRange(date(2026, 6, 1), date(2026, 6, 1)),
                        location=Location(CountryCode("ES")),
                        play_mode=PlayMode(play_mode),
                        tournament_type=tipo,
                        status=CompetitionStatus.ACTIVE,
                    )
                )
                await self.uow.commit()
        async with self.uow:
            competicion = await self.uow.competitions.find_by_id(self.competition_id)
            for barras in campos:
                campo_id = GolfCourseId(uuid4())
                self.campos.por_id[campo_id] = _campo(barras)
                competicion.add_golf_course(campo_id, CountryCode("ES"))
            await self.uow.competitions.update(competicion)
            await self.uow.commit()
        self.inscripciones = {}
        for jugador in (self.jugadora, self.capitana, self.capitan_b, self.otro):
            inscripcion = await create_approved_enrollment(
                self.uow, self.competition_id.value, jugador
            )
            # El hándicap del torneo, fijado al cerrar: lo usan las partidas de stroke play
            inscripcion.congelar_handicap(Decimal("18.0"))
            async with self.uow:
                await self.uow.enrollments.update(inscripcion)
                await self.uow.commit()
            self.inscripciones[jugador] = inscripcion
        self.inscripcion = self.inscripciones[self.jugadora]
        return self

    async def _competicion(self, cambio):
        async with self.uow:
            competicion = await self.uow.competitions.find_by_id(self.competition_id)
            cambio(competicion)
            await self.uow.competitions.update(competicion)
            await self.uow.commit()

    async def capitanes(self):
        """Nombra a la capitana (A) y al capitán (B); eso cierra las inscripciones."""
        await self._competicion(
            lambda c: c.name_captains(
                self.capitana,
                self.capitan_b,
                approved_player_ids=list(self.inscripciones),
                has_teams=False,
            )
        )

    async def con_equipos(self):
        await self.capitanes()
        equipos = TeamAssignment.create(
            competition_id=self.competition_id,
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=[self.capitana, self.jugadora],
            team_b_player_ids=[self.capitan_b, self.otro],
        )
        async with self.uow:
            await self.uow.team_assignments.add(equipos)
            await self.uow.commit()
        return self

    async def cerrar(self):
        await self._competicion(lambda c: c.close_enrollments())

    async def empezar(self):
        await self._competicion(lambda c: c.start())

    async def terminar(self):
        await self._competicion(lambda c: c.complete())

    async def cancelar(self):
        await self._competicion(lambda c: c.cancel())

    def caso(self) -> ChangeEnrollmentTeeUseCase:
        return ChangeEnrollmentTeeUseCase(
            self.uow,
            golf_course_repository=self.campos,
            user_repository=self.usuarios,
            zonas=_Zonas(),
            reloj=self._reloj,
        )

    def _reloj(self) -> datetime:
        """La hora fija, o la siguiente de `horas` si se dio una lista (un reloj que avanza)."""
        if self.horas:
            return self.horas.pop(0)
        return self.ahora

    async def cambiar(self, color, quien=None, is_admin=False, de=None):
        inscripcion = self.inscripciones[de] if de else self.inscripcion
        return await self.caso().execute(
            ChangeEnrollmentTeeRequestDTO(enrollment_id=inscripcion.id.value, tee_color=color),
            quien or self.jugadora,
            is_admin=is_admin,
        )

    async def barras_guardadas(self, de=None):
        inscripcion = self.inscripciones[de] if de else self.inscripcion
        guardada = await self.uow.enrollments.find_by_id(inscripcion.id)
        return guardada.tee_color

    async def ronda(self, formato=MatchFormat.SINGLES, campo=0) -> Round:
        """Una sesión en el campo `campo` (el primero por defecto) de la competición."""
        ronda = Round.create(
            competition_id=self.competition_id,
            golf_course_id=list(self.campos.por_id)[campo],
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=formato,
        )
        async with self.uow:
            await self.uow.rounds.add(ronda)
            await self.uow.commit()
        return ronda

    async def partido(
        self,
        team_a,
        team_b,
        formato=MatchFormat.SINGLES,
        campo=0,
        empezado=False,
        handicaps=None,
        barras=None,
        ronda=None,
    ):
        """
        Un partido generado. La foto de cada uno: amarillas de hombre (o la de
        `barras`), hándicap índice 18 (o el de `handicaps`) y 10 golpes de juego.
        """
        ronda = ronda or await self.ronda(formato, campo)
        handicaps = handicaps or {}
        barras = barras or {}

        def jugadores(ids):
            return [
                MatchPlayer.create(
                    user_id=j,
                    playing_handicap=10,
                    tee_color=barras.get(j, (TeeColor.YELLOW, Gender.MALE))[0],
                    tee_gender=barras.get(j, (TeeColor.YELLOW, Gender.MALE))[1],
                    strokes_received=list(range(1, 11)),
                    player_handicap=handicaps.get(j, Decimal("18.0")),
                )
                for j in ids
            ]

        partido = Match.create(
            round_id=ronda.id,
            match_number=1,
            team_a_players=jugadores(team_a),
            team_b_players=jugadores(team_b),
        )
        if empezado:
            partido.start()
        async with self.uow:
            await self.uow.matches.add(partido)
            await self.uow.commit()
        return partido.id

    async def el_partido(self, match_id) -> Match:
        return await self.uow.matches.find_by_id(match_id)

    async def partida_con(self, jugador: UserId, empezada=False, sin_franja=False):
        """
        Una partida de stroke play generada con ella en amarillas, hándicap 18 y 10
        golpes, la primera de una franja que sale a las 09:00 (Madrid) del 1 jun.
        """
        franja = Round.create_franja(
            competition_id=self.competition_id,
            golf_course_id=next(iter(self.campos.por_id)),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            hoja_de_salidas=HojaDeSalidas(time(9, 0), time(11, 0), 10, 4),
        )
        if not sin_franja:
            async with self.uow:
                await self.uow.rounds.add(franja)
                await self.uow.commit()
        partida = Partida.crear(
            self.competition_id,
            franja.id,
            1,
            [
                JugadorDePartida(
                    user_id=jugador,
                    handicap=Decimal("18.0"),
                    playing_handicap=10,
                    tee_color=TeeColor.YELLOW,
                    tee_gender=Gender.MALE,
                    golpes_por_hoyo=(1,) * 10 + (0,) * 8,
                    par_por_hoyo=(4,) * 18,
                )
            ],
        )
        if empezada:
            partida.empezar()
        async with self.uow:
            await self.uow.partidas.anadir([partida])
            await self.uow.commit()
        return partida.id

    async def la_partida(self, partida_id) -> Partida:
        return await self.uow.partidas.find_by_id(partida_id)

    async def inscripcion_en(self, estado: EnrollmentStatus):
        """Una inscripción más, de alguien nuevo, en ese estado."""
        inscripcion = Enrollment(
            id=EnrollmentId.generate(),
            competition_id=self.competition_id,
            user_id=UserId(uuid4()),
            status=estado,
        )
        async with self.uow:
            await self.uow.enrollments.add(inscripcion)
            await self.uow.commit()
        return inscripcion


class TestQuienPuedeAntesDeEmpezar:
    async def test_change_tee_by_the_player_saves_it(self):
        """
        Given una jugadora inscrita en una competición abierta en Aldeamayor
        When cambia sus barras a azules (valoradas para mujer)
        Then quedan guardadas
        """
        mundo = await _Mundo().montar()

        respuesta = await mundo.cambiar(TeeColor.BLUE)

        assert respuesta.tee_color == "BLUE"
        assert await mundo.barras_guardadas() == TeeColor.BLUE

    async def test_change_tee_by_the_organizer_saves_it(self):
        """
        Given una jugadora inscrita
        When el organizador, que no juega, le cambia las barras
        Then quedan guardadas
        """
        mundo = await _Mundo().montar()

        await mundo.cambiar(TeeColor.RED, quien=mundo.organizador)

        assert await mundo.barras_guardadas() == TeeColor.RED

    async def test_change_tee_by_an_admin_saves_it(self):
        """
        Given una jugadora inscrita
        When un admin que no es el organizador le cambia las barras
        Then quedan guardadas, como en el resto de la gestión de inscritos
        """
        mundo = await _Mundo().montar()

        await mundo.cambiar(TeeColor.RED, quien=UserId(uuid4()), is_admin=True)

        assert await mundo.barras_guardadas() == TeeColor.RED

    async def test_change_tee_by_the_captain_of_her_team_saves_it(self):
        """
        Given equipos formados y la jugadora en el equipo de la capitana
        When la capitana le cambia las barras
        Then quedan guardadas
        """
        mundo = await (await _Mundo().montar()).con_equipos()

        await mundo.cambiar(TeeColor.RED, quien=mundo.capitana)

        assert await mundo.barras_guardadas() == TeeColor.RED

    async def test_change_tee_by_the_captain_for_herself_saves_it(self):
        """
        Given equipos formados
        When la capitana cambia las suyas
        Then quedan guardadas
        """
        mundo = await (await _Mundo().montar()).con_equipos()

        await mundo.cambiar(TeeColor.BLUE, quien=mundo.capitana, de=mundo.capitana)

        assert await mundo.barras_guardadas(de=mundo.capitana) == TeeColor.BLUE

    async def test_change_tee_by_the_captain_of_the_other_team_is_forbidden(self):
        """
        Given equipos formados
        When el capitán del otro equipo intenta cambiar las barras de la jugadora
        Then no puede (403) y se quedan como estaban
        """
        mundo = await (await _Mundo().montar()).con_equipos()

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.capitan_b)

        assert await mundo.barras_guardadas() is None

    async def test_change_tee_by_a_captain_without_teams_is_forbidden(self):
        """
        Given capitanes nombrados pero sin equipos formados
        When la capitana intenta cambiar las barras de la jugadora
        Then no puede: sin equipos no hay «su equipo»
        """
        mundo = await _Mundo().montar()
        await mundo.capitanes()

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.capitana)

    async def test_change_tee_by_another_player_is_forbidden(self):
        """
        Given una jugadora inscrita
        When otro jugador intenta cambiarle las barras
        Then no puede (403) y se quedan como estaban
        """
        mundo = await _Mundo().montar()

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.otro)

        assert await mundo.barras_guardadas() is None

    async def test_change_tee_of_an_unknown_enrollment_is_not_found(self):
        """
        Given una inscripción que no existe
        When se intenta cambiar sus barras
        Then no se encuentra
        """
        mundo = await _Mundo().montar()

        with pytest.raises(EnrollmentNotFoundError):
            await mundo.caso().execute(
                ChangeEnrollmentTeeRequestDTO(enrollment_id=uuid4(), tee_color=TeeColor.RED),
                mundo.jugadora,
            )

    async def test_change_tee_locks_the_competition(self):
        """
        Given una jugadora inscrita
        When cambia sus barras
        Then se lee la competición con bloqueo, como al generar y al quitar: que
            no se generen sus partidos entre la comprobación y el cambio
        """
        mundo = await _Mundo().montar()
        mundo.uow.competitions.find_by_id_for_update = AsyncMock(
            wraps=mundo.uow.competitions.find_by_id_for_update
        )

        await mundo.cambiar(TeeColor.BLUE)

        mundo.uow.competitions.find_by_id_for_update.assert_awaited_once()


class TestQuienPuedeYaEmpezada:
    @pytest.mark.parametrize(
        "quien",
        ["capitana", "organizador", "admin"],
    )
    async def test_change_tee_in_progress_by_captain_organizer_or_admin_saves_it(self, quien):
        """
        Given la competición en curso, equipos formados y la jugadora sin partido
        When la capitana de su equipo, el organizador o un admin le cambian las barras
        Then se guardan: la sesión 2 de una Ryder se genera ya empezada
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()
        quienes = {
            "capitana": (mundo.capitana, False),
            "organizador": (mundo.organizador, False),
            "admin": (UserId(uuid4()), True),
        }
        user_id, is_admin = quienes[quien]

        await mundo.cambiar(TeeColor.RED, quien=user_id, is_admin=is_admin)

        assert await mundo.barras_guardadas() == TeeColor.RED

    async def test_change_tee_in_progress_by_the_player_is_forbidden(self):
        """
        Given la competición en curso
        When la propia jugadora (no capitana) intenta cambiar sus barras
        Then no puede (403)
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED)

    async def test_change_tee_in_progress_by_the_captain_of_the_other_team_is_forbidden(self):
        """
        Given la competición en curso
        When el capitán del otro equipo intenta cambiar las barras de la jugadora
        Then no puede (403)
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.capitan_b)

    @pytest.mark.parametrize("final", ["terminar", "cancelar"])
    async def test_change_tee_once_finished_is_closed_for_the_organizer(self, final):
        """
        Given una competición terminada o cancelada
        When el organizador intenta cambiar las barras
        Then ya no se puede (409 TEE_CHANGE_CLOSED)
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        if final == "terminar":
            await mundo.empezar()
        await getattr(mundo, final)()

        with pytest.raises(TeeChangeClosedError) as error:
            await mundo.cambiar(TeeColor.RED, quien=mundo.organizador)

        assert error.value.error_code == "TEE_CHANGE_CLOSED"

    async def test_change_tee_once_finished_by_the_player_is_forbidden_not_closed(self):
        """
        Given una competición terminada
        When la propia jugadora intenta cambiar sus barras
        Then es un 403: no se le dice nada del estado a quien no puede
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()
        await mundo.terminar()

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED)


class TestQueBarras:
    async def test_change_tee_to_one_not_rated_for_her_gender_is_rejected(self):
        """
        Given Aldeamayor, sin amarillas de mujer
        When la jugadora elige amarillas
        Then se rechaza (422 TEE_NOT_AVAILABLE) y se quedan como estaban
        """
        mundo = await _Mundo().montar()

        with pytest.raises(TeeNotAvailableError) as error:
            await mundo.cambiar(TeeColor.YELLOW)

        assert error.value.error_code == "TEE_NOT_AVAILABLE"
        assert await mundo.barras_guardadas() is None

    async def test_change_tee_rated_only_on_the_second_course_saves_it(self):
        """
        Given una competición con dos campos, y amarillas de mujer solo en el segundo
        When la jugadora elige amarillas
        Then valen: basta con alguno de los campos
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, [(TeeColor.YELLOW, Gender.FEMALE)]))

        await mundo.cambiar(TeeColor.YELLOW)

        assert await mundo.barras_guardadas() == TeeColor.YELLOW

    async def test_change_tee_to_a_mixed_one_saves_it(self):
        """
        Given un campo con blancas sin género
        When la jugadora elige blancas
        Then valen (valoradas sin género)
        """
        mundo = await _Mundo().montar(campos=([(TeeColor.WHITE, None)],))

        await mundo.cambiar(TeeColor.WHITE)

        assert await mundo.barras_guardadas() == TeeColor.WHITE

    async def test_change_tee_of_a_player_without_gender_rejects_a_gendered_tee(self):
        """
        Given un jugador sin género en su perfil
        When elige rojas, que solo están valoradas para mujer
        Then se rechaza: sin género solo valen las mixtas
        """
        mundo = await _Mundo().montar()
        mundo.usuarios.poner(mundo.jugadora, None)

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.RED)

    async def test_change_tee_of_a_player_without_gender_accepts_a_mixed_tee(self):
        """
        Given un jugador sin género en su perfil y un campo con blancas mixtas
        When elige blancas
        Then valen
        """
        mundo = await _Mundo().montar(campos=([(TeeColor.WHITE, None)],))
        mundo.usuarios.poner(mundo.jugadora, None)

        await mundo.cambiar(TeeColor.WHITE)

        assert await mundo.barras_guardadas() == TeeColor.WHITE

    async def test_change_tee_of_an_unknown_user_is_treated_as_without_gender(self):
        """
        Given una inscripción cuyo usuario ya no se encuentra
        When el organizador elige rojas, valoradas solo para mujer
        Then se rechaza, como sin género
        """
        mundo = await _Mundo().montar()
        mundo.usuarios.quitar(mundo.jugadora)

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.organizador)

    async def test_change_tee_in_scratch_of_a_player_without_gender_accepts_a_mixed_card(self):
        """
        Given una competición SCRATCH y blancas mixtas con tarjeta, sin valorar
        When un jugador sin género elige blancas
        Then valen
        """
        mundo = await _Mundo().montar(
            campos=([(TeeColor.WHITE, None, SOLO_TARJETA)],), play_mode="SCRATCH"
        )
        mundo.usuarios.poner(mundo.jugadora, None)

        await mundo.cambiar(TeeColor.WHITE)

        assert await mundo.barras_guardadas() == TeeColor.WHITE

    async def test_change_tee_in_scratch_accepts_a_tee_with_card_but_no_rating(self):
        """
        Given una competición SCRATCH y un campo con blancas de mujer con tarjeta
            pero sin valoración posible
        When la jugadora elige blancas
        Then valen: sin golpes no hace falta valorarlas
        """
        mundo = await _Mundo().montar(
            campos=([(TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)],), play_mode="SCRATCH"
        )

        await mundo.cambiar(TeeColor.WHITE)

        assert await mundo.barras_guardadas() == TeeColor.WHITE

    async def test_change_tee_with_handicap_rejects_a_tee_with_card_but_no_rating(self):
        """
        Given una competición con hándicap y las mismas blancas sin valoración
        When la jugadora elige blancas
        Then se rechaza: con golpes hace falta la valoración
        """
        mundo = await _Mundo().montar(
            campos=([(TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)],), play_mode="HANDICAP"
        )

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.WHITE)

    async def test_change_tee_in_scratch_rejects_a_tee_without_card_nor_rating(self):
        """
        Given una competición SCRATCH y unas blancas de mujer sin tarjeta ni valoración
        When la jugadora elige blancas
        Then se rechaza
        """
        mundo = await _Mundo().montar(
            campos=([(TeeColor.WHITE, Gender.FEMALE, NI_UNA_NI_OTRA)],), play_mode="SCRATCH"
        )

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.WHITE)

    async def test_change_tee_in_scratch_rejects_a_card_of_the_other_gender(self):
        """
        Given una competición SCRATCH y blancas con tarjeta solo de hombre
        When la jugadora elige blancas
        Then se rechaza: nunca las del otro género
        """
        mundo = await _Mundo().montar(
            campos=([(TeeColor.WHITE, Gender.MALE, SOLO_TARJETA)],), play_mode="SCRATCH"
        )

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.WHITE)

    async def test_change_tee_to_none_goes_back_to_the_default(self):
        """
        Given una jugadora que eligió azules
        When pide volver a las de por defecto (null)
        Then se quedan sin elegir, y juega desde las habituales de su género
        """
        mundo = await _Mundo().montar()
        await mundo.cambiar(TeeColor.BLUE)

        respuesta = await mundo.cambiar(None)

        assert respuesta.tee_color is None
        assert await mundo.barras_guardadas() is None


class TestCuando:
    async def test_change_tee_with_the_competition_closed_saves_it(self):
        """
        Given una competición con las inscripciones cerradas, sin partidos
        When la jugadora cambia sus barras
        Then se guardan: aún no se ha calculado nada con ellas
        """
        mundo = await _Mundo().montar()
        await mundo.cerrar()

        await mundo.cambiar(TeeColor.BLUE)

        assert await mundo.barras_guardadas() == TeeColor.BLUE

    @pytest.mark.parametrize(
        "estado",
        [
            EnrollmentStatus.REQUESTED,
            EnrollmentStatus.INVITED,
            EnrollmentStatus.REJECTED,
            EnrollmentStatus.CANCELLED,
            EnrollmentStatus.WITHDRAWN,
        ],
    )
    async def test_change_tee_of_an_enrollment_not_approved_is_rejected(self, estado):
        """
        Given una inscripción que no está aprobada
        When el organizador intenta cambiar sus barras
        Then no se puede (409 ENROLLMENT_NOT_APPROVED)
        """
        mundo = await _Mundo().montar()
        inscripcion = await mundo.inscripcion_en(estado)

        with pytest.raises(EnrollmentNotApprovedError) as error:
            await mundo.caso().execute(
                ChangeEnrollmentTeeRequestDTO(
                    enrollment_id=inscripcion.id.value, tee_color=TeeColor.RED
                ),
                mundo.organizador,
            )

        assert error.value.error_code == "ENROLLMENT_NOT_APPROVED"


class TestLoQueQuedaPorJugar:
    """
    No se cambia lo ya jugado, pero sí lo que queda por jugar (Agustín, 20 nov):
    en sus partidos y partidas generados sin empezar cambia SU barra y lo que
    depende de ella. Los demás se quedan como se generaron.
    """

    async def test_change_tee_recalculates_her_scheduled_match_with_her_saved_handicap(self):
        """
        Given la jugadora con un individual programado en amarillas, con su hándicap
            índice guardado en el partido (12) distinto del de su perfil (18)
        When cambia a rojas
        Then su partido la lleva en rojas de mujer, con el hándicap de juego que sale
            de su índice GUARDADO; el rival conserva su barra y su índice
        """
        mundo = await _Mundo().montar()
        partido = await mundo.partido(
            [mundo.jugadora], [mundo.otro], handicaps={mundo.jugadora: Decimal("12.0")}
        )

        await mundo.cambiar(TeeColor.RED)

        rehecho = await mundo.el_partido(partido)
        ella = rehecho.find_player(mundo.jugadora)
        assert (ella.tee_color, ella.tee_gender) == (TeeColor.RED, Gender.FEMALE)
        assert ella.player_handicap == Decimal("12.0")
        # 12 con Slope 113 y CR 71,2 sobre par 72 al 100 %: 11
        assert ella.playing_handicap == 11
        rival = rehecho.find_player(mundo.otro)
        assert (rival.tee_color, rival.tee_gender, rival.player_handicap) == (
            TeeColor.YELLOW,
            Gender.MALE,
            Decimal("18.0"),
        )

    async def test_change_tee_leaves_a_started_match_alone(self):
        """
        Given la jugadora con un individual ya empezado
        When cambia a rojas
        Then ese partido sigue como se generó: lo jugado no se toca
        """
        mundo = await _Mundo().montar()
        partido = await mundo.partido([mundo.jugadora], [mundo.otro], empezado=True)

        await mundo.cambiar(TeeColor.RED)

        ella = (await mundo.el_partido(partido)).find_player(mundo.jugadora)
        assert (ella.tee_color, ella.playing_handicap) == (TeeColor.YELLOW, 10)
        assert await mundo.barras_guardadas() == TeeColor.RED

    async def test_change_tee_in_fourball_keeps_the_others_and_moves_the_allocation(self):
        """
        Given un fourball programado en el que la jugadora tiene el índice más bajo
        When cambia a azules y luego a rojas
        Then la pareja y los rivales conservan su barra y su índice guardados, pero
            el reparto (sale de la diferencia con el más bajo) se mueve con ella
        """
        mundo = await _Mundo().montar()
        partido = await mundo.partido(
            [mundo.jugadora, mundo.capitana],
            [mundo.capitan_b, mundo.otro],
            formato=MatchFormat.FOURBALL,
            handicaps={mundo.jugadora: Decimal("2.0")},
        )

        await mundo.cambiar(TeeColor.BLUE)
        con_azules = (await mundo.el_partido(partido)).find_player(mundo.capitana)
        await mundo.cambiar(TeeColor.RED)
        rehecho = await mundo.el_partido(partido)

        for user_id in (mundo.capitana, mundo.capitan_b, mundo.otro):
            foto = rehecho.find_player(user_id)
            assert (foto.tee_color, foto.tee_gender, foto.player_handicap) == (
                TeeColor.YELLOW,
                Gender.MALE,
                Decimal("18.0"),
            )
        companera = rehecho.find_player(mundo.capitana)
        assert companera.playing_handicap != con_azules.playing_handicap
        assert companera.strokes_received != con_azules.strokes_received

    async def test_change_tee_to_the_same_tee_again_changes_nothing(self):
        """
        Given la jugadora ya en rojas de mujer en su partido programado (su foto)
        When elige rojas
        Then el partido queda idéntico: ni ella ni nadie cambia
        """
        mundo = await _Mundo().montar()
        partido = await mundo.partido(
            [mundo.jugadora],
            [mundo.otro],
            barras={mundo.jugadora: (TeeColor.RED, Gender.FEMALE)},
        )
        antes = await mundo.el_partido(partido)
        fotos = (antes.team_a_players, antes.team_b_players, antes.handicap_strokes_given)

        await mundo.cambiar(TeeColor.RED)
        await mundo.cambiar(TeeColor.RED)

        despues = await mundo.el_partido(partido)
        assert (
            despues.team_a_players,
            despues.team_b_players,
            despues.handicap_strokes_given,
        ) == fotos

    async def test_change_tee_back_to_default_recalculates_with_her_usual_tee(self):
        """
        Given la jugadora en azules con un individual programado
        When vuelve a las de por defecto (null)
        Then su partido la lleva en rojas, las habituales de mujer
        """
        mundo = await _Mundo().montar()
        await mundo.cambiar(TeeColor.BLUE)
        partido = await mundo.partido([mundo.jugadora], [mundo.otro])

        await mundo.cambiar(None)

        ella = (await mundo.el_partido(partido)).find_player(mundo.jugadora)
        assert ella.tee_color == TeeColor.RED

    async def test_change_tee_not_rated_on_a_pending_match_course_changes_nothing(self):
        """
        Given dos campos: el primero con rojas de mujer, el segundo sin ellas, y su
            partido programado en el segundo
        When la jugadora elige rojas
        Then se rechaza (422 TEE_NOT_AVAILABLE, por SU barra) y no cambia nada
        """
        mundo = await _Mundo().montar(
            campos=(ALDEAMAYOR, [(TeeColor.YELLOW, Gender.MALE), (TeeColor.BLUE, Gender.FEMALE)])
        )
        partido = await mundo.partido([mundo.jugadora], [mundo.otro], campo=1)

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.RED)

        assert await mundo.barras_guardadas() is None
        ella = (await mundo.el_partido(partido)).find_player(mundo.jugadora)
        assert ella.tee_color == TeeColor.YELLOW

    async def test_change_tee_with_a_rival_tee_no_longer_rated_is_a_conflict(self):
        """
        Given su partido programado con un rival en blancas, que el campo ya no tiene
        When la jugadora elige rojas
        Then 409 PENDING_GAME_NOT_RECALCULABLE (no un 422 por la barra de otro) y no
            cambia nada
        """
        mundo = await _Mundo().montar()
        partido = await mundo.partido(
            [mundo.jugadora], [mundo.otro], barras={mundo.otro: (TeeColor.WHITE, Gender.MALE)}
        )

        with pytest.raises(PendingGameNotRecalculableError) as error:
            await mundo.cambiar(TeeColor.RED)

        assert error.value.error_code == "PENDING_GAME_NOT_RECALCULABLE"
        assert await mundo.barras_guardadas() is None
        assert (await mundo.el_partido(partido)).find_player(mundo.jugadora).playing_handicap == 10

    async def test_change_tee_with_a_match_on_a_missing_course_is_a_conflict(self):
        """
        Given su partido programado en una sesión cuyo campo ya no existe
        When la jugadora elige rojas
        Then 409 PENDING_GAME_NOT_RECALCULABLE, no un 500
        """
        mundo = await _Mundo().montar()
        ronda = Round.create(
            competition_id=mundo.competition_id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with mundo.uow:
            await mundo.uow.rounds.add(ronda)
            await mundo.uow.commit()
        await mundo.partido([mundo.jugadora], [mundo.otro], ronda=ronda)

        with pytest.raises(PendingGameNotRecalculableError):
            await mundo.cambiar(TeeColor.RED)

    async def test_change_tee_with_a_match_without_saved_handicap_is_a_conflict(self):
        """
        Given su partido programado de antes de guardar el hándicap índice (sin foto)
        When la jugadora elige rojas
        Then 409: no se rehace con el del perfil, que no llega a lo ya generado
        """
        mundo = await _Mundo().montar()
        await mundo.partido([mundo.jugadora], [mundo.otro], handicaps={mundo.otro: None})

        with pytest.raises(PendingGameNotRecalculableError):
            await mundo.cambiar(TeeColor.RED)

    async def test_change_tee_in_progress_by_her_captain_recalculates_session_two(self):
        """
        Given la competición en curso y la jugadora con un partido de la sesión 2
            generado y sin empezar
        When la capitana de su equipo le cambia las barras
        Then se guardan y su partido sale con ellas
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()
        partido = await mundo.partido([mundo.jugadora], [mundo.otro])

        await mundo.cambiar(TeeColor.RED, quien=mundo.capitana)

        ella = (await mundo.el_partido(partido)).find_player(mundo.jugadora)
        assert ella.tee_color == TeeColor.RED

    async def test_change_tee_recalculates_her_scheduled_tee_group(self):
        """
        Given la jugadora en una partida de stroke play generada, sin golpes y antes
            de su hora
        When cambia a rojas
        Then la partida la lleva en rojas de mujer, con el hándicap del torneo de su
            foto (18)
        """
        mundo = await _Mundo().montar()
        partida = await mundo.partida_con(mundo.jugadora)

        await mundo.cambiar(TeeColor.RED)

        [ella] = (await mundo.la_partida(partida)).jugadores
        assert (ella.tee_color, ella.tee_gender) == (TeeColor.RED, Gender.FEMALE)
        assert ella.handicap == Decimal("18.0")
        assert ella.playing_handicap != 10

    async def test_change_tee_leaves_a_started_tee_group_alone(self):
        """
        Given la jugadora en una partida con golpes
        When cambia a rojas
        Then la partida sigue como se generó
        """
        mundo = await _Mundo().montar()
        partida = await mundo.partida_con(mundo.jugadora, empezada=True)

        await mundo.cambiar(TeeColor.RED)

        [ella] = (await mundo.la_partida(partida)).jugadores
        assert (ella.tee_color, ella.playing_handicap) == (TeeColor.YELLOW, 10)

    async def test_change_tee_leaves_a_tee_group_whose_time_has_come_alone(self):
        """
        Given la jugadora en una partida sin golpes cuya hora (09:00 en Madrid) ya pasó
        When cambia a rojas
        Then la partida no se toca: ya salió (#544, «tiene golpes o le llegó su hora»)
        """
        mundo = await _Mundo().montar()
        partida = await mundo.partida_con(mundo.jugadora)
        mundo.ahora = datetime(2026, 6, 1, 8, 30, tzinfo=UTC)  # 10:30 en Madrid

        await mundo.cambiar(TeeColor.RED)

        [ella] = (await mundo.la_partida(partida)).jugadores
        assert (ella.tee_color, ella.playing_handicap) == (TeeColor.YELLOW, 10)

    async def test_change_tee_with_a_tee_group_of_a_missing_session_is_a_conflict(self):
        """
        Given una partida suya de una franja que ya no existe
        When cambia sus barras
        Then 409 PENDING_GAME_NOT_RECALCULABLE: no se salta en silencio
        """
        mundo = await _Mundo().montar()
        await mundo.partida_con(mundo.jugadora, sin_franja=True)

        with pytest.raises(PendingGameNotRecalculableError):
            await mundo.cambiar(TeeColor.RED)

    async def test_change_tee_leaves_matches_of_others_alone(self):
        """
        Given un partido programado en el que ella no juega
        When cambia sus barras
        Then ese partido no se toca
        """
        mundo = await _Mundo().montar()
        partido = await mundo.partido([mundo.capitana], [mundo.otro])

        await mundo.cambiar(TeeColor.RED)

        assert (await mundo.el_partido(partido)).find_player(mundo.capitana).playing_handicap == 10


class TestLosBloqueosYLasLecturas:
    """Quinta ronda (/code-review): sin 500, sin bloquear lo que está en juego, sin N+1."""

    async def test_change_tee_skips_a_tee_group_she_left_before_the_lock(self):
        """
        Given una partida suya que, al bloquearla, ya no la tiene (la movieron)
        When cambia sus barras
        Then esa partida se salta, sin un 500, y su inscripción cambia
        """
        mundo = await _Mundo().montar()
        partida_id = await mundo.partida_con(mundo.jugadora)
        sin_ella = copy.deepcopy(await mundo.la_partida(partida_id))
        sin_ella.acompanar(
            JugadorDePartida(
                user_id=mundo.capitana,
                handicap=Decimal("18.0"),
                playing_handicap=10,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
                golpes_por_hoyo=(1,) * 10 + (0,) * 8,
                par_por_hoyo=(4,) * 18,
            )
        )
        sin_ella.quitar(mundo.jugadora)
        mundo.uow.partidas.find_by_id_for_update = AsyncMock(return_value=sin_ella)

        await mundo.cambiar(TeeColor.RED)

        assert await mundo.barras_guardadas() == TeeColor.RED

    async def test_change_tee_in_scratch_keeps_a_missing_saved_handicap_missing(self):
        """
        Given una Ryder SCRATCH con un individual programado en el que ni ella ni el
            rival tienen hándicap índice guardado
        When cambia a rojas
        Then los dos siguen sin él: no se reescribe a 0
        """
        mundo = await _Mundo().montar(play_mode="SCRATCH")
        partido = await mundo.partido(
            [mundo.jugadora],
            [mundo.otro],
            handicaps={mundo.jugadora: None, mundo.otro: None},
        )

        await mundo.cambiar(TeeColor.RED)

        rehecho = await mundo.el_partido(partido)
        assert rehecho.find_player(mundo.jugadora).tee_color == TeeColor.RED
        assert rehecho.find_player(mundo.jugadora).player_handicap is None
        assert rehecho.find_player(mundo.otro).player_handicap is None

    async def test_change_tee_does_not_lock_a_tee_group_that_already_left(self):
        """
        Given una partida suya cuya hora ya pasó
        When cambia sus barras
        Then ni se bloquea: solo se bloquea lo que queda por salir
        """
        mundo = await _Mundo().montar()
        await mundo.partida_con(mundo.jugadora)
        mundo.ahora = datetime(2026, 6, 1, 8, 30, tzinfo=UTC)
        mundo.uow.partidas.find_by_id_for_update = AsyncMock(
            wraps=mundo.uow.partidas.find_by_id_for_update
        )

        await mundo.cambiar(TeeColor.RED)

        mundo.uow.partidas.find_by_id_for_update.assert_not_awaited()

    async def test_change_tee_does_not_lock_a_started_match(self):
        """
        Given un partido suyo ya empezado
        When cambia sus barras
        Then ni se bloquea
        """
        mundo = await _Mundo().montar()
        await mundo.partido([mundo.jugadora], [mundo.otro], empezado=True)
        mundo.uow.matches.find_by_id_for_update = AsyncMock(
            wraps=mundo.uow.matches.find_by_id_for_update
        )

        await mundo.cambiar(TeeColor.RED)

        mundo.uow.matches.find_by_id_for_update.assert_not_awaited()

    async def test_change_tee_skips_a_tee_group_that_left_while_locking(self):
        """
        Given una partida suya sin salir al leerla, con golpes al bloquearla
        When cambia sus barras
        Then se salta: cuenta lo leído con el bloqueo
        """
        mundo = await _Mundo().montar()
        partida_id = await mundo.partida_con(mundo.jugadora)
        en_juego = copy.deepcopy(await mundo.la_partida(partida_id))
        en_juego.empezar()
        mundo.uow.partidas.find_by_id_for_update = AsyncMock(return_value=en_juego)

        await mundo.cambiar(TeeColor.RED)

        [ella] = (await mundo.la_partida(partida_id)).jugadores
        assert ella.tee_color == TeeColor.YELLOW

    async def test_change_tee_reads_each_course_once(self):
        """
        Given dos partidos suyos pendientes en el mismo campo
        When cambia sus barras
        Then el campo se lee una sola vez en toda la ejecución
        """
        mundo = await _Mundo().montar()
        await mundo.partido([mundo.jugadora], [mundo.otro])
        await mundo.partido([mundo.jugadora], [mundo.capitan_b])
        mundo.campos.find_by_id = AsyncMock(wraps=mundo.campos.find_by_id)

        await mundo.cambiar(TeeColor.RED)

        assert mundo.campos.find_by_id.await_count == 1


class TestLosDeCodeRabbit:
    """Sexta ronda (CodeRabbit en la PR #915)."""

    async def test_change_tee_rechecks_a_tee_group_with_a_fresh_time_after_the_lock(self):
        """
        Given una partida suya que no había salido al leerla, cuya hora llega
            mientras se bloquea (el reloj avanza)
        When cambia sus barras
        Then con el bloqueo se mira con la hora nueva, y la partida no se toca
        """
        mundo = await _Mundo().montar()
        partida = await mundo.partida_con(mundo.jugadora)
        mundo.horas = [
            datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
            datetime(2026, 6, 1, 8, 30, tzinfo=UTC),  # 10:30 en Madrid
        ]

        await mundo.cambiar(TeeColor.RED)

        [ella] = (await mundo.la_partida(partida)).jugadores
        assert (ella.tee_color, ella.playing_handicap) == (TeeColor.YELLOW, 10)

    async def test_change_tee_to_her_saved_tee_needs_no_saved_handicaps(self):
        """
        Given su partido con ella ya en rojas de mujer y un rival sin índice guardado
        When elige rojas
        Then no hay nada que rehacer: ni 409 por el índice del rival, el partido
            queda igual y su inscripción cambia
        """
        mundo = await _Mundo().montar()
        partido = await mundo.partido(
            [mundo.jugadora],
            [mundo.otro],
            barras={mundo.jugadora: (TeeColor.RED, Gender.FEMALE)},
            handicaps={mundo.otro: None},
        )

        await mundo.cambiar(TeeColor.RED)

        assert await mundo.barras_guardadas() == TeeColor.RED
        assert (await mundo.el_partido(partido)).find_player(mundo.jugadora).playing_handicap == 10

    async def test_change_tee_to_her_saved_tee_no_longer_rated_there_is_rejected(self):
        """
        Given su partido en un campo que ya no valora las rojas, con ella guardada en
            rojas mixtas (la misma clave que daría su barra nueva allí)
        When elige rojas (las tiene el otro campo de la competición)
        Then 422: aunque la clave sea la guardada, en ese campo ya no está valorada
        """
        mundo = await _Mundo().montar(
            campos=(ALDEAMAYOR, [(TeeColor.YELLOW, Gender.MALE), (TeeColor.BLUE, Gender.FEMALE)])
        )
        await mundo.partido(
            [mundo.jugadora],
            [mundo.otro],
            campo=1,
            barras={mundo.jugadora: (TeeColor.RED, None)},
        )

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.RED)

    async def test_change_tee_in_scratch_keeps_the_others_snapshots_as_they_are(self):
        """
        Given una Ryder SCRATCH con un fourball suyo programado y una compañera
            guardada en blancas, que el campo ya no tiene
        When la jugadora cambia a rojas
        Then solo su foto cambia: la de la compañera y las de los rivales quedan tal
            cual, sin volver a buscarlas en el campo
        """
        mundo = await _Mundo().montar(play_mode="SCRATCH")
        partido = await mundo.partido(
            [mundo.jugadora, mundo.capitana],
            [mundo.capitan_b, mundo.otro],
            formato=MatchFormat.FOURBALL,
            barras={mundo.capitana: (TeeColor.WHITE, Gender.FEMALE)},
        )
        antes = await mundo.el_partido(partido)
        otros = [antes.find_player(u) for u in (mundo.capitana, mundo.capitan_b, mundo.otro)]

        await mundo.cambiar(TeeColor.RED)

        rehecho = await mundo.el_partido(partido)
        assert rehecho.find_player(mundo.jugadora).tee_color == TeeColor.RED
        assert [rehecho.find_player(u) for u in (mundo.capitana, mundo.capitan_b, mundo.otro)] == (
            otros
        )

    @pytest.mark.parametrize("tipo", [TournamentType.STABLEFORD, TournamentType.MEDAL])
    async def test_change_tee_in_a_scratch_stroke_play_uses_the_pars_of_the_card(self, tipo):
        """
        Given un stroke play SCRATCH y un campo con blancas de mujer que solo tienen
            tarjeta (pares de 5), con una partida suya pendiente
        When la jugadora elige blancas
        Then su foto nueva lleva los pares de esa tarjeta (`pars_by_tee`)
        """
        mundo = await _Mundo().montar(
            campos=(
                [(TeeColor.YELLOW, Gender.MALE), (TeeColor.WHITE, Gender.FEMALE, SOLO_TARJETA)],
            ),
            play_mode="SCRATCH",
            tipo=tipo,
        )
        partida = await mundo.partida_con(mundo.jugadora)

        await mundo.cambiar(TeeColor.WHITE)

        [ella] = (await mundo.la_partida(partida)).jugadores
        assert (ella.tee_color, ella.tee_gender) == (TeeColor.WHITE, Gender.FEMALE)
        assert ella.par_por_hoyo == (5,) * 18


class TestElRastro:
    async def test_change_tee_logs_who_what_and_how_many(self, caplog):
        """
        Given la jugadora con un partido y una partida pendientes
        When la capitana de su equipo le cambia las barras a rojas
        Then queda en el log quién, de qué inscripción, la barra antes y después,
            como qué lo hizo y cuántos partidos y partidas se rehicieron; con ids,
            sin nombres
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.partido([mundo.jugadora], [mundo.otro])
        await mundo.partida_con(mundo.jugadora)

        with caplog.at_level(logging.INFO):
            await mundo.cambiar(TeeColor.RED, quien=mundo.capitana)

        [registro] = [r for r in caplog.records if "Tee change" in r.getMessage()]
        mensaje = registro.getMessage()
        for trozo in (
            str(mundo.capitana.value),
            str(mundo.inscripcion.id.value),
            "as=captain",
            "from=None",
            "to=RED",
            "matches=1",
            "tee_groups=1",
        ):
            assert trozo in mensaje


class TestQuienPuedeMas:
    async def test_change_tee_by_a_captain_of_another_competition_is_forbidden(self):
        """
        Given la capitana de otra competición, que no juega en esta
        When intenta cambiar las barras de la jugadora
        Then 403
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        otra = await (await _Mundo().montar()).con_equipos()

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED, quien=otra.capitana)

    async def test_change_tee_by_the_vice_captain_is_forbidden(self):
        """
        Given la jugadora, subcapitana del equipo A
        When intenta cambiar las barras de su capitana, de su mismo equipo
        Then 403: el subcapitán no cuenta como capitán (Agustín, 20 nov)
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo._competicion(
            lambda c: c.name_vice_captain(
                "A", mundo.jugadora, [mundo.capitana, mundo.jugadora], has_teams=True
            )
        )

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.jugadora, de=mundo.capitana)

    async def test_change_tee_unauthorized_locks_nothing(self):
        """
        Given una jugadora inscrita
        When otro jugador intenta cambiarle las barras
        Then 403 sin llegar a bloquear la competición
        """
        mundo = await _Mundo().montar()
        mundo.uow.competitions.find_by_id_for_update = AsyncMock(
            wraps=mundo.uow.competitions.find_by_id_for_update
        )

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.otro)

        mundo.uow.competitions.find_by_id_for_update.assert_not_awaited()

    async def test_change_tee_rechecks_who_can_after_the_lock(self):
        """
        Given la jugadora, con la competición abierta al leerla y ya en curso al
            bloquearla
        When cambia sus barras
        Then 403: con la competición en curso ella ya no puede
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        en_curso = await mundo.uow.competitions.find_by_id(mundo.competition_id)
        en_curso.start()
        mundo.uow.competitions.find_by_id_for_update = AsyncMock(return_value=en_curso)
        mundo.uow.competitions.find_by_id = AsyncMock(
            side_effect=lambda _id: _abierta(mundo, en_curso)
        )

        with pytest.raises(NotCompetitionCreatorError):
            await mundo.cambiar(TeeColor.RED)


def _abierta(mundo, en_curso):
    """Una copia de la competición antes de empezar."""
    import copy

    abierta = copy.deepcopy(en_curso)
    abierta._status = CompetitionStatus.CLOSED
    return abierta

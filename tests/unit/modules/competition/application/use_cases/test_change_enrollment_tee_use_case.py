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

Siempre que el jugador no tenga aún partido ni partida generados (su hándicap
de juego ya salió de esas barras), y con la inscripción aprobada. Un capitán
de otro equipo o un jugador cualquiera: 403, sin decir antes nada del estado.
Sin equipos formados (stroke play, o antes del reparto) no hay capitanes.

Qué barras: valoradas para su género o sin género en alguno de los campos; en
SCRATCH también las que solo tienen tarjeta (sin golpes no hace falta
valoración). Sin género en el perfil (o sin usuario), basta con que el color
exista. Sin barras (null) vuelve a las habituales de su género.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentTeeRequestDTO,
)
from src.modules.competition.application.exceptions import (
    EnrollmentNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.change_enrollment_tee_use_case import (
    ChangeEnrollmentTeeUseCase,
    EnrollmentNotApprovedError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    PlayerHasMatchesError,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import TeamAssignmentMode
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
)

pytestmark = pytest.mark.asyncio

VALORADA = "valorada"
SOLO_TARJETA = "solo tarjeta"
NI_UNA_NI_OTRA = "ni valorada ni con tarjeta"


def _tarjeta():
    hoyos = []
    for i in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = i
        hoyo.par = 4
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
        tee.slope_rating = 128 if como == VALORADA else 0
        tee.holes = _tarjeta() if como == SOLO_TARJETA else []
        tee.par_total = 72
        tees.append(tee)
    campo = MagicMock()
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

    def poner(self, user_id, genero):
        usuario = MagicMock()
        usuario.id = user_id
        usuario.gender = genero
        self.por_id[user_id] = usuario

    def quitar(self, user_id):
        self.por_id.pop(user_id)

    async def find_by_id(self, user_id):
        return self.por_id.get(user_id)


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

    async def montar(self, campos=(ALDEAMAYOR,), play_mode="HANDICAP"):
        creada = await create_competition(self.uow, self.organizador, play_mode=play_mode)
        self.competition_id = CompetitionId(creada.id)
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
            self.inscripciones[jugador] = await create_approved_enrollment(
                self.uow, creada.id, jugador
            )
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
            self.uow, golf_course_repository=self.campos, user_repository=self.usuarios
        )

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

    async def ronda(self) -> Round:
        ronda = Round.create(
            competition_id=self.competition_id,
            golf_course_id=next(iter(self.campos.por_id)),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with self.uow:
            await self.uow.rounds.add(ronda)
            await self.uow.commit()
        return ronda

    async def partido_con(self, *jugadores: UserId):
        ronda = await self.ronda()
        a, b = (
            MatchPlayer.create(
                user_id=j,
                playing_handicap=10,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
                strokes_received=[],
            )
            for j in jugadores
        )
        partido = Match.create(
            round_id=ronda.id, match_number=1, team_a_players=[a], team_b_players=[b]
        )
        async with self.uow:
            await self.uow.matches.add(partido)
            await self.uow.commit()

    async def partida_con(self, jugador: UserId):
        ronda = await self.ronda()
        partida = Partida.crear(
            self.competition_id,
            ronda.id,
            1,
            [
                JugadorDePartida(
                    user_id=jugador,
                    handicap=Decimal("20"),
                    playing_handicap=18,
                    tee_color=TeeColor.RED,
                    tee_gender=Gender.FEMALE,
                    golpes_por_hoyo=(1,) * 18,
                    par_por_hoyo=(4,) * 18,
                )
            ],
        )
        async with self.uow:
            await self.uow.partidas.anadir([partida])
            await self.uow.commit()

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

    async def test_change_tee_in_progress_with_a_match_generated_is_rejected(self):
        """
        Given la competición en curso y la jugadora con su partido ya generado
        When el organizador intenta cambiar sus barras
        Then no se puede (409): su hándicap de juego ya salió de ellas
        """
        mundo = await (await _Mundo().montar()).con_equipos()
        await mundo.empezar()
        await mundo.partido_con(mundo.jugadora, mundo.otro)

        with pytest.raises(PlayerHasMatchesError):
            await mundo.cambiar(TeeColor.RED, quien=mundo.organizador)

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

    async def test_change_tee_of_a_player_without_gender_needs_the_colour_for_someone(self):
        """
        Given un jugador sin género en su perfil
        When elige rojas, que solo existen de mujer
        Then valen: el aviso de género lo verá el organizador al generar
        """
        mundo = await _Mundo().montar()
        mundo.usuarios.poner(mundo.jugadora, None)

        await mundo.cambiar(TeeColor.RED)

        assert await mundo.barras_guardadas() == TeeColor.RED

    async def test_change_tee_of_a_player_without_gender_rejects_a_missing_colour(self):
        """
        Given un jugador sin género en su perfil
        When elige negras, que el campo no tiene
        Then se rechaza
        """
        mundo = await _Mundo().montar()
        mundo.usuarios.poner(mundo.jugadora, None)

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.BLACK)

    async def test_change_tee_of_an_unknown_user_is_treated_as_without_gender(self):
        """
        Given una inscripción cuyo usuario ya no se encuentra
        When el organizador elige rojas, que solo existen de mujer
        Then valen, como sin género
        """
        mundo = await _Mundo().montar()
        mundo.usuarios.quitar(mundo.jugadora)

        await mundo.cambiar(TeeColor.RED, quien=mundo.organizador)

        assert await mundo.barras_guardadas() == TeeColor.RED

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

    async def test_change_tee_with_a_ryder_match_generated_is_rejected(self):
        """
        Given una jugadora con un partido de Ryder ya generado
        When intenta cambiar sus barras
        Then no se puede (409 PLAYER_HAS_MATCHES)
        """
        mundo = await _Mundo().montar()
        await mundo.partido_con(mundo.jugadora, mundo.otro)

        with pytest.raises(PlayerHasMatchesError) as error:
            await mundo.cambiar(TeeColor.BLUE)

        assert error.value.error_code == "PLAYER_HAS_MATCHES"

    async def test_change_tee_with_a_tee_group_generated_is_rejected(self):
        """
        Given una jugadora con una partida de stroke play ya generada
        When intenta cambiar sus barras
        Then no se puede
        """
        mundo = await _Mundo().montar()
        await mundo.partida_con(mundo.jugadora)

        with pytest.raises(PlayerHasMatchesError):
            await mundo.cambiar(TeeColor.BLUE)

    async def test_change_tee_with_matches_of_others_only_saves_it(self):
        """
        Given partidos generados en los que ella no juega
        When cambia sus barras
        Then se guardan: lo que cuenta es SU partido
        """
        mundo = await _Mundo().montar()
        await mundo.partido_con(mundo.otro, UserId(uuid4()))

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

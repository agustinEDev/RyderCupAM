"""
Cambiar las barras de una inscripción (BE #912, decidido el 20 nov 2026).

Una jugadora invitada se quedaba en amarillas en un campo sin amarillas de
mujer, y nadie podía cambiárselas: la generación se bloqueaba para siempre.
Ahora las cambian el propio jugador y el organizador, mientras no tenga partido
ni partida generados (su hándicap de juego ya se calculó con esas barras).

| #  | Caso                                                         | Resultado                    |
|----|--------------------------------------------------------------|------------------------------|
| C1 | El propio jugador cambia las suyas                            | Guardadas                    |
| C2 | El organizador cambia las de un inscrito                      | Guardadas                    |
| C2 | Un admin, sin ser el organizador                              | Guardadas                    |
| C3 | Otro jugador                                                  | NotCompetitionCreatorError   |
| C4 | Un color sin valorar para su género en ningún campo           | TeeNotAvailableError         |
| C4 | Valorado en el segundo campo, no en el primero                | Guardadas                    |
| C4 | Mixto (sin género)                                            | Guardadas                    |
| C4 | Jugador sin género: vale si el color existe para alguno       | Guardadas                    |
| C5 | Sin barras (null)                                             | Vuelve a las de por defecto  |
| C6 | Competición en curso, terminada o cancelada                   | TeeChangeClosedError         |
| C7 | Ya tiene partido de Ryder generado                            | PlayerHasMatchesError        |
| C7 | Ya tiene partida (grupo de salida) generada                   | PlayerHasMatchesError        |
| C7 | Hay partidos, pero no suyos                                   | Guardadas                    |
| C8 | La inscripción no está aprobada                               | EnrollmentNotApprovedError   |
| C9 | El organizador no juega y cambia la de otro                   | Guardadas                    |
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
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
    PlayerHasMatchesError,
    TeeChangeClosedError,
    TeeNotAvailableError,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
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
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


def _campo(barras):
    """Un campo con esas barras valoradas —(color, sexo)— y 18 hoyos."""
    tees = []
    for color, sexo in barras:
        tee = MagicMock()
        tee.color = color
        tee.gender = sexo
        tee.course_rating = Decimal("71.2")
        tee.slope_rating = 128
        tees.append(tee)
    hoyos = []
    for i in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = i
        hoyo.par = 4
        hoyo.stroke_index = i
        hoyos.append(hoyo)
    campo = MagicMock()
    campo.tees = tees
    campo.reference_card = hoyos
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

    async def find_by_id(self, user_id):
        return self.por_id.get(user_id)


# Aldeamayor: amarillas de hombre y azules y rojas de mujer
ALDEAMAYOR = [
    (TeeColor.YELLOW, Gender.MALE),
    (TeeColor.BLUE, Gender.FEMALE),
    (TeeColor.RED, Gender.FEMALE),
]


class _Mundo:
    """Una competición abierta en Aldeamayor, su organizador y una jugadora inscrita."""

    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.campos = _Campos()
        self.usuarios = _Usuarios()
        self.organizador = UserId(uuid4())
        self.jugadora = UserId(uuid4())
        self.otro = UserId(uuid4())
        self.usuarios.poner(self.organizador, Gender.MALE)
        self.usuarios.poner(self.jugadora, Gender.FEMALE)
        self.usuarios.poner(self.otro, Gender.MALE)

    async def montar(self, campos=(ALDEAMAYOR,)):
        creada = await create_competition(self.uow, self.organizador)
        self.competition_id = CompetitionId(creada.id)
        async with self.uow:
            competicion = await self.uow.competitions.find_by_id(self.competition_id)
            for barras in campos:
                campo_id = GolfCourseId(uuid4())
                self.campos.por_id[campo_id] = _campo(barras)
                competicion.add_golf_course(campo_id, CountryCode("ES"))
            await self.uow.competitions.update(competicion)
            await self.uow.commit()
        self.inscripcion = await create_approved_enrollment(self.uow, creada.id, self.jugadora)
        await create_approved_enrollment(self.uow, creada.id, self.otro)
        return self

    def caso(self) -> ChangeEnrollmentTeeUseCase:
        return ChangeEnrollmentTeeUseCase(
            self.uow, golf_course_repository=self.campos, user_repository=self.usuarios
        )

    async def cambiar(self, color, quien=None, is_admin=False, inscripcion=None):
        return await self.caso().execute(
            ChangeEnrollmentTeeRequestDTO(
                enrollment_id=(inscripcion or self.inscripcion).id.value, tee_color=color
            ),
            quien or self.jugadora,
            is_admin=is_admin,
        )

    async def barras_guardadas(self, inscripcion=None):
        guardada = await self.uow.enrollments.find_by_id((inscripcion or self.inscripcion).id)
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


class TestQuienPuede:
    async def test_change_tee_by_the_player_saves_it(self):
        """
        Given una jugadora inscrita en una competición abierta en Aldeamayor
        When cambia sus barras a azules (valoradas para mujer)
        Then quedan guardadas (C1)
        """
        mundo = await _Mundo().montar()

        respuesta = await mundo.cambiar(TeeColor.BLUE)

        assert respuesta.tee_color == "BLUE"
        assert await mundo.barras_guardadas() == TeeColor.BLUE

    async def test_change_tee_by_the_organizer_saves_it(self):
        """
        Given una jugadora inscrita
        When el organizador le cambia las barras
        Then quedan guardadas (C2), aunque él no juegue con barras propias (C9)
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

    async def test_change_tee_by_another_player_is_forbidden(self):
        """
        Given una jugadora inscrita
        When otro jugador intenta cambiarle las barras
        Then no puede (C3) y se quedan como estaban
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


class TestQueBarras:
    async def test_change_tee_to_one_not_rated_for_her_gender_is_rejected(self):
        """
        Given Aldeamayor, sin amarillas de mujer
        When la jugadora elige amarillas
        Then se rechaza (C4) y se quedan como estaban
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
        Then valen: basta con alguno de los campos (C4)
        """
        mundo = await _Mundo().montar(campos=(ALDEAMAYOR, [(TeeColor.YELLOW, Gender.FEMALE)]))

        await mundo.cambiar(TeeColor.YELLOW)

        assert await mundo.barras_guardadas() == TeeColor.YELLOW

    async def test_change_tee_to_a_mixed_one_saves_it(self):
        """
        Given un campo con blancas sin género
        When la jugadora elige blancas
        Then valen (C4: valoradas sin género)
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
        Then se rechaza (C4)
        """
        mundo = await _Mundo().montar()
        mundo.usuarios.poner(mundo.jugadora, None)

        with pytest.raises(TeeNotAvailableError):
            await mundo.cambiar(TeeColor.BLACK)

    async def test_change_tee_to_none_goes_back_to_the_default(self):
        """
        Given una jugadora que eligió azules
        When pide volver a las de por defecto (null)
        Then se quedan sin elegir, y juega desde las habituales de su género (C5)
        """
        mundo = await _Mundo().montar()
        await mundo.cambiar(TeeColor.BLUE)

        respuesta = await mundo.cambiar(None)

        assert respuesta.tee_color is None
        assert await mundo.barras_guardadas() is None


class TestCuando:
    @pytest.mark.parametrize("estado", ["IN_PROGRESS", "COMPLETED", "CANCELLED"])
    async def test_change_tee_once_the_competition_started_is_closed(self, estado):
        """
        Given una competición en curso, terminada o cancelada
        When la jugadora intenta cambiar sus barras
        Then ya no se puede (C6)
        """
        mundo = await _Mundo().montar()
        await set_competition_status(mundo.uow, mundo.competition_id.value, estado)

        with pytest.raises(TeeChangeClosedError) as error:
            await mundo.cambiar(TeeColor.BLUE)

        assert error.value.error_code == "TEE_CHANGE_CLOSED"

    async def test_change_tee_with_the_competition_closed_saves_it(self):
        """
        Given una competición con las inscripciones cerradas, sin partidos
        When la jugadora cambia sus barras
        Then se guardan: aún no se ha calculado nada con ellas
        """
        mundo = await _Mundo().montar()
        await set_competition_status(mundo.uow, mundo.competition_id.value, "CLOSED")

        await mundo.cambiar(TeeColor.BLUE)

        assert await mundo.barras_guardadas() == TeeColor.BLUE

    async def test_change_tee_with_a_ryder_match_generated_is_rejected(self):
        """
        Given una jugadora con un partido de Ryder ya generado
        When intenta cambiar sus barras
        Then no se puede (C7): su hándicap de juego ya salió de ellas
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
        Then no se puede (C7)
        """
        mundo = await _Mundo().montar()
        await mundo.partida_con(mundo.jugadora)

        with pytest.raises(PlayerHasMatchesError):
            await mundo.cambiar(TeeColor.BLUE)

    async def test_change_tee_with_matches_of_others_only_saves_it(self):
        """
        Given partidos generados en los que ella no juega
        When cambia sus barras
        Then se guardan: lo que cuenta es SU partido (C7)
        """
        mundo = await _Mundo().montar()
        await mundo.partido_con(mundo.otro, UserId(uuid4()))

        await mundo.cambiar(TeeColor.BLUE)

        assert await mundo.barras_guardadas() == TeeColor.BLUE

    async def test_change_tee_of_a_withdrawn_enrollment_is_rejected(self):
        """
        Given una inscripción retirada
        When se intentan cambiar sus barras
        Then no se puede (C8)
        """
        mundo = await _Mundo().montar()
        async with mundo.uow:
            inscripcion = await mundo.uow.enrollments.find_by_id(
                EnrollmentId(mundo.inscripcion.id.value)
            )
            inscripcion.withdraw()
            await mundo.uow.enrollments.update(inscripcion)
            await mundo.uow.commit()

        with pytest.raises(EnrollmentNotApprovedError) as error:
            await mundo.cambiar(TeeColor.BLUE)

        assert error.value.error_code == "ENROLLMENT_NOT_APPROVED"

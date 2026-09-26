"""Helper factories para tests de use cases de Enrollment/Handicap."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


class UsuariosConGenero:
    """Todos con género, salvo los que se digan (#710: crear exige el del organizador)."""

    def __init__(self, sin_genero=()):
        self._sin_genero = set(sin_genero)

    async def find_by_id(self, user_id):
        genero = None if user_id in self._sin_genero else Gender.MALE
        return SimpleNamespace(id=user_id, gender=genero)


USUARIOS_CON_GENERO = UsuariosConGenero()


async def create_competition(
    uow: InMemoryUnitOfWork, creator_id: UserId, enrollment_opens_days_before: int | None = None
):
    """Crea una competición.

    Sin días de apertura nace con las inscripciones abiertas (BE #332). Con
    ellos espera en DRAFT, que es la única forma de tener hoy un borrador.
    """
    create_uc = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO)
    request = CreateCompetitionRequestDTO(
        name="Test Cup",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        main_country="ES",
        play_mode="SCRATCH",
        max_players=24,
        enrollment_opens_days_before=enrollment_opens_days_before,
    )
    return await create_uc.execute(request, creator_id)


async def set_competition_status(uow: InMemoryUnitOfWork, competition_id, status: str):
    """Mueve una competición a través de sus transiciones hasta `status`."""
    async with uow:
        competition = await uow.competitions.find_by_id(CompetitionId(competition_id))
        # Desde BE #332 nace ya ACTIVE si no lleva apertura programada, asi que
        # solo hay que abrirla cuando todavia esta esperando su hora
        if status == "DRAFT":
            raise ValueError(
                "Una competicion creada sin apertura programada ya nace ACTIVE "
                "(BE #332), y de ahi no se vuelve. Para un borrador, creala con "
                "`create_competition(uow, creator_id, enrollment_opens_days_before=5)`. "
                "Dejarlo pasar devolveria una abierta y el test afirmaria contra "
                "el estado que no es."
            )
        if competition.is_draft():
            competition.activate()
        if status in ("CLOSED", "IN_PROGRESS", "COMPLETED"):
            competition.close_enrollments()
        if status in ("IN_PROGRESS", "COMPLETED"):
            competition.start()
        if status == "COMPLETED":
            competition.complete()
        if status == "CANCELLED":
            competition.cancel()
        await uow.competitions.update(competition)
        await uow.commit()


async def create_approved_enrollment(
    uow: InMemoryUnitOfWork,
    competition_id,
    user_id: UserId,
    custom_handicap: Decimal | None = None,
) -> Enrollment:
    """Crea un enrollment ya aprobado, opcionalmente con hándicap personalizado."""
    enrollment = Enrollment.direct_enroll(
        id=EnrollmentId.generate(),
        competition_id=CompetitionId(competition_id),
        user_id=user_id,
        custom_handicap=custom_handicap,
    )
    async with uow:
        await uow.enrollments.add(enrollment)
        await uow.commit()
    return enrollment


# Hasta dónde llegó a jugarse un calendario (BE #347). El orden importa poco;
# lo que cuenta es que «empezado» y «sin jugar» NO son jugar, y el resto sí
COMO_SE_JUGO = (
    "sin jugar",
    "empezado",
    "golpe propio",
    "golpe del marcador",
    "raya",
    "walkover",
    "concedido",
    "terminado",
)


def _jugador() -> MatchPlayer:
    return MatchPlayer.create(
        user_id=UserId.generate(),
        playing_handicap=10,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        strokes_received=[],
    )


async def montar_calendario(uow: InMemoryUnitOfWork, competition_id, como: str) -> None:
    """Cuelga de la competición una ronda con un partido jugado hasta `como`.

    «empezado» deja las tarjetas creadas y VACÍAS, que es lo que hace de verdad
    empezar un partido (`match_opener`): tener filas no es haber anotado nada.
    """
    if como not in COMO_SE_JUGO:
        raise ValueError(f"no sé montar un calendario «{como}»")
    if not isinstance(competition_id, CompetitionId):
        competition_id = CompetitionId(competition_id)
    ronda = Round.create(
        competition_id=competition_id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=date(2030, 6, 1),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    a, b = _jugador(), _jugador()
    partido = Match.create(
        round_id=ronda.id, match_number=1, team_a_players=[a], team_b_players=[b]
    )
    tarjetas = []
    if como == "walkover":
        partido.declare_walkover("A")
    elif como != "sin jugar":
        partido.start()
        tarjetas = [
            HoleScore.create(
                match_id=partido.id,
                hole_number=hoyo,
                player_user_id=jugador.user_id,
                team=equipo,
                strokes_received=0,
            )
            for hoyo in range(1, 19)
            for jugador, equipo in ((a, "A"), (b, "B"))
        ]
        if como == "golpe propio":
            tarjetas[0].set_own_score(4)
        if como == "golpe del marcador":
            tarjetas[0].set_marker_score(4)
        if como == "raya":
            # Bola levantada: se envía sin número, y es un hoyo jugado
            tarjetas[0].set_own_score(None)
        if como == "concedido":
            # Sin un solo golpe: se concede antes de empezar a anotar
            partido.concede("B")
        if como == "terminado":
            partido.complete({"winner": "A", "score": "1UP"})
    async with uow:
        await uow.rounds.add(ronda)
        await uow.matches.add(partido)
        await uow.hole_scores.add_many(tarjetas)
        await uow.commit()

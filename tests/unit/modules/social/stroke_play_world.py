"""
Un torneo de stroke play (grupos de salida) montado en memoria, para los tests
del bloque L: logros, historial de campos y estadisticas.

Lo comparten los tests de `social` y de `user` porque los tres miran las mismas
tarjetas: si cada uno montara la suya, una regla nueva (que tarjeta cuenta) se
probaria con datos distintos en cada sitio.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.marcadores_en_cadena import MarcadoresEnCadena
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.entities.user import User
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode

PAR = 4
DIA = date(2026, 6, 1)
MOMENTO = datetime(2026, 6, 1, 10, 0)


def tarjeta(par: int = PAR, **cambios: int | None) -> dict[int, int | None]:
    """Los 18 hoyos al par, con los cambios que se digan: `tarjeta(h4=3)`."""
    golpes: dict[int, int | None] = dict.fromkeys(range(1, 19), par)
    for clave, valor in cambios.items():
        golpes[int(clave.removeprefix("h"))] = valor
    return golpes


class StrokePlayWorld:
    """Usuarios, campos, torneos, rondas y grupos de stroke play en memoria."""

    def __init__(self, competition_uow, golf_course_uow, user_uow):
        self.comp = competition_uow
        self.golf = golf_course_uow
        self.users = user_uow

    async def user(self, *, share_activity: bool = True, handicap: float | None = None) -> User:
        user = User.create(
            first_name="Stroke",
            last_name="Player",
            email_str=f"sp_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        if not share_activity:
            user.set_activity_sharing(False)
        if handicap is not None:
            user.update_handicap(handicap)
        async with self.users:
            await self.users.users.save(user)
        return user

    async def course(self, creator: User, *, pars: dict[int, int] | None = None) -> GolfCourse:
        pars = pars or {}
        course = GolfCourse.create(
            name=f"Stroke Club {uuid4().hex[:4]}",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator.id,
            tees=[
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    identifier="Yellow",
                    course_rating=70.0,
                    slope_rating=125,
                ),
            ],
            holes=[Hole(number=i, par=pars.get(i, PAR), stroke_index=i) for i in range(1, 19)],
        )
        course.approve()
        async with self.golf:
            await self.golf.golf_courses.save(course)
        return course

    async def competition(
        self,
        creator: User,
        *,
        tipo: TournamentType = TournamentType.STABLEFORD,
        completed: bool = True,
        play_mode: PlayMode = PlayMode.HANDICAP,
        enrolled: list[User] | None = None,
    ) -> Competition:
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator.id,
            name=CompetitionName("Medal de Otoño"),
            dates=DateRange(start_date=DIA, end_date=DIA + timedelta(days=2)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=play_mode,
            tournament_type=tipo,
        )
        competition.activate()
        competition.close_enrollments(total_enrollments=len(enrolled or []))
        competition.start()
        if completed:
            competition.complete()
        async with self.comp:
            await self.comp.competitions.add(competition)
            for jugador in enrolled or []:
                await self.comp.enrollments.add(
                    Enrollment.direct_enroll(
                        id=EnrollmentId(uuid4()),
                        competition_id=competition.id,
                        user_id=jugador.id,
                    )
                )
        return competition

    async def save_competition(self, competition: Competition) -> None:
        async with self.comp:
            await self.comp.competitions.update(competition)

    async def round(self, competition: Competition, course: GolfCourse, dia: date = DIA) -> Round:
        round_ = Round.create(
            competition_id=competition.id,
            golf_course_id=course.id,
            round_date=dia,
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with self.comp:
            await self.comp.rounds.add(round_)
        return round_

    async def group(
        self,
        competition: Competition,
        round_: Round,
        golpes: dict[User, dict[int, int | None]],
        *,
        estados: dict[User, EstadoDeTarjeta] | None = None,
        estado: EstadoPartida = EstadoPartida.COMPLETED,
        sin_validar: dict[User, dict[int, int]] | None = None,
        pars: dict[int, int] | None = None,
        handicap: Decimal = Decimal("10"),
        numero: int = 1,
    ) -> Partida:
        """
        `golpes[user]`: sus hoyos VALIDADOS (jugador y marcador coinciden; None
        es una raya). `sin_validar[user]`: hoyos en los que el marcador apunto
        otra cosa, asi que no estan validados.
        """
        pars = pars or {}
        cerradas = estados or {}

        def foto(user: User) -> JugadorDePartida:
            return JugadorDePartida(
                user_id=user.id,
                handicap=handicap,
                playing_handicap=0,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
                golpes_por_hoyo=(0,) * 18,
                par_por_hoyo=tuple(pars.get(i, PAR) for i in range(1, 19)),
            )

        quedan = [u.id for u in golpes if not (u in cerradas and cerradas[u].fuera_de_la_partida())]
        partida = Partida(
            id=PartidaId.generate(),
            competition_id=competition.id,
            round_id=round_.id,
            numero=numero,
            jugadores=[foto(u) for u in golpes],
            marcadores=MarcadoresEnCadena.de(quedan) if len(quedan) > 1 else {},
            estado=estado,
            estados_de_tarjeta={u.id: cerradas.get(u, EstadoDeTarjeta.ENTREGADA) for u in golpes},
        )
        async with self.comp:
            await self.comp.partidas.anadir([partida])
            for user, suyos in golpes.items():
                for hoyo, valor in suyos.items():
                    golpe = GolpeDePartida.crear(
                        partida.id, round_.id, competition.id, user.id, hoyo, MOMENTO
                    )
                    golpe.anotar_propio(valor, True, user.id, MOMENTO)
                    golpe.anotar_del_marcador(valor, True, user.id, MOMENTO)
                    await self.comp.golpes_de_partida.guardar(golpe)
            for user, hoyos in (sin_validar or {}).items():
                for hoyo, valor in hoyos.items():
                    golpe = GolpeDePartida.crear(
                        partida.id, round_.id, competition.id, user.id, hoyo, MOMENTO
                    )
                    golpe.anotar_propio(valor, True, user.id, MOMENTO)
                    golpe.anotar_del_marcador(valor + 1, True, user.id, MOMENTO)
                    await self.comp.golpes_de_partida.guardar(golpe)
        return partida

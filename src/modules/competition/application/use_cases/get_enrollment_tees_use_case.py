"""
Caso de Uso: las barras de una inscripción, campo a campo (barras por campo, 20 nov 2026).

El front no conoce el género de los demás inscritos, así que al organizador o al
capitán el selector no podía saber qué ofrecer. Decidido con Agustín: lo calcula
el back, con la MISMA regla que los cambios (`BarrasDeLaInscripcion`). Por cada
campo de la competición: la barra que juega (su cambio propio, la del campo para
su género o su general, si ese campo la tiene para él; si no, ninguna), de dónde
sale y las que se le pueden fijar. Además, su barra general y la habitual de su
género.

Con la competición terminada o cancelada (tabla del 21 nov 2026, B), en cada campo
donde jugó, la barra de la foto de su partido (Ryder) o su partida (stroke play), de
la última ronda allí por fecha y sesión, con origen PLAYED. Solo si jugó de verdad
(decidido el 21 nov 2026): en la Ryder, su partido empezó (un WO cuenta solo con
algún hoyo apuntado: el que se declara sin empezar, no); en stroke play, está en
`quienes_jugaron` de su partida (no un NO_PRESENTADO). Donde no, la configuración de
siempre. Ya no se cambia nada: sin
opciones en ningún campo.

Quién: el propio jugador, el capitán de su equipo, el organizador o un admin, en
cualquier estado de la competición (consultar es una lectura); comprobado antes
de mirar nada más. Es una lectura: no bloquea nada. No devuelve el género del jugador,
pero las opciones (barras de un género o mixtas) lo dejan ver a quien puede
cambiar sus barras: por eso solo las ven ellos.
"""

from typing import Literal
from uuid import UUID

from src.modules.competition.application.dto.enrollment_dto import (
    CourseTeesDTO,
    EnrollmentTeesResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    EnrollmentNotApprovedError,
    EnrollmentNotFoundError,
)
from src.modules.competition.application.services.barras_de_la_inscripcion import (
    BarrasDeLaInscripcion,
)
from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.application.services.envelope_desk import ORDEN_DE_SESION
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.barra_del_jugador import barras_por_defecto
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.services.stroke_context import StrokeContext
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

# Ya no se juega ni se cambia nada: cada campo dice la barra que jugó (B)
ACABADA = frozenset({CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED})
# Un partido en estos estados empezó: se jugó en el campo (el WO se mira aparte)
SE_JUGO = frozenset({MatchStatus.IN_PROGRESS, MatchStatus.COMPLETED, MatchStatus.CONCEDED})


class GetEnrollmentTeesUseCase:
    """
    Las barras que el propio jugador (antes de empezar), el capitán de su equipo, el
    organizador o un admin pueden elegir para una inscripción.
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
    ):
        self._uow = uow
        self._campos = golf_course_repository
        self._usuarios = user_repository
        self._reglas = BarrasDeLaInscripcion(uow, golf_course_repository)
        self._contextos: dict[GolfCourseId, StrokeContext] = {}

    async def execute(
        self, enrollment_id: UUID, quien: UserId, is_admin: bool = False
    ) -> EnrollmentTeesResponseDTO:
        """
        Las barras que valen, las de por defecto y las elegidas.

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            CompetitionNotFoundError: Si su competición no existe
            NotCompetitionCreatorError: Si no es el jugador, el capitán de su equipo, el
                organizador ni un admin
            EnrollmentNotApprovedError: Si la inscripción no está aprobada
        """
        async with self._uow:
            enrollment = await self._uow.enrollments.find_by_id(EnrollmentId(enrollment_id))
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {enrollment_id}")
            competition = await self._uow.competitions.find_by_id(enrollment.competition_id)
            if competition is None:
                raise CompetitionNotFoundError(
                    f"Competición no encontrada: {enrollment.competition_id}"
                )
            # Primero quién: a quien no puede no se le dice nada más. Consultar es
            # una lectura: vale en cualquier estado (la competición cerrada no
            # cambia lo que juega cada uno), y el propio jugador puede siempre
            await self._reglas.comprobar_quien_consulta(competition, enrollment, quien, is_admin)
            if not enrollment.is_approved():
                raise EnrollmentNotApprovedError("La inscripción no está aprobada")
            usuario = await self._usuarios.find_by_id(enrollment.user_id)
            genero = usuario.gender if usuario else None
            acabada = competition.status in ACABADA
            jugadas = await self._jugadas(competition, enrollment.user_id) if acabada else {}
            campos = [
                CourseTeesDTO(
                    golf_course_id=del_campo.golf_course_id.value,
                    golf_course_name=await self._nombre(del_campo.golf_course_id),
                    tee=jugadas[del_campo.golf_course_id].value,
                    source="PLAYED",
                    options=[],
                )
                if del_campo.golf_course_id in jugadas
                else await self._campo(
                    competition,
                    del_campo.golf_course_id,
                    enrollment.user_id,
                    enrollment.tee_color,
                    genero,
                    con_opciones=not acabada,
                )
                for del_campo in competition.golf_courses
            ]

        return EnrollmentTeesResponseDTO(
            general_tee=enrollment.tee_color.value if enrollment.tee_color else None,
            # Sin usuario no se sabe cuál tendría
            default_tee=barras_por_defecto(genero).value if usuario else None,
            courses=campos,
        )

    async def _jugadas(
        self, competition: Competition, user_id: UserId
    ) -> dict[GolfCourseId, TeeColor]:
        """
        La barra que jugó en cada campo: la de la foto de su partido (Ryder) o su
        partida (stroke play) donde jugó de verdad, de la última ronda en ese campo
        por fecha y sesión. Los campos donde no llegó a jugar no salen.
        """
        rondas = {r.id: r for r in await self._uow.rounds.find_by_competition(competition.id)}
        partidos = await self._uow.matches.find_by_rounds_for_player(list(rondas), user_id)
        # Un WO no dice si empezó: cuenta si alguien apuntó algún hoyo
        con_hoyos = {
            match_id
            for match_id, _ in await self._uow.hole_scores.played_holes(
                [p.id for p in partidos if p.status == MatchStatus.WALKOVER]
            )
        }
        fotos = [
            (partido.round_id, jugador.tee_color)
            for partido in partidos
            if (partido.status in SE_JUGO or partido.id in con_hoyos)
            and (jugador := partido.find_player(user_id)) is not None
        ]
        partidas = await self._uow.partidas.del_jugador(competition.id, user_id)
        golpes = await self._uow.golpes_de_partida.de_las_partidas([p.id for p in partidas])
        fotos += [
            (partida.round_id, jugador.tee_color)
            for partida in partidas
            if user_id in partida.quienes_jugaron(golpes)
            for jugador in partida.jugadores
            if jugador.user_id == user_id
        ]
        jugadas: dict[GolfCourseId, TeeColor] = {}
        # De la primera a la última: cada una pisa la de antes en su campo
        for round_id, color in sorted(
            ((r, c) for r, c in fotos if r in rondas),
            key=lambda foto: (
                rondas[foto[0]].round_date,
                ORDEN_DE_SESION[rondas[foto[0]].session_type],
            ),
        ):
            jugadas[rondas[round_id].golf_course_id] = color
        return jugadas

    async def _nombre(self, golf_course_id: GolfCourseId) -> str:
        """El nombre del campo, o vacío si ya no existe."""
        campo = await self._campos.find_by_id(golf_course_id)
        return campo.name if campo is not None else ""

    async def _campo(
        self,
        competition: Competition,
        golf_course_id: GolfCourseId,
        user_id: UserId,
        general: TeeColor | None,
        genero: Gender | None,
        con_opciones: bool = True,
    ) -> CourseTeesDTO:
        """
        Lo de un campo: la barra que juega (su cambio propio, la del campo para su
        género o su general, si ese campo la tiene para él), de dónde sale y las
        que se le pueden fijar (`con_opciones`; acabada, ninguna). Un campo que ya
        no existe sale sin opciones.
        """
        campo = await self._campos.find_by_id(golf_course_id)
        if campo is not None and golf_course_id not in self._contextos:
            self._contextos[golf_course_id] = course_context_for(campo)
        cambios = await self._uow.barras_por_campo.del_campo(competition.id, golf_course_id)
        color = cambios.color_de(user_id, general, genero)
        source: Literal["OWN", "COURSE", "GENERAL", "DEFAULT", "NONE"]
        if user_id in cambios.propias:
            source = "OWN"
        elif genero is not None and genero in cambios.por_genero:
            source = "COURSE"
        elif general is not None:
            source = "GENERAL"
        else:
            # Ni cambios ni barra general: la habitual de su género
            source = "DEFAULT"
        # La habitual de su género si no tiene ninguna: la que jugaría
        jugaria = color or barras_por_defecto(genero)
        valida = await self._reglas.vale_en_el_campo(
            competition, golf_course_id, jugaria, genero, self._contextos
        )
        opciones = (
            await self._reglas.las_que_valen_en_el_campo(
                competition, golf_course_id, genero, self._contextos
            )
            if con_opciones
            else []
        )
        return CourseTeesDTO(
            golf_course_id=golf_course_id.value,
            golf_course_name=campo.name if campo is not None else "",
            tee=jugaria.value if valida else None,
            source=source if valida else "NONE",
            options=[c.value for c in opciones],
        )

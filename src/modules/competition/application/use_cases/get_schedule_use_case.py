"""Caso de Uso: Obtener Schedule de la competición."""

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from src.modules.competition.application.dto.match_generation_block_dto import block_to_dto
from src.modules.competition.application.dto.round_match_dto import (
    GetScheduleRequestDTO,
    GetScheduleResponseDTO,
    MatchPlayerResponseDTO,
    MatchResponseDTO,
    RoundResponseDTO,
    ScheduleDayDTO,
    TeamAssignmentResponseDTO,
    TeeSheetResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
)
from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    Acceso,
    LoJugadoQueVe,
    con_la_llave,
)
from src.modules.competition.application.services.quien_ve_los_inscritos import (
    LoQueVe,
    alcance_de,
    lo_que_ve,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_opening_service import (
    ScoringOpeningService,
)
from src.modules.competition.domain.services.zona_horaria import zona_del_campo
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId

if TYPE_CHECKING:
    # Solo para el tipo: la mesa de sobres llega hasta aquí por el generador de
    # partidos, e importarla de verdad cierra un círculo
    from src.modules.competition.application.services.envelope_desk import EnvelopeDesk


def _jugadores(match: Match) -> list[UserId]:
    """Los de los dos lados de un partido."""
    return [p.user_id for p in (*match.team_a_players, *match.team_b_players)]


def _descansan(team_assignment, inscritos: set[UserId], matches: list) -> list[UserId]:
    """Los inscritos de los equipos que no juegan ningún partido de la sesión (#710).

    Con equipos desiguales el que sobra se quedaba sin partido y nadie lo decía.
    Sin partidos todavía no se sabe quién juega, así que nadie descansa aún.
    """
    if not team_assignment or not matches:
        return []
    juegan = {p.user_id for m in matches for p in [*m.team_a_players, *m.team_b_players]}
    return [
        uid
        for uid in [*team_assignment.team_a_player_ids, *team_assignment.team_b_player_ids]
        if uid in inscritos and uid not in juegan
    ]


class GetScheduleUseCase:
    """
    Caso de uso para obtener el schedule completo de una competición.

    Retorna todas las rondas agrupadas por día, con sus partidos
    y la asignación de equipos.

    Accesible por cualquier usuario (lectura).
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repo: IGolfCourseRepository | None = None,
        sobres: "EnvelopeDesk | None" = None,
        amigos: AmigosInterface | None = None,
        eventos: EventosDeAmigosInterface | None = None,
    ):
        self._uow = uow
        # La llave de quien está fuera de una privada: sus partidos, solo los
        # de un amigo con evento en su Actividad (27 oct 2026)
        self._eventos = eventos
        # De quién es amigo quien mira: en las franjas solo ve a sus amigos
        # hasta que se publica (release social 2)
        self._amigos = amigos
        # Mirar la agenda abre los sobres que ya tocan (BE #367), como mirar la
        # página del sobre: si nadie la abría, la sesión llegaba a su hora con
        # los sobres cerrados y, desde la #361, sin partidos
        self._sobres = sobres
        # Para la hora a la que abre la anotacion de cada ronda, que es la LOCAL
        # de SU campo (BE #305). De aqui saca el movil su lista de proximos
        # partidos, asi que sin esto no puede ofrecer «Anotar» sin cobertura
        self._gc_repo = golf_course_repo

    async def execute(
        self,
        request: GetScheduleRequestDTO,
        *,
        viewer_id: UserId | None = None,
        viewer_is_admin: bool = False,
        viewer_email: str | None = None,
    ) -> GetScheduleResponseDTO:
        """
        La agenda. Diciendo quién mira, en cada franja ve solo a quien le deja
        `quien_ve_los_inscritos` (con las plazas ocupadas de verdad); sin
        decirlo, entera: es como la leen los usos internos.
        """
        alcance = None
        async with self._uow:
            # 1. Verificar que la competición existe
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Obtener todas las rondas
            rounds = await self._uow.rounds.find_by_competition(competition_id)
            # Quién tiene plaza en cada franja de un stroke play (#251)
            plazas = await self._uow.plazas.de_la_competicion(competition_id)
            esperas = await self._uow.esperas.de_la_competicion(competition_id)
            await self._abre_los_sobres_que_tocan(competition, rounds)

            # 3. Obtener partidos para cada ronda
            total_matches = 0
            rounds_with_matches: list[tuple] = []
            for round_entity in rounds:
                matches = await self._uow.matches.find_by_round(round_entity.id)
                rounds_with_matches.append((round_entity, matches))
                total_matches += len(matches)

            # 4. Obtener asignación de equipos
            team_assignment = await self._uow.team_assignments.find_by_competition(competition_id)
            # Quién sigue dentro: un retirado no «descansa», no está (#710)
            inscritos = (
                {
                    e.user_id
                    for e in await self._uow.enrollments.find_by_competition_and_status(
                        competition_id, EnrollmentStatus.APPROVED
                    )
                }
                if team_assignment
                else set()
            )
            if viewer_id is not None:
                alcance = await alcance_de(
                    self._uow, competition, viewer_id, es_admin=viewer_is_admin, email=viewer_email
                )

        ve = await lo_que_ve(alcance, viewer_id, self._amigos) if alcance and viewer_id else None
        # En una privada, sus partidos solo los ve quien está dentro (27 oct
        # 2026): ahí `completa` es organizador, admin o aprobado
        jugado = (
            await con_la_llave(
                competition.visibility is not Visibility.PRIVATE or ve.completa,
                competition_id,
                ve.quien,
                self._eventos,
            )
            if ve
            else LoJugadoQueVe(Acceso.ENTERO)
        )
        entero = jugado.acceso is Acceso.ENTERO
        if not entero:
            rounds_with_matches = [
                (r, [m for m in matches if jugado.ve_la_partida(_jugadores(m))])
                for r, matches in rounds_with_matches
            ]
            total_matches = sum(len(matches) for _, matches in rounds_with_matches)

        # 5. La zona horaria de cada campo, una consulta por campo distinto: una
        # competicion juega en uno o dos, no en veinte
        # (y su nombre, para «Mis Próximos Partidos», BE #532)
        zonas_por_campo: dict = {}
        nombres_por_campo: dict[GolfCourseId, str | None] = {}
        if self._gc_repo:
            for round_entity, _ in rounds_with_matches:
                if round_entity.golf_course_id in zonas_por_campo:
                    continue
                golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
                zonas_por_campo[round_entity.golf_course_id] = (
                    golf_course.timezone if golf_course else None
                )
                nombres_por_campo[round_entity.golf_course_id] = (
                    golf_course.name if golf_course else None
                )

        # 6. Agrupar rondas por día
        days_map = defaultdict(list)
        for round_entity, matches in rounds_with_matches:
            match_dtos = [
                MatchResponseDTO(
                    id=m.id.value,
                    round_id=m.round_id.value,
                    match_number=m.match_number,
                    team_a_players=[
                        MatchPlayerResponseDTO.from_domain(p) for p in m.team_a_players
                    ],
                    team_b_players=[
                        MatchPlayerResponseDTO.from_domain(p) for p in m.team_b_players
                    ],
                    status=m.status.value,
                    handicap_strokes_given=m.handicap_strokes_given,
                    strokes_given_to_team=m.strokes_given_to_team,
                    result=m.result,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in matches
            ]

            round_dto = RoundResponseDTO(
                id=round_entity.id.value,
                competition_id=round_entity.competition_id.value,
                golf_course_id=round_entity.golf_course_id.value,
                golf_course_name=nombres_por_campo.get(round_entity.golf_course_id),
                round_date=round_entity.round_date,
                session_type=round_entity.session_type.value,
                # Una franja de stroke play no tiene formato de partido (#541)
                match_format=None
                if round_entity.hoja_de_salidas
                else round_entity.match_format.value,
                status=round_entity.status.value,
                handicap_mode=round_entity.handicap_mode.value
                if round_entity.handicap_mode
                else None,
                allowance_percentage=round_entity.allowance_percentage,
                effective_allowance=round_entity.get_effective_allowance(),
                tee_sheet=_hoja(
                    round_entity.hoja_de_salidas,
                    [p.user_id.value for p in plazas if p.round_id == round_entity.id],
                    [e.user_id.value for e in esperas if e.round_id == round_entity.id],
                    ve,
                ),
                matches=match_dtos,
                scoring_opens_at=_abre(
                    round_entity, zonas_por_campo.get(round_entity.golf_course_id)
                ),
                # El aviso de por qué no hay partidos nombra a jugadores: de una
                # privada, solo para quien está dentro (CodeRabbit)
                match_generation_block=block_to_dto(round_entity.match_generation_block)
                if entero
                else None,
                resting_player_ids=[
                    uid.value for uid in _descansan(team_assignment, inscritos, matches)
                ]
                if entero
                else [],
                created_at=round_entity.created_at,
                updated_at=round_entity.updated_at,
            )
            days_map[round_entity.round_date].append(round_dto)

        # 6. Construir días ordenados (cronológico: MORNING → AFTERNOON → EVENING)
        session_order = {"MORNING": 0, "AFTERNOON": 1, "EVENING": 2}
        days = [
            ScheduleDayDTO(
                date=d,
                rounds=sorted(r, key=lambda x: session_order.get(x.session_type.upper(), 99)),
            )
            for d, r in sorted(days_map.items())
        ]

        # 7. Construir respuesta de team assignment
        ta_dto = None
        if team_assignment and entero:
            ta_dto = TeamAssignmentResponseDTO(
                id=team_assignment.id.value,
                competition_id=team_assignment.competition_id.value,
                mode=team_assignment.mode.value,
                team_a_player_ids=[uid.value for uid in team_assignment.team_a_player_ids],
                team_b_player_ids=[uid.value for uid in team_assignment.team_b_player_ids],
                created_at=team_assignment.created_at,
            )

        # Ya guardado: los avisos de los partidos que haya creado abrir los sobres (G2)
        if self._sobres is not None:
            await self._sobres.avisar_salidas()

        return GetScheduleResponseDTO(
            competition_id=request.competition_id,
            days=days,
            total_rounds=len(rounds),
            total_matches=total_matches,
            team_assignment=ta_dto,
            # Lo que caben en todas las franjas de un stroke play (#251)
            tee_sheet_capacity=(
                sum(r.hoja_de_salidas.cupo for r in rounds if r.hoja_de_salidas is not None)
                if competition.stroke_play is not None
                else None
            ),
        )

    async def _abre_los_sobres_que_tocan(self, competition, rounds) -> None:
        """Abre los sobres vencidos de las sesiones que esperan partidos.

        Solo en modo Ryder, que es donde hay sobres: en el manual, leer la
        agenda no puede ponerse a generar partidos. Y solo las sesiones que
        esperan partidos, porque la agenda la lee mucha más gente que la
        página del sobre: el resto no cuesta ni una consulta.
        """
        if (
            self._sobres is None
            or competition.ryder_cup is None
            or competition.ryder_cup.setup_mode != SetupMode.RYDER_CUP
        ):
            return
        for ronda in rounds:
            if ronda.status != RoundStatus.PENDING_MATCHES:
                continue
            sobres = {s.team: s for s in await self._uow.envelopes.find_by_round(ronda.id)}
            await self._sobres.revelar_si_toca(ronda, competition, sobres)


def _hoja(
    hoja: HojaDeSalidas | None,
    jugadores: list[UUID],
    esperan: list[UUID],
    ve: LoQueVe | None = None,
) -> TeeSheetResponseDTO | None:
    """
    La hoja de salidas de una franja, con sus horas, su cupo y quién va (#251).

    Quien no ve la lista completa ve solo a quien le deja `ve`, pero las plazas
    ocupadas son las de verdad: así le salen bien las libres (release social 2).
    """
    if hoja is None:
        return None
    ocupadas = len(jugadores)
    en_espera = len(esperan)
    mi_puesto = (
        esperan.index(ve.quien.value) + 1 if ve is not None and ve.quien.value in esperan else None
    )
    if ve is not None:
        jugadores = [j for j in jugadores if ve.ve_a(UserId(j))]
        esperan = [j for j in esperan if ve.ve_a(UserId(j))]
    return TeeSheetResponseDTO(
        first_tee_time=hoja.primera_salida,
        last_tee_time=hoja.ultima_salida,
        interval_minutes=hoja.intervalo_minutos,
        group_size=hoja.jugadores_por_partida,
        tee_times=hoja.salidas,
        capacity=hoja.cupo,
        places_taken=ocupadas,
        waiting_count=en_espera,
        my_waiting_position=mi_puesto,
        player_ids=jugadores,
        waiting_ids=esperan,
    )


def _abre(ronda, zona: str | None) -> datetime | None:
    """
    Una franja de stroke play abre a su primera salida, como en su vista de
    anotar (#551); una sesión de Ryder, a la hora de su sesión (BE #305).
    """
    hoja = ronda.hoja_de_salidas
    if hoja is None:
        return ScoringOpeningService.opens_at(ronda.round_date, ronda.session_type, zona)
    campo = zona_del_campo(zona)
    if campo is None or ronda.round_date is None:
        return None
    return datetime.combine(ronda.round_date, hoja.hora_de(1), tzinfo=campo)

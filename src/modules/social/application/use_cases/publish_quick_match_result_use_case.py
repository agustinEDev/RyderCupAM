"""Caso de Uso: Publicar como acabo cada uno una partida rapida (BE-2, bloque D)."""

from dataclasses import dataclass
from decimal import Decimal

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.services.stroke_context import StrokeContextBuilder
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.hole_completion_service import hole_is_complete
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    ParticipantStrokes,
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.social.application.publication import stamp_for_publication
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.services.ranking import rank
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.services.stroke_play_scoring import (
    NET_DOUBLE_BOGEY_OVER_PAR,
    StrokePlayScoring,
)
from src.shared.domain.value_objects.scoring_format import ScoringFormat

TOTAL_HOLES = 18
_EMPATE = "HALVED"


@dataclass(frozen=True)
class _Totales:
    """La vuelta de uno sobre lo anotado, como la cuenta la clasificacion de la partida."""

    participant: QuickMatchParticipant
    points: int
    gross: int
    net: int
    par_played: int
    holes_played: int
    # Si jugo todos los hoyos de su tarjeta
    complete: bool

    @property
    def to_par(self) -> int:
        return self.net - self.par_played


@dataclass(frozen=True)
class _Lectura:
    match: QuickMatch
    course: GolfCourse
    scores: dict[ParticipantId, dict[int, int | None]]
    users: dict
    strokes: dict[ParticipantId, ParticipantStrokes]


class PublishQuickMatchResultUseCase:
    """
    Al terminar una partida rapida, como acabo cada jugador con cuenta.

    - **Stableford o Medal**: su puesto, de cuantos, si lo comparte, sus puntos
      (o su neto y su resultado contra el par) y sus golpes. Tambien el ultimo:
      lo decidio Agustin (21 oct 2026). Jugando solo, sin puesto (D18).
    - **Match play**: ganado, perdido o empatado, el tanteo y contra quien.

    **El puesto no lo guarda nadie**: la clasificacion de la partida rapida la
    pinta el cliente (`StablefordCalculator.rankParticipants`). Aqui se cuenta
    igual —los mismos golpes repartidos que el detalle de la partida y las
    mismas reglas por hoyo, que estan portadas con paridad en
    `StrokePlayScoring`— con una diferencia decidida en la tabla: un empate a
    puntos comparte puesto, no lo desempatan los golpes. El match play sale del
    mismo motor que el historial de partidas (`MatchPlayScoring`).

    Los invitados cuentan en la clasificacion, pero no tienen donde publicar.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        stroke_allocation: StrokeAllocationService | None = None,
        match_play: MatchPlayScoring | None = None,
    ):
        self._social_uow = social_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow
        self._user_uow = user_uow
        self._stroke_allocation = stroke_allocation or StrokeAllocationService()
        self._match_play = match_play or MatchPlayScoring()

    async def execute(self, quick_match_id_raw: str) -> int:
        """Publica el resultado de cada jugador con cuenta y devuelve cuantos."""
        lectura = await self._leer(quick_match_id_raw)
        if lectura is None:
            return 0

        if lectura.match.match_format is None:
            eventos = self._clasificacion(lectura)
        else:
            eventos = self._match_play_de(lectura)
        if not eventos:
            return 0

        eventos = await stamp_for_publication(self._user_uow, eventos)
        async with self._social_uow:
            await self._social_uow.activity_events.add_many(eventos)
        return len(eventos)

    # === Leer ===

    async def _leer(self, quick_match_id_raw: str) -> _Lectura | None:
        async with self._quick_match_uow, self._golf_course_uow, self._user_uow:
            match = await self._quick_match_uow.quick_matches.find_by_id(
                QuickMatchId(quick_match_id_raw)
            )
            if match is None or match.status != QuickMatchStatus.COMPLETED:
                return None
            course = await self._golf_course_uow.golf_courses.find_by_id(match.golf_course_id)
            if course is None:
                return None
            anotados = await self._quick_match_uow.quick_match_hole_scores.find_by_match(match.id)
            registrados = [p.user_id for p in match.participants if p.user_id is not None]
            users = {u.id: u for u in await self._user_uow.users.find_by_ids(registrados)}

        scores: dict[ParticipantId, dict[int, int | None]] = {}
        for anotado in anotados:
            scores.setdefault(anotado.participant_id, {})[anotado.hole_number] = anotado.score
        return _Lectura(match, course, scores, users, self._golpes(match, course, users))

    def _golpes(
        self, match: QuickMatch, course: GolfCourse, users: dict
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """El reparto de golpes de la partida, el mismo que da su detalle."""
        contexto = StrokeContextBuilder.build(course)
        handicaps: dict[ParticipantId, Decimal | None] = {}
        for p in match.participants:
            user: User | None = users.get(p.user_id) if p.user_id else None
            indice = p.effective_handicap(user.handicap.value if user and user.handicap else None)
            handicaps[p.participant_id] = None if indice is None else Decimal(str(indice))
        return self._stroke_allocation.allocate(
            participants=match.participants,
            handicaps=handicaps,
            tee_ratings=contexto.tee_ratings,
            holes_by_stroke_index=contexto.holes_by_stroke_index,
            holes_by_stroke_index_by_tee=contexto.holes_by_tee,
            match_format=match.match_format,
            allowance_percentage=match.get_effective_allowance(),
            play_mode=match.play_mode,
        )

    # === Stableford y Medal ===

    def _clasificacion(self, lectura: _Lectura) -> list[ActivityEvent]:
        match = lectura.match
        es_medal = match.scoring_format == ScoringFormat.MEDAL
        # Solo quien anoto algo: sin hoyos no hay vuelta que clasificar
        vueltas = [
            totales
            for p in match.participants
            if (totales := self._totales(lectura, p)) is not None
        ]
        if not vueltas:
            return []

        valores = [v.to_par if es_medal else v.points for v in vueltas]
        puestos = rank(valores, higher_is_better=not es_medal)
        hay_puesto = len(vueltas) > 1
        # El mejor bruto, solo entre tarjetas completas: nueve hoyos siempre
        # tienen menos golpes que dieciocho. El orden no se toca: el cliente
        # clasifica las incompletas con todas, por puntos o contra el par de lo
        # jugado (`StablefordCalculator`), y aqui se le sigue
        completas = [v.gross for v in vueltas if v.complete]
        mejor_bruto = min(completas) if completas else None

        eventos = []
        for vuelta, puesto in zip(vueltas, puestos, strict=True):
            user_id = vuelta.participant.user_id
            if user_id is None:
                continue
            payload: dict = {
                "golf_course_id": str(match.golf_course_id.value),
                "scoring_format": match.scoring_format.value if match.scoring_format else None,
                "holes_played": vuelta.holes_played,
                "gross_strokes": vuelta.gross,
                "total_players": len(vueltas),
                "position": puesto.position if hay_puesto else None,
                "tied": puesto.tied if hay_puesto else False,
                # La etiqueta «mejor bruto del grupo», solo si no gano: quien
                # gano ya tiene su titular
                "best_gross_in_group": (
                    hay_puesto
                    and vuelta.complete
                    and vuelta.gross == mejor_bruto
                    and puesto.position != 1
                ),
            }
            if es_medal:
                payload["net_strokes"] = vuelta.net
                payload["to_par"] = vuelta.to_par
            else:
                payload["points"] = vuelta.points
            eventos.append(self._evento(match, user_id, payload))
        return eventos

    def _totales(self, lectura: _Lectura, p: QuickMatchParticipant) -> _Totales | None:
        """
        Puntos, bruto y neto de su vuelta, como `computeParticipantTotals` del
        cliente: contra la tarjeta de su barra, y la raya (recogio) a doble
        bogey, que no puntua.
        """
        anotados = lectura.scores.get(p.participant_id)
        if not anotados:
            return None
        golpes = lectura.strokes.get(p.participant_id)
        puntos = bruto = neto = par = hoyos = 0
        tarjeta = lectura.course.hole_card_for(p.tee_color, p.tee_gender)
        for hoyo in tarjeta:
            if hoyo.number not in anotados:
                continue
            recibe = golpes.strokes_on_hole(hoyo.number) if golpes else 0
            score = anotados[hoyo.number]
            hoyos += 1
            par += hoyo.par
            if score is None:
                bruto += hoyo.par + NET_DOUBLE_BOGEY_OVER_PAR
                neto += hoyo.par + NET_DOUBLE_BOGEY_OVER_PAR
                continue
            puntos += StrokePlayScoring.hole_points(score, hoyo.par, recibe)
            bruto += score
            neto += score - recibe
        if hoyos == 0:
            return None
        return _Totales(p, puntos, bruto, neto, par, hoyos, complete=hoyos == len(tarjeta))

    # === Match play ===

    def _match_play_de(self, lectura: _Lectura) -> list[ActivityEvent]:
        match = lectura.match
        bandos = match.team_rosters()
        if bandos is None:
            return []
        bando_a, bando_b = bandos

        resultados = []
        for numero in range(1, TOTAL_HOLES + 1):
            del_hoyo = {
                pid: hoyos[numero] for pid, hoyos in lectura.scores.items() if numero in hoyos
            }
            if not hole_is_complete(del_hoyo, bando_a, bando_b, match.match_format):
                continue
            resultados.append(
                self._match_play.calculate_hole_winner(
                    [
                        self._neto(lectura, pid, numero, del_hoyo)
                        for pid in bando_a
                        if pid in del_hoyo
                    ],
                    [
                        self._neto(lectura, pid, numero, del_hoyo)
                        for pid in bando_b
                        if pid in del_hoyo
                    ],
                    match.match_format,
                )
            )
        if not resultados:
            return []

        ganador, tanteo = self._resultado(resultados)
        eventos = []
        for p in match.participants:
            if p.user_id is None:
                continue
            mio = bando_a if p.participant_id in bando_a else bando_b
            payload = {
                "golf_course_id": str(match.golf_course_id.value),
                "match_format": match.match_format.value if match.match_format else None,
                "holes_played": len(resultados),
                "outcome": self._lado(ganador, "A" if mio is bando_a else "B"),
                "score": tanteo,
                "partners": [
                    self._quien(o) for o in match.participants if o.participant_id in mio and o != p
                ],
                "opponents": [
                    self._quien(o) for o in match.participants if o.participant_id not in mio
                ],
            }
            eventos.append(self._evento(match, p.user_id, payload))
        return eventos

    def _resultado(self, resultados: list[str]) -> tuple[str | None, str]:
        """
        Quien gano y el tanteo, como el historial de partidas: «3&2» si se
        decidio antes del 18, la ventaja tal cual si no, «AS» si acabo igualado.
        """
        standing = self._match_play.calculate_match_standing(resultados)
        if self._match_play.is_match_decided(standing):
            decidido = self._match_play.format_decided_result(resultados)
            return decidido["winner"], decidido["score"]
        if standing["leading_team"] is None:
            return _EMPATE, "AS"
        return standing["leading_team"], standing["status"]

    @staticmethod
    def _neto(lectura: _Lectura, pid: ParticipantId, hoyo: int, del_hoyo: dict) -> int | None:
        # La raya se propaga: es el bando que no entrega bola y pierde el hoyo
        score = del_hoyo[pid]
        if score is None:
            return None
        golpes = lectura.strokes.get(pid)
        return golpes.net_score(hoyo, score) if golpes else score

    @staticmethod
    def _quien(p: QuickMatchParticipant) -> dict:
        """El rival o compañero: el id de quien tiene cuenta; el nombre del invitado."""
        if p.user_id is not None:
            return {"user_id": str(p.user_id.value), "name": None}
        return {"user_id": None, "name": f"{p.first_name} {p.last_name}".strip()}

    @staticmethod
    def _lado(ganador: str | None, bando: str) -> str:
        if ganador == _EMPATE or ganador is None:
            return "HALVED"
        return "WON" if ganador == bando else "LOST"

    @staticmethod
    def _evento(match: QuickMatch, user_id, payload: dict) -> ActivityEvent:
        return ActivityEvent.create(
            user_id=user_id,
            type=ActivityEventType.QUICK_MATCH_FINISHED,
            # La partida rapida no guarda cuando se jugo: se crea el mismo dia
            occurred_at=match.created_at,
            source_match_id=str(match.id.value),
            payload=payload,
        )

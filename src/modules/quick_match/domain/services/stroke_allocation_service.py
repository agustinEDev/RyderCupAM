"""
StrokeAllocationService - Reparto de golpes de handicap en una partida rapida.

Responde a una sola pregunta: cuantos golpes recibe cada participante en cada
hoyo. De ahi salen tanto los puntos que pinta la tarjeta como el score neto con
el que se decide cada hoyo en match play, que hasta ahora eran dos calculos
distintos (y discrepantes).

El reparto depende del formato, siguiendo el WHS igual que `competition`:

- SCRATCH: nadie recibe golpes, sea cual sea el formato.
- SINGLES: metodo diferencial. Solo el de mayor Playing Handicap recibe, y
  recibe la diferencia, en los hoyos de menor stroke index. El otro juega off
  scratch. Repartir el PH completo a cada uno (lo que hacia el frontend) da un
  total parecido pero en hoyos distintos, que es justo lo que decide los hoyos
  ajustados.
- FOURBALL: diferencias respecto al menor Course Handicap de los cuatro, con el
  allowance aplicado a la diferencia.
- FOURSOMES: a nivel de equipo, sobre el promedio de Course Handicaps; los dos
  jugadores del equipo comparten el mismo reparto porque comparten bola.
- Partido libre (MEDAL/STABLEFORD): cada uno contra el campo, con su Playing
  Handicap individual. Aqui el reparto individual SI es el correcto.
"""

from dataclasses import dataclass
from decimal import Decimal

from src.modules.competition.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode

from ..value_objects.participant_id import ParticipantId
from ..value_objects.quick_match_participant import QuickMatchParticipant

# Un SINGLES es exactamente 1 vs 1: con cualquier otro numero de participantes
# la partida esta a medio montar y no hay diferencia que repartir.
SINGLES_PARTICIPANTS = 2


@dataclass(frozen=True)
class ParticipantStrokes:
    """
    Golpes que recibe un participante, resueltos para un campo concreto.

    `strokes_received` lleva un numero de hoyo repetido tantas veces como golpes
    reciba en el (wrap-around cuando el reparto pasa de 18), igual que
    `MatchPlayer.strokes_received` en `competition`.
    """

    participant_id: ParticipantId
    playing_handicap: int
    strokes_received: tuple[int, ...]

    def strokes_on_hole(self, hole_number: int) -> int:
        """Golpes en un hoyo concreto (0, 1, 2...)."""
        return self.strokes_received.count(hole_number)

    def net_score(self, hole_number: int, gross_score: int) -> int:
        """Score neto en un hoyo, con el mismo suelo de 0 que `HoleScore` en competition."""
        return max(0, gross_score - self.strokes_on_hole(hole_number))


class StrokeAllocationService:
    """Servicio de dominio puro: sin IO, se le entregan los datos del campo ya resueltos."""

    def __init__(self, calculator: PlayingHandicapCalculator | None = None):
        self._calculator = calculator or PlayingHandicapCalculator()

    def allocate(
        self,
        *,
        participants: list[QuickMatchParticipant],
        handicaps: dict[ParticipantId, Decimal | None],
        tee_ratings: dict[tuple[str, str | None], TeeRating],
        holes_by_stroke_index: list[int],
        match_format: MatchFormat | None,
        allowance_percentage: int,
        play_mode: PlayMode,
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """
        Calcula el reparto de golpes de todos los participantes.

        Args:
            participants: Participantes de la partida (llevan tee_color/tee_gender)
            handicaps: Handicap Index ya resuelto por participante (custom_handicap,
                handicap manual del invitado o el del perfil). None si no se conoce.
            tee_ratings: Ratings por (color, genero); el genero va como str o None
            holes_by_stroke_index: Numeros de hoyo ordenados por stroke index
            match_format: SINGLES/FOURBALL/FOURSOMES, o None en partido libre
            allowance_percentage: Allowance efectivo de la partida (50-100)
            play_mode: SCRATCH no reparte nada; HANDICAP aplica el reparto WHS

        Returns:
            dict participant_id -> ParticipantStrokes (una entrada por participante,
            siempre; los que no reciben golpes salen con la tupla vacia)
        """
        if play_mode == PlayMode.SCRATCH:
            return {p.participant_id: self._no_strokes(p.participant_id) for p in participants}

        if match_format is None:
            return self._allocate_free_play(
                participants, handicaps, tee_ratings, holes_by_stroke_index, allowance_percentage
            )

        if match_format == MatchFormat.SINGLES:
            return self._allocate_singles(
                participants, handicaps, tee_ratings, holes_by_stroke_index, allowance_percentage
            )

        if match_format == MatchFormat.FOURBALL:
            return self._allocate_fourball(
                participants, handicaps, tee_ratings, holes_by_stroke_index, allowance_percentage
            )

        return self._allocate_foursomes(
            participants, handicaps, tee_ratings, holes_by_stroke_index, allowance_percentage
        )

    # ===========================================
    # Reparto por formato
    # ===========================================

    def _allocate_free_play(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """Cada uno contra el campo: su Playing Handicap individual, entero."""
        result = {}
        for p in participants:
            ph = self._playing_handicap(p, handicaps, tee_ratings, allowance)
            result[p.participant_id] = self._build(p.participant_id, ph, holes_by_stroke_index)
        return result

    def _allocate_singles(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """
        Metodo diferencial WHS: solo el de mayor PH recibe, y recibe la diferencia.

        Con menos de dos participantes (partida a medio montar) no hay contra quien
        medir la diferencia, asi que nadie recibe.
        """
        if len(participants) != SINGLES_PARTICIPANTS:
            return {p.participant_id: self._no_strokes(p.participant_id) for p in participants}

        a, b = participants
        ph_a = self._playing_handicap(a, handicaps, tee_ratings, allowance)
        ph_b = self._playing_handicap(b, handicaps, tee_ratings, allowance)

        strokes_a, strokes_b = self._calculator.calculate_singles_differential(
            ph_a, ph_b, holes_by_stroke_index
        )
        return {
            a.participant_id: ParticipantStrokes(a.participant_id, ph_a, tuple(strokes_a)),
            b.participant_id: ParticipantStrokes(b.participant_id, ph_b, tuple(strokes_b)),
        }

    def _allocate_fourball(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """Diferencias respecto al menor Course Handicap de los cuatro, con allowance."""
        course_handicaps = [
            (str(p.participant_id.value), self._course_handicap(p, handicaps, tee_ratings))
            for p in participants
        ]
        differential_phs = self._calculator.calculate_fourball_differential(
            course_handicaps, allowance
        )

        result = {}
        for p in participants:
            ph = differential_phs[str(p.participant_id.value)]
            result[p.participant_id] = self._build(p.participant_id, ph, holes_by_stroke_index)
        return result

    def _allocate_foursomes(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """
        A nivel de equipo: allowance sobre la diferencia de promedios de Course Handicap.

        Los dos jugadores de un equipo reciben exactamente el mismo reparto: juegan
        una sola bola a golpe alterno, de modo que el golpe es del equipo, no de
        quien la golpee en ese hoyo.
        """
        team_a = [p for p in participants if p.team == "A"]
        team_b = [p for p in participants if p.team == "B"]
        if not team_a or not team_b:
            return {p.participant_id: self._no_strokes(p.participant_id) for p in participants}

        team_a_chs = [self._course_handicap(p, handicaps, tee_ratings) for p in team_a]
        team_b_chs = [self._course_handicap(p, handicaps, tee_ratings) for p in team_b]

        team_a_ph, team_b_ph = self._calculator.calculate_foursomes_differential(
            team_a_chs, team_b_chs, allowance
        )

        result = {}
        for p in team_a:
            result[p.participant_id] = self._build(
                p.participant_id, team_a_ph, holes_by_stroke_index
            )
        for p in team_b:
            result[p.participant_id] = self._build(
                p.participant_id, team_b_ph, holes_by_stroke_index
            )
        return result

    # ===========================================
    # Helpers
    # ===========================================

    def _playing_handicap(
        self,
        participant: QuickMatchParticipant,
        handicaps: dict[ParticipantId, Decimal | None],
        tee_ratings: dict[tuple[str, str | None], TeeRating],
        allowance: int,
    ) -> int:
        """
        Playing Handicap del participante, con allowance aplicado.

        Sin handicap conocido juega a scratch. Sin un tee que se pueda valorar
        (no eligio barra, o la barra elegida no esta en el campo) se usa el propio
        Handicap Index como Playing Handicap: es una aproximacion, pero deja la
        partida utilizable en vez de tratar al jugador como scratch.
        """
        hi = handicaps.get(participant.participant_id)
        if hi is None:
            return 0

        tee_rating = self._tee_rating_for(participant, tee_ratings)
        if tee_rating is None:
            return max(0, int(hi.to_integral_value()))

        return self._calculator.calculate(hi, tee_rating, allowance)

    def _course_handicap(
        self,
        participant: QuickMatchParticipant,
        handicaps: dict[ParticipantId, Decimal | None],
        tee_ratings: dict[tuple[str, str | None], TeeRating],
    ) -> int:
        """Course Handicap (sin allowance), base de los repartos por equipos."""
        hi = handicaps.get(participant.participant_id)
        if hi is None:
            return 0

        tee_rating = self._tee_rating_for(participant, tee_ratings)
        if tee_rating is None:
            return max(0, int(hi.to_integral_value()))

        return self._calculator.calculate_course_handicap(hi, tee_rating)

    @staticmethod
    def _tee_rating_for(
        participant: QuickMatchParticipant,
        tee_ratings: dict[tuple[str, str | None], TeeRating],
    ) -> TeeRating | None:
        """
        Busca la valoracion del tee elegido por (color, genero).

        El genero forma parte de la clave, no es un detalle decorativo: un campo
        federado valora la misma barra por separado para cada genero y la
        diferencia de CR/SR entre ambas vale varios golpes.
        """
        if participant.tee_color is None:
            return None
        gender = participant.tee_gender.value if participant.tee_gender else None
        return tee_ratings.get((participant.tee_color.value, gender))

    def _build(
        self, participant_id: ParticipantId, playing_handicap: int, holes_by_stroke_index: list[int]
    ) -> ParticipantStrokes:
        strokes = self._calculator.compute_strokes_received(
            playing_handicap, holes_by_stroke_index
        )
        return ParticipantStrokes(participant_id, playing_handicap, tuple(strokes))

    @staticmethod
    def _no_strokes(participant_id: ParticipantId) -> ParticipantStrokes:
        return ParticipantStrokes(participant_id, 0, ())

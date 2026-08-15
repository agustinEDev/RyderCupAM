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

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

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

    `strokes_by_hole` va CON SIGNO y solo lleva los hoyos con golpe: positivo si
    lo recibe, negativo si lo cede. Un jugador de handicap plus cede golpes al
    campo empezando por el hoyo mas facil (Regla WHS 8.2), y por eso no vale la
    lista de hoyos repetidos que usa `MatchPlayer` en `competition`: esa no sabe
    representar un golpe negativo.
    """

    participant_id: ParticipantId
    playing_handicap: int
    strokes_by_hole: dict[int, int] = field(default_factory=dict)

    def strokes_on_hole(self, hole_number: int) -> int:
        """Golpes en un hoyo concreto: 0, 1, 2... o negativo si los cede."""
        return self.strokes_by_hole.get(hole_number, 0)

    def net_score(self, hole_number: int, gross_score: int) -> int:
        """Score neto en un hoyo, con el mismo suelo de 0 que `HoleScore` en competition."""
        return max(0, gross_score - self.strokes_on_hole(hole_number))

    @property
    def total_strokes(self) -> int:
        """Suma con signo de los golpes repartidos en la vuelta."""
        return sum(self.strokes_by_hole.values())


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
        holes_by_stroke_index_by_tee: dict[tuple[str, str | None], list[int]] | None = None,
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """
        Calcula el reparto de golpes de todos los participantes.

        Args:
            participants: Participantes de la partida (llevan tee_color/tee_gender)
            handicaps: Handicap Index ya resuelto por participante (custom_handicap,
                handicap manual del invitado o el del perfil). None si no se conoce.
            tee_ratings: Ratings por (color, genero); el genero va como str o None
            holes_by_stroke_index: Numeros de hoyo ordenados por stroke index (por defecto)
            holes_by_stroke_index_by_tee: Orden propio de cada barra, cuando el campo
                lo trae. En un campo federado el stroke index puede cambiar de una
                barra a otra, y los golpes van en los hoyos de la barra que se juega
            match_format: SINGLES/FOURBALL/FOURSOMES, o None en partido libre
            allowance_percentage: Allowance efectivo de la partida (50-100)
            play_mode: SCRATCH no reparte nada; HANDICAP aplica el reparto WHS

        Returns:
            dict participant_id -> ParticipantStrokes (una entrada por participante,
            siempre; los que no reciben golpes salen con el reparto vacio)
        """
        if play_mode == PlayMode.SCRATCH:
            return {p.participant_id: self._no_strokes(p.participant_id) for p in participants}

        # Se pasa como argumento en lugar de guardarlo en el objeto: el servicio
        # se inyecta como singleton y tiene que seguir siendo puro.
        by_tee = holes_by_stroke_index_by_tee or {}

        if match_format is None:
            return self._allocate_free_play(
                participants,
                handicaps,
                tee_ratings,
                holes_by_stroke_index,
                allowance_percentage,
                by_tee,
            )

        if match_format == MatchFormat.SINGLES:
            return self._allocate_singles(
                participants,
                handicaps,
                tee_ratings,
                holes_by_stroke_index,
                allowance_percentage,
                by_tee,
            )

        if match_format == MatchFormat.FOURBALL:
            return self._allocate_fourball(
                participants,
                handicaps,
                tee_ratings,
                holes_by_stroke_index,
                allowance_percentage,
                by_tee,
            )

        if match_format == MatchFormat.FOURSOMES:
            return self._allocate_foursomes(
                participants,
                handicaps,
                tee_ratings,
                holes_by_stroke_index,
                allowance_percentage,
                by_tee,
            )

        # Un formato nuevo tiene que traer su reparto: caer aqui por descarte le
        # daria en silencio el de golpe alterno, que casi seguro no es el suyo.
        raise ValueError(f"No stroke allocation defined for match format {match_format}")

    # ===========================================
    # Reparto por formato
    # ===========================================

    def _allocate_free_play(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance, by_tee
    ) -> dict[ParticipantId, ParticipantStrokes]:
        """
        Cada uno contra el campo: su Playing Handicap individual, entero.

        Aqui el Playing Handicap NO se acota a cero. Un jugador de handicap plus
        cede golpes al campo (Regla WHS 8.2), y acotarlo dejaria la tarjeta
        contando una cosa y la clasificacion otra.
        """
        result = {}
        for p in participants:
            ph = self._playing_handicap(
                p, handicaps, tee_ratings, allowance, allow_negative=True
            )
            result[p.participant_id] = self._build(
                p.participant_id, ph, self._holes_for(p, holes_by_stroke_index, by_tee)
            )
        return result

    def _allocate_singles(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance, by_tee
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
        difference = ph_a - ph_b

        # El PH que se guarda es el individual, para poder mostrarlo; el reparto
        # es la diferencia, y solo la recibe uno de los dos.
        return {
            a.participant_id: self._build(
                a.participant_id,
                max(0, difference),
                self._holes_for(a, holes_by_stroke_index, by_tee),
                display_handicap=ph_a,
            ),
            b.participant_id: self._build(
                b.participant_id,
                max(0, -difference),
                self._holes_for(b, holes_by_stroke_index, by_tee),
                display_handicap=ph_b,
            ),
        }

    def _allocate_fourball(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance, by_tee
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
            allocated = differential_phs[str(p.participant_id.value)]
            # Se guarda el Playing Handicap del jugador, no la diferencia. Si no,
            # la tarjeta enseña "Hcp de juego 14 - recibe 14 golpes": el mismo
            # numero dos veces, y ninguno es su handicap de juego.
            result[p.participant_id] = self._build(
                p.participant_id,
                allocated,
                self._holes_for(p, holes_by_stroke_index, by_tee),
                display_handicap=self._playing_handicap(p, handicaps, tee_ratings, allowance),
            )
        return result

    def _allocate_foursomes(
        self, participants, handicaps, tee_ratings, holes_by_stroke_index, allowance, by_tee
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
        for team, allocated in ((team_a, team_a_ph), (team_b, team_b_ph)):
            # Golpe alterno: una sola bola, asi que un solo orden de dificultad
            # para los dos. Se usa el del campo aunque cada uno juegue una barra
            # distinta, porque el golpe es del equipo y no puede caer en dos
            # hoyos segun quien golpee.
            for p in team:
                result[p.participant_id] = self._build(
                    p.participant_id,
                    allocated,
                    holes_by_stroke_index,
                    display_handicap=self._playing_handicap(
                        p, handicaps, tee_ratings, allowance
                    ),
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
        allow_negative: bool = False,
    ) -> int:
        """
        Playing Handicap del participante, con allowance aplicado.

        Sin handicap conocido juega a scratch. Sin un tee que se pueda valorar
        (no eligio barra, o la barra elegida no esta en el campo) se usa el propio
        Handicap Index como Playing Handicap: es una aproximacion, pero deja la
        partida utilizable en vez de tratar al jugador como scratch.

        `allow_negative` deja pasar el handicap plus. En match play no se usa: la
        diferencia entre dos Playing Handicaps ya recoge la ventaja, y el WHS
        acota cada uno a cero antes de restarlos.
        """
        hi = handicaps.get(participant.participant_id)
        if hi is None:
            return 0

        tee_rating = self._tee_rating_for(participant, tee_ratings)
        if tee_rating is None:
            # El allowance se aplica igual: sin el, quien no tiene barra
            # valorable jugaria al 100% de su handicap mientras el resto de la
            # partida juega al 95%, y saldria ganando por no tener datos.
            rounded = self._round_half_up(hi * Decimal(allowance) / Decimal(100))
            return rounded if allow_negative else max(0, rounded)

        if allow_negative:
            return self._calculator.calculate_unbounded(hi, tee_rating, allowance)
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
            return max(0, self._round_half_up(hi))

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

        Pero un campo dado de alta a mano puede tener la salida sin genero, y el
        participante siempre manda color y genero juntos (lo exige el DTO). Sin
        la reserva a `(color, None)` esa busqueda no acertaria nunca y el jugador
        caeria al Handicap Index: cinco golpes de diferencia, en silencio. Es la
        misma reserva que hace `generate_matches_use_case` en competition.
        """
        if participant.tee_color is None:
            return None

        color = participant.tee_color.value
        gender = participant.tee_gender.value if participant.tee_gender else None
        return tee_ratings.get((color, gender)) or tee_ratings.get((color, None))

    @staticmethod
    def _holes_for(
        participant: QuickMatchParticipant,
        default: list[int],
        by_tee: dict[tuple[str, str | None], list[int]],
    ) -> list[int]:
        """
        Orden de dificultad de la barra que juega el participante.

        Cae al del campo cuando la barra no trae tarjeta propia. Misma reserva de
        genero que `_tee_rating_for`, para que las dos resuelvan la misma barra.
        """
        if participant.tee_color is None:
            return default
        color = participant.tee_color.value
        gender = participant.tee_gender.value if participant.tee_gender else None
        return by_tee.get((color, gender)) or by_tee.get((color, None)) or default

    def _build(
        self,
        participant_id: ParticipantId,
        allocated: int,
        holes_by_stroke_index: list[int],
        display_handicap: int | None = None,
    ) -> ParticipantStrokes:
        """
        Args:
            allocated: Golpes a repartir (la diferencia, en los formatos por equipos)
            display_handicap: Playing Handicap del jugador, para mostrar. En match
                play NO coincide con `allocated`: uno es con lo que juega y el otro
                lo que recibe.
        """
        return ParticipantStrokes(
            participant_id,
            allocated if display_handicap is None else display_handicap,
            self.allocate_by_hole(allocated, holes_by_stroke_index),
        )

    @staticmethod
    def _round_half_up(value: Decimal) -> int:
        """
        Redondea alejandose del cero, como `PlayingHandicapCalculator`.

        `Decimal.to_integral_value()` usa ROUND_HALF_EVEN por defecto: 20.5 -> 20
        y 21.5 -> 22. Todo el resto del calculo de handicap usa ROUND_HALF_UP, y
        el frontend tambien, asi que dejarlo al default partia el empate para el
        lado contrario en los handicaps acabados en .5, que son de lo mas comun.
        """
        return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def allocate_by_hole(playing_handicap: int, holes_by_stroke_index: list[int]) -> dict[int, int]:
        """
        Reparte un Playing Handicap con signo sobre los hoyos del campo.

        Positivo: se reparte del hoyo mas dificil (stroke index 1) al mas facil,
        dando la vuelta cuando pasa del numero de hoyos.
        Negativo (handicap plus): se cede empezando por el mas facil y hacia
        atras, que es lo que manda la Regla WHS 8.2.

        Solo devuelve los hoyos con golpe, para no arrastrar 18 ceros.
        """
        total_holes = len(holes_by_stroke_index)
        if total_holes == 0 or playing_handicap == 0:
            return {}

        sign = 1 if playing_handicap > 0 else -1
        magnitude = abs(playing_handicap)
        base, remainder = divmod(magnitude, total_holes)

        allocation: dict[int, int] = {}
        for position, hole_number in enumerate(holes_by_stroke_index):
            stroke_index = position + 1
            count = base
            if sign > 0:
                count += 1 if remainder >= stroke_index else 0
            else:
                count += 1 if remainder >= (total_holes + 1 - stroke_index) else 0
            if count:
                allocation[hole_number] = sign * count
        return allocation

    @staticmethod
    def _no_strokes(participant_id: ParticipantId) -> ParticipantStrokes:
        return ParticipantStrokes(participant_id, 0, {})

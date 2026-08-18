"""
ScoringCoverageService - Domain Service.

Calcula el reparto de "quien anota a quien" en una partida rapida cuando no
todos los participantes tienen la app (invitados, o registrados que no van
a anotar en esa partida concreta).

Es puro (sin dependencias de framework ni IO).

Reglas (confirmadas con el usuario):
- El creador es siempre uno de los anotadores.
- El reparto de no-anotadores entre anotadores es lo mas uniforme posible.
- El sobrante de un reparto no exacto lo absorbe el creador.
- FOURSOMES no se anota por jugador: **una pareja marca a la otra**. Ahi la
  unidad es el bando, no el jugador, y el reparto uniforme no aplica.
"""

from src.modules.competition.domain.value_objects.match_format import MatchFormat

from ..exceptions.quick_match_violations import InvalidScorerConfigurationViolation
from ..value_objects.participant_id import ParticipantId
from ..value_objects.quick_match_participant import QuickMatchParticipant


class ScoringCoverageService:
    """Servicio de dominio para el reparto de anotacion en partidas rapidas."""

    def compute_assignments(
        self,
        participants: list[QuickMatchParticipant],
        scorer_ids: list[ParticipantId],
        creator_participant_id: ParticipantId,
        match_format: MatchFormat | None = None,
    ) -> dict[ParticipantId, list[ParticipantId]]:
        """
        Calcula que participantes cubre cada anotador.

        Cada anotador se cubre siempre a si mismo. Los participantes que no
        son anotadores (invitados o registrados no seleccionados) se
        reparten a partes iguales (division entera) entre TODOS los
        anotadores, incluido el creador; el sobrante de una division no
        exacta lo absorbe el creador.

        Returns:
            Dict {scorer_participant_id: [participant_ids cubiertos]}
        """
        if creator_participant_id not in scorer_ids:
            raise InvalidScorerConfigurationViolation(
                "creator_participant_id must be included in scorer_ids."
            )

        if match_format == MatchFormat.FOURSOMES:
            return self._foursomes_assignments(participants, scorer_ids)

        all_ids = [p.participant_id for p in participants]
        non_scorer_ids = [pid for pid in all_ids if pid not in scorer_ids]

        assignments: dict[ParticipantId, list[ParticipantId]] = {sid: [sid] for sid in scorer_ids}

        n_scorers = len(scorer_ids)
        base = len(non_scorer_ids) // n_scorers
        remainder = len(non_scorer_ids) % n_scorers

        idx = 0
        for scorer_id in scorer_ids:
            assignments[scorer_id].extend(non_scorer_ids[idx : idx + base])
            idx += base

        if remainder:
            assignments[creator_participant_id].extend(non_scorer_ids[idx:])

        return assignments

    @staticmethod
    def _foursomes_assignments(
        participants: list[QuickMatchParticipant],
        scorer_ids: list[ParticipantId],
    ) -> dict[ParticipantId, list[ParticipantId]]:
        """
        En foursomes marca la pareja rival, no cada jugador por su cuenta.

        El bando juega UNA bola, asi que solo hay dos tarjetas que llevar y la
        unidad es la pareja: cada anotador cubre a los dos del bando contrario.
        Repartir jugador a jugador —lo que vale cuando cada uno juega su bola—
        dejaba a un anotador con un rival y sin su propio companero, sin que eso
        significara nada en un formato de bola alterna.

        Si el bando contrario no tiene ningun anotador, este ademas lleva la
        suya: alguien tiene que anotarla, y es preferible a que esa bola se
        quede sin tarjeta.
        """
        sides: dict[str, list[ParticipantId]] = {}
        for participant in participants:
            sides.setdefault(participant.team or "A", []).append(participant.participant_id)

        side_of = {pid: side for side, pids in sides.items() for pid in pids}

        assignments: dict[ParticipantId, list[ParticipantId]] = {}
        for scorer_id in scorer_ids:
            own_side = side_of.get(scorer_id)
            rival_sides = [side for side in sides if side != own_side]

            covered = [pid for side in rival_sides for pid in sides[side]]

            rival_has_scorer = any(
                pid in scorer_ids for side in rival_sides for pid in sides[side]
            )
            if not rival_has_scorer and own_side is not None:
                covered.extend(sides[own_side])

            assignments[scorer_id] = covered

        return assignments

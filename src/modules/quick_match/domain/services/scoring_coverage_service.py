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
"""

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

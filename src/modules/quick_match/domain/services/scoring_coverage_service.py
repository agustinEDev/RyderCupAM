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
- FOURSOMES no se anota por jugador: el bando juega UNA bola, asi que solo
  hay dos tarjetas y se anotan **cruzadas, como en un 1 vs 1**. Cada anotador
  apunta los golpes de su propio bando y marca los del contrario, de modo que
  cubre a los cuatro participantes y el reparto uniforme no aplica.
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

        En FOURSOMES no hay reparto: la anotacion es cruzada y cada anotador
        cubre a los cuatro (ver `_foursomes_assignments`).

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
        En foursomes se anota cruzado: cada anotador cubre a los cuatro.

        El bando juega UNA bola, asi que en la partida solo hay dos tarjetas y
        funciona como un 1 vs 1: cada anotador apunta los golpes de su propio
        bando y marca los del contrario. Con un anotador en cada bando las dos
        bolas se llevan por duplicado; con uno solo, ese lleva las dos. En
        ningun caso queda una bola sin quien pueda anotarla, que es lo que si
        pasaba al repartir jugador a jugador: ese reparto vale cuando cada uno
        juega su bola, y aqui dejaba a un anotador con un rival y sin su propio
        companero, sin que eso significara nada en un formato de bola alterna.

        Que dos anotadores puedan escribir la misma bola es deliberado y es lo
        mismo que ya ocurre en un 1 vs 1: si las anotaciones no coinciden se
        aclara entre las parejas y se corrige el hoyo. Las partidas rapidas no
        llevan validacion jugador/marcador; esa vive en el modulo competition.
        """
        all_ids = [p.participant_id for p in participants]
        return {scorer_id: list(all_ids) for scorer_id in scorer_ids}

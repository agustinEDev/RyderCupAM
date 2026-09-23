"""
EnvelopePairings - Los enfrentamientos que fijan los sobres (FE #655).

Cuando los dos sobres de una sesion estan abiertos, los enfrentamientos ya
estan decididos: salen de cruzar las dos listas por posicion. La generacion de
partidos los respeta en vez de emparejar por handicap, que es lo que hace
cuando no hay sobres.

Sin esto los sobres serian un adorno: el organizador pulsaria «generar» y la
aplicacion emparejaria por ranking como si nadie hubiera entregado nada.
"""

from src.modules.competition.application.dto.round_match_dto import ManualPairingDTO
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_id import RoundId


class EnvelopesNotRevealedError(Exception):
    """Hay sobres entregados y todavia cerrados: primero se abren."""

    pass


class EnvelopesDecideThePairingsError(Exception):
    """Con los sobres abiertos, los enfrentamientos ya no los pone nadie mas."""

    pass


class EnvelopePairings:
    """Los enfrentamientos de una sesion, si los sobres ya estan abiertos."""

    @staticmethod
    async def decidir(uow: CompetitionUnitOfWorkInterface, round_id: RoundId, manual_pairings=None):
        """Los enfrentamientos que se van a usar para generar los partidos.

        Los de los sobres abiertos mandan: sin esto el organizador pulsaria
        «generar» y la aplicacion emparejaria por handicap como si nadie
        hubiera entregado nada. Y los que manda el organizador NO los pisan;
        la comprobacion va ANTES de mirarlos porque, si no, la guarda de los
        sobres sin abrir se esquivaba mandando emparejamientos a mano.

        Returns:
            Los de los sobres, los del organizador, o None para emparejar por
            ranking como se ha hecho siempre

        Raises:
            EnvelopesDecideThePairingsError: Si hay sobres abiertos y ademas se
                mandan emparejamientos a mano
            EnvelopesNotRevealedError: Si hay algun sobre entregado sin abrir
        """
        de_los_sobres = await EnvelopePairings.de_la_ronda(uow, round_id)
        if de_los_sobres is None:
            await EnvelopePairings.comprobar_que_no_hay_sobres_sin_abrir(uow, round_id)
            return manual_pairings
        if manual_pairings:
            raise EnvelopesDecideThePairingsError(
                "Los enfrentamientos de esta sesión salen de los sobres de los capitanes"
            )
        return de_los_sobres

    @staticmethod
    async def comprobar_que_no_hay_sobres_sin_abrir(
        uow: CompetitionUnitOfWorkInterface, round_id: RoundId
    ) -> None:
        """Con un sobre entregado y sin abrir no se empareja por ranking.

        Seria tirar a la basura la lista que el capitan si entrego: los
        enfrentamientos saldrian del handicap y nadie diria nada.

        Raises:
            EnvelopesNotRevealedError: Si algun sobre esta entregado y cerrado
        """
        for sobre in await uow.envelopes.find_by_round(round_id):
            if sobre.is_submitted() and sobre.is_sealed():
                raise EnvelopesNotRevealedError(
                    "Hay sobres entregados sin abrir: ábrelos antes de generar los partidos"
                )

    @staticmethod
    async def de_la_ronda(
        uow: CompetitionUnitOfWorkInterface, round_id: RoundId
    ) -> list[ManualPairingDTO] | None:
        """
        Args:
            uow: Unit of Work ya abierta
            round_id: La sesion

        Returns:
            Los enfrentamientos en la MISMA forma que los manda el organizador
            —por eso son `ManualPairingDTO` y no tuplas: los consume el mismo
            codigo—, o None si esta sesion no los tiene fijados: sin sobres,
            con uno solo o con los dos todavia cerrados
        """
        sobres = {s.team: s for s in await uow.envelopes.find_by_round(round_id)}
        sobre_a, sobre_b = sobres.get("A"), sobres.get("B")
        if not sobre_a or not sobre_b:
            return None
        if sobre_a.is_sealed() or sobre_b.is_sealed():
            return None
        return [
            ManualPairingDTO(
                team_a_player_ids=[uid.value for uid in fila_a],
                team_b_player_ids=[uid.value for uid in fila_b],
            )
            for fila_a, fila_b in Envelope.pair_up(sobre_a, sobre_b)
        ]

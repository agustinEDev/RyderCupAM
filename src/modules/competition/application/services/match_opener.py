"""
MatchOpener - Abrir un partido para anotar, en un solo sitio.

Abrir un partido son tres cosas, no una: ponerlo IN_PROGRESS, **pre-crear los 18
HoleScore de cada jugador** y arrancar su ronda si estaba programada.

Los tres pasos vivian dentro del START manual. Desde la BE #305 hay un segundo
camino —la apertura automatica al llegar el primer golpe— y duplicarlos habria
sido peligroso: si un camino abre el partido pero no crea los hoyos, el POST del
golpe devuelve 200 y **no guarda nada**, porque quien anota busca la fila del
hoyo y, si no esta, no hace nada y no se queja. Una perdida silenciosa.
"""

from src.modules.competition.domain.entities.hole_score import MAX_HOLE, MIN_HOLE, HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.round_status import RoundStatus


class MatchOpener:
    """Deja un partido listo para anotar."""

    @staticmethod
    async def open(
        match: Match,
        round_entity: Round,
        uow: CompetitionUnitOfWorkInterface,
    ) -> str | None:
        """
        Arranca el partido, crea sus hoyos y arranca la ronda si hacia falta.

        No persiste el partido ni la ronda: eso lo hace quien llama, que sabe si
        tiene que actualizar uno, otro o los dos.

        :returns: el estado nuevo de la ronda si la ha arrancado, o `None`.
        :raises ValueError: si el partido no se puede arrancar (lo lanza el dominio).
        """
        match.start()

        hole_scores = []
        for team, players in [("A", match.team_a_players), ("B", match.team_b_players)]:
            for player in players:
                for hole_num in range(MIN_HOLE, MAX_HOLE + 1):
                    hole_scores.append(
                        HoleScore.create(
                            match_id=match.id,
                            hole_number=hole_num,
                            player_user_id=player.user_id,
                            team=team,
                            strokes_received=player.strokes_on_hole(hole_num),
                        )
                    )
        await uow.hole_scores.add_many(hole_scores)
        # Volcado a la sesion antes de seguir: quien abre el partido para anotar
        # un golpe busca acto seguido la fila de ese hoyo, y si todavia no esta
        # no anota nada y no se queja —la peticion contesta 200 y el golpe
        # desaparece—. Lo destapo el test de integracion de la BE #305
        await uow.flush()

        if round_entity.status == RoundStatus.SCHEDULED:
            round_entity.start()
            return round_entity.status.value
        return None

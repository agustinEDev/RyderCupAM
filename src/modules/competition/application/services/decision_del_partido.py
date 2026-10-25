"""La decisión del partido, revisada tras un cambio en lo que cuenta (25 oct 2026)."""

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.shared.domain.value_objects.match_format import MatchFormat


async def revisa_la_decision(
    uow: CompetitionUnitOfWorkInterface,
    scoring_service: ScoringService,
    match: Match,
    match_format: MatchFormat,
) -> bool:
    """
    Vuelve a mirar si el partido está decidido con lo anotado: corregir un hoyo
    anterior, retirar a un jugador o devolverlo puede quitar la decisión o
    cambiar el N&M (Agustín, 25 oct 2026). Con una tarjeta ya entregada, una
    decisión que ya había no se mueve: quien entregó con el partido decidido ya
    no puede anotar el resto, y se atascaría. Si aún no estaba decidido, sí puede
    llegar. Devuelve si cambió; quien llama guarda el partido.
    """
    if match.scorecard_submitted_by and match.is_decided:
        return False
    all_scores = await uow.hole_scores.find_by_match(match.id)
    decided_result = scoring_service.decided_result(all_scores, match_format, match.bolas_fuera)
    if decided_result == match.decided_result:
        return False
    if decided_result is None:
        match.clear_decided()
    else:
        match.mark_decided(decided_result)
    return True

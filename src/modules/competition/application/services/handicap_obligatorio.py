"""
El hándicap es obligatorio para jugar un Stableford o un Medal (#251, 7 oct 2026).

Como en los torneos de la RFEG: sin hándicap no se entra, porque de él sale la
categoría. Vale el del perfil, o uno personalizado que ponga el organizador (lo
único en lo que nos apartamos del mercado). Se exige por los mismos caminos que
el género: crear la competición, pedir plaza, aceptar una invitación, la
inscripción directa y aprobar una solicitud. La Ryder no lo exige.
"""

from decimal import Decimal

from src.modules.competition.application.services.genero_obligatorio import (
    PerfilIncompletoError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class HandicapRequiredError(PerfilIncompletoError):
    """Quien entra en un stroke play no tiene hándicap, ni uno personalizado."""


async def exigir_handicap(
    user_repository: UserRepositoryInterface,
    competition: Competition,
    user_id: UserId,
    *,
    es_quien_se_apunta: bool,
    al_crear: bool = False,
    personalizado: Decimal | None = None,
) -> None:
    """
    Args:
        user_repository: De donde sale el perfil
        competition: Donde entra; solo un stroke play lo exige
        user_id: Quien entra
        es_quien_se_apunta: Si lo pide el propio jugador o el organizador por él
        al_crear: Si es el organizador creándola: queda inscrito como jugador
        personalizado: El que le pone el organizador al inscribirlo, si lo hay

    Raises:
        HandicapRequiredError: Si no tiene ninguno
    """
    if competition.stroke_play is None or personalizado is not None:
        return
    usuario = await user_repository.find_by_id(user_id)
    # Uno que no existe no es cosa de esta regla: no se le acusa de nada
    if usuario is None or usuario.handicap is not None:
        return
    if al_crear:
        raise HandicapRequiredError(
            "Para crear un Stableford o un Medal, indica tu hándicap en tu perfil: como "
            "organizador juegas en él, y de tu hándicap sale tu categoría."
        )
    if es_quien_se_apunta:
        raise HandicapRequiredError(
            "Para apuntarte a un Stableford o un Medal, indica tu hándicap en tu perfil: "
            "de él sale tu categoría."
        )
    raise HandicapRequiredError(
        "Este jugador no tiene hándicap en su perfil: para inscribirlo, ponle uno personalizado."
    )


async def exigir_que_no_se_quede_sin(
    user_repository: UserRepositoryInterface, competition: Competition, user_id: UserId
) -> None:
    """
    Quitar el personalizado no puede dejar a nadie sin hándicap en un stroke play.

    Raises:
        HandicapRequiredError: Si no tiene hándicap en su perfil
    """
    if competition.stroke_play is None:
        return
    usuario = await user_repository.find_by_id(user_id)
    if usuario is not None and usuario.handicap is None:
        raise HandicapRequiredError(
            "No se puede quitar: el jugador no tiene hándicap en su perfil y se quedaría "
            "sin hándicap. Cámbialo por otro valor."
        )

"""
El género es obligatorio para apuntarse a una competición (#710, 24 sep).

Las barras de salida se valoran por género: sin él no se sabe desde cuáles
juega, y al generar los partidos se bloqueaba la sesión entera (BE #360). Se
exige al entrar, por los tres caminos: pedir plaza, aceptar una invitación y
la inscripción directa del organizador. El mensaje de la generación queda como
red para quien ya estuviera inscrito sin él.
"""

from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GenderRequiredError(Exception):
    """Quien se apunta no tiene el género en su perfil."""


async def exigir_genero(
    user_repository: UserRepositoryInterface,
    user_id: UserId,
    *,
    es_quien_se_apunta: bool,
    al_crear: bool = False,
) -> None:
    """
    Args:
        user_repository: De donde sale el perfil
        user_id: Quien entra en la competición
        es_quien_se_apunta: Si lo pide el propio jugador (le toca a él
            rellenarlo) o el organizador por él
        al_crear: Si es el organizador creándola: crearla le inscribe como
            jugador, y el mensaje tiene que decir por qué se le pide

    Raises:
        GenderRequiredError: Si existe y no tiene el género puesto
    """
    usuario = await user_repository.find_by_id(user_id)
    # Uno que no existe no es cosa de esta regla: no se le acusa de nada
    if usuario is None or usuario.gender is not None:
        return
    if al_crear:
        raise GenderRequiredError(
            "Para crear una competición, indica tu género en tu perfil: como "
            "organizador juegas en ella y las barras de salida se valoran por género."
        )
    if es_quien_se_apunta:
        raise GenderRequiredError(
            "Para apuntarte, indica tu género en tu perfil: las barras de salida "
            "se valoran por género."
        )
    raise GenderRequiredError(
        "Este jugador no tiene el género en su perfil: sin él no se sabe desde qué barras juega."
    )

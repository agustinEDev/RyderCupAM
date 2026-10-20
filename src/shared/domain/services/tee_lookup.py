"""
Buscar la barra de un jugador por color y género (RyderCupAM#165).

Un campo federado valora la misma barra por separado para cada género: la
diferencia de Course Rating y Slope entre ellas vale varios golpes. Pero un
campo dado de alta a mano puede tener la barra sin género, y el jugador siempre
llega con color y género. La regla: primero (color, género) y, si no está,
(color, sin género). Nunca la del otro género.

Estaba escrita siete veces entre competición y partida rápida. Las claves son
los valores en texto, (color, género), como las guardan los contextos del campo.
"""

from collections.abc import Mapping
from typing import TypeVar, overload

T = TypeVar("T")
TeeKey = tuple[str, str | None]


def tee_key_for(by_tee: Mapping[TeeKey, object], color: str, gender: str | None) -> TeeKey | None:
    """
    La barra que se usa: (color, género), o (color, None) como reserva.

    Competición la necesita, y no solo el valor, porque guarda en el jugador el
    género de la barra con la que juega.

    Returns:
        La clave encontrada, o None si no hay ninguna de las dos
    """
    for key in ((color, gender), (color, None)):
        if key in by_tee:
            return key
    return None


@overload
def find_tee(by_tee: Mapping[TeeKey, T], color: str, gender: str | None) -> T | None: ...


@overload
def find_tee(by_tee: Mapping[TeeKey, T], color: str, gender: str | None, default: T) -> T: ...


def find_tee(
    by_tee: Mapping[TeeKey, T], color: str, gender: str | None, default: T | None = None
) -> T | None:
    """El valor de esa barra (su valoración, su orden de hoyos…), o `default`."""
    key = tee_key_for(by_tee, color, gender)
    return by_tee[key] if key is not None else default

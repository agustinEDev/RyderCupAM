"""
Qué tarjeta cuenta como vuelta jugada.

Vive en `shared` porque la regla la necesitan dos módulos que no deben depender
uno del otro: las estadísticas (`user`, BE #174) y el feed de logros (`social`,
BE #175). Y tiene que ser **la misma** en ambos: si una tarjeta no es fiable para
la media del jugador, tampoco lo es para presumir de ella delante de sus amigos.
"""

# Media vuelta: los nueve de ida o los nueve de vuelta. Cuenta como vuelta
# terminada, siempre que la partida esté cerrada.
HALF_ROUND_HOLES = 9


def countable_holes(scores_by_hole: dict, hole_card: list) -> list | None:
    """
    Los hoyos que forman una vuelta computable, o None si no forman ninguna.

    Vale la vuelta entera y vale media: los nueve de ida o los nueve de vuelta,
    que es como se juega media vuelta de verdad. Lo que no vale es una tarjeta a
    la que le falten hoyos sueltos, porque eso no es media vuelta sino una vuelta
    abandonada — y son justo las malas las que se abandonan.

    De ahí que a la media vuelta se le exija tener **exactamente** sus nueve: con
    diez anotados no hay ni vuelta entera ni mitad limpia.

    Recibe la tarjeta ya resuelta y no el campo: el par y el índice son de la
    barra que juega cada uno, y quien llama es el único que sabe cuál es. Sacar
    aquí la tarjeta de referencia le colaba la de otra barra a quien no juega la
    primera.
    """
    holes = sorted(hole_card, key=lambda hole: hole.number)
    # Sin hoyos no hay vuelta que contar. Hay que decirlo explícitamente porque
    # `all()` sobre una lista vacía es cierto, así que un campo sin hoyos
    # devolvería `[]` — que no es `None` y pasaría por vuelta válida de cero
    # hoyos ante quien pregunte `if holes is None`
    if not holes:
        return None

    def all_scored(subset: list) -> bool:
        return all(hole.number in scores_by_hole for hole in subset)

    if all_scored(holes):
        return holes

    if len(scores_by_hole) == HALF_ROUND_HOLES:
        for half in (holes[:HALF_ROUND_HOLES], holes[HALF_ROUND_HOLES:]):
            if len(half) == HALF_ROUND_HOLES and all_scored(half):
                return half

    return None

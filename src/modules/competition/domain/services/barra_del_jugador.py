"""
barra_del_jugador - Desde qué barras juega cada uno (#251, PR 4).

La regla es la de RyderCupAM#165: las barras que eligió en su inscripción
(amarillas si no eligió), valoradas para su género y, si el campo no las tiene
así, las mismas sin género. Nunca las del otro género. Sale de
`MatchPlayersBuilder.resolve_player_data` para que la Ryder y las partidas de
stroke play elijan igual.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.services.tee_lookup import TeeKey, tee_key_for
from src.shared.domain.value_objects.gender import Gender

BARRAS_POR_DEFECTO = TeeColor.YELLOW


@dataclass(frozen=True)
class BarraDelJugador:
    """
    Atributos:
        tee_color: Las barras
        tee_gender: El género con el que están valoradas, o None si sin género
        tee_rating: Su valoración, o None si el campo no las tiene
    """

    tee_color: TeeColor
    tee_gender: Gender | None
    tee_rating: TeeRating | None


def barra_del_jugador(
    de_la_inscripcion: TeeColor | None,
    genero: Gender | None,
    valoradas: Mapping[TeeKey, TeeRating],
) -> BarraDelJugador:
    """
    Args:
        de_la_inscripcion: Las barras que eligió, si eligió
        genero: El del jugador
        valoradas: Las barras del campo por (color, género)
    """
    tee_color = de_la_inscripcion or BARRAS_POR_DEFECTO
    clave = tee_key_for(valoradas, tee_color.value, genero.value if genero else None)
    if clave is None:
        return BarraDelJugador(tee_color, None, None)
    return BarraDelJugador(tee_color, genero if clave[1] is not None else None, valoradas[clave])

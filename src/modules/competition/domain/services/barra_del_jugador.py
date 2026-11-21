"""
barra_del_jugador - Desde qué barras juega cada uno (#251, PR 4).

La regla es la de RyderCupAM#165: las barras que eligió en su inscripción
(si no eligió, las habituales de su género), valoradas para su género y, si el
campo no las tiene así, las mismas sin género. Nunca las del otro género. Sale de
`MatchPlayersBuilder.resolve_player_data` para que la Ryder y las partidas de
stroke play elijan igual.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from src.modules.competition.domain.value_objects.barras_del_campo import BarrasDelCampo
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_GENDER,
    MISSING_TEE_COLOR,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.services.tee_lookup import TeeKey, tee_key_for
from src.shared.domain.value_objects.gender import Gender

# Las habituales de cada género (BE #912, decidido el 20 nov 2026): la misma
# regla que ya usaba el front al crear una partida rápida
# (RyderCupWeb/src/utils/barraPorDefecto.js, FE #1025): amarillas los hombres y
# rojas las mujeres, de su género o mixtas. Sin género, amarillas, como siempre.
# Si el campo no las tiene valoradas se quedan sin valorar y el organizador ve
# el aviso al generar.
BARRAS_HABITUALES = {Gender.MALE: TeeColor.YELLOW, Gender.FEMALE: TeeColor.RED}
BARRAS_SIN_GENERO = TeeColor.YELLOW


def barras_por_defecto(genero: Gender | None) -> TeeColor:
    """Las barras de quien no eligió: las habituales de su género."""
    return BARRAS_SIN_GENERO if genero is None else BARRAS_HABITUALES[genero]


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
    tee_color = de_la_inscripcion or barras_por_defecto(genero)
    clave = tee_key_for(valoradas, tee_color.value, genero.value if genero else None)
    if clave is None:
        return BarraDelJugador(tee_color, None, None)
    return BarraDelJugador(tee_color, genero if clave[1] is not None else None, valoradas[clave])


def barra_sin_golpes(
    de_la_inscripcion: TeeColor | None,
    genero: Gender | None,
    valoradas: Mapping[TeeKey, TeeRating],
    con_tarjeta: Mapping[TeeKey, object],
) -> BarraDelJugador:
    """
    Las barras de quien juega SCRATCH: sin golpes no hace falta que estén
    valoradas, pero su género se busca también entre las que traen tarjeta (P12
    de stroke play). Con él, la tarjeta y el mapa del hoyo son los de su barra
    (en la Ryder, desde RyderCupWeb #880).

    Args:
        con_tarjeta: Las barras del campo con tarjeta, por (color, género)
    """
    barra = barra_del_jugador(de_la_inscripcion, genero, valoradas)
    clave = tee_key_for(con_tarjeta, barra.tee_color.value, genero.value if genero else None)
    if clave is None or clave[1] is None:
        return barra
    return BarraDelJugador(barra.tee_color, genero, barra.tee_rating)


def barra_en_el_campo(
    user_id: UserId,
    general: TeeColor | None,
    genero: Gender | None,
    cambios: BarrasDelCampo,
    valoradas: Mapping[TeeKey, TeeRating],
    con_tarjeta: Mapping[TeeKey, object] | None = None,
) -> BarraDelJugador:
    """
    Desde qué barras juega un jugador en un campo (barras por campo, 20 nov 2026).

    La única regla para todo lo que elige barras (generar, sobres, partidas,
    reasignar, rehacer lo pendiente, el aviso de generar): gana su cambio propio
    en ese campo (R1), si no la del campo para su género (R2), si no su barra
    general (R3, o la habitual de su género). Con ese color, la búsqueda de
    siempre: valoradas para su género o sin género, y en SCRATCH (`con_tarjeta`)
    también las que solo tienen tarjeta. Si el campo no la tiene, se queda sin
    valorar y el organizador ve el aviso (R4): no se elige otra sola.

    Args:
        user_id: El jugador
        general: Su barra general (la de la inscripción), o None
        genero: El del jugador
        cambios: Los cambios de barras de ese campo
        valoradas: Las barras valoradas del campo por (color, género)
        con_tarjeta: En SCRATCH, las barras con tarjeta por (color, género)
    """
    color = cambios.color_de(user_id, general, genero)
    if con_tarjeta is None:
        return barra_del_jugador(color, genero, valoradas)
    return barra_sin_golpes(color, genero, valoradas, con_tarjeta)


def la_barra_vale(
    color: TeeColor,
    genero: Gender | None,
    valoradas: Mapping[TeeKey, TeeRating],
    con_tarjeta: Mapping[TeeKey, object] | None = None,
) -> bool:
    """
    Si el campo tiene esas barras para él: la regla de siempre (`tee_key_for`, de
    su género o sin género, nunca las del otro) entre las valoradas y, en SCRATCH
    (`con_tarjeta`), también entre las que traen tarjeta: sin golpes no hace falta
    valoración. Sin género solo valen las mixtas.

    El único criterio de «tiene barra válida en ese campo»: el del selector y el
    de `GET /enrollments/{id}/tees`, y el del aviso al generar (`lo_que_le_falta`).

    Args:
        con_tarjeta: En SCRATCH, las barras con tarjeta por (color, género)
    """
    barras = set(valoradas) | set(con_tarjeta or {})
    su_genero = genero.value if genero else None
    return tee_key_for(dict.fromkeys(barras), color.value, su_genero) is not None


def lo_que_le_falta(
    barra: BarraDelJugador,
    genero: Gender | None,
    valoradas: Mapping[TeeKey, TeeRating],
    con_tarjeta: Mapping[TeeKey, object] | None = None,
) -> tuple[str, str | None] | None:
    """
    Qué le falta a quien no tiene barras en el campo (BE #360, #361).

    Con golpes, le falta si no están valoradas; en SCRATCH (`con_tarjeta`), si
    tampoco traen tarjeta (`la_barra_vale`): sin ellas no se genera (R4).

    Solo es su género si de verdad no lo tiene y el color existe para alguno: con
    género, lo que falta es su color para él.

    Args:
        con_tarjeta: En SCRATCH, las barras con tarjeta por (color, género)

    Returns:
        None si tiene barras; si no, (clave de lo que falta, color o None)
    """
    if barra.tee_rating is not None:
        return None
    if con_tarjeta is not None and la_barra_vale(barra.tee_color, genero, valoradas, con_tarjeta):
        return None
    existe_el_color = any(
        color == barra.tee_color.value for color, _ in (*valoradas, *(con_tarjeta or {}))
    )
    if existe_el_color and genero is None:
        return MISSING_GENDER, None
    return MISSING_TEE_COLOR, barra.tee_color.value

"""
SinActualizarConLaRfeg - Quién se quedó sin actualizar con la RFEG (15 nov 2026).

Decidido con Agustín el 15 nov 2026 (H1-H6). Al terminar una actualización de
hándicaps, y en cada pasada de una incompleta:

- **Al organizador**, todos los que se quedaron sin actualizar con la RFEG (no
  encontrados, fallidos o sin preguntar todavía) que sean españoles; y si la
  competición es en España, también los demás (sin licencia española), para
  que les ponga el hándicap a mano.
- **Al jugador español al que la RFEG no encontró**, su propio aviso. Si la
  RFEG falló, a él nada: no es cosa suya (H4). A un extranjero, nunca (H6).
- **Solo cuenta lo que dijo la RFEG** (D1, 16 nov 2026): si después la RFEG
  lo encuentra (otra pasada, o lo pide desde su perfil), queda apuntado como
  actualizado y ya no sale (H5). Un hándicap puesto a mano no lo actualiza.
- Quien tiene hándicap personalizado no cuenta: ese lo puso el organizador.
- Quien entró después de una actualización completa no cuenta en ella (T4):
  nadie le preguntó porque llegó tarde, no porque falte.
- A quien no es un no encontrado se le retira su aviso, si lo tenía (D3).

Aquí solo la decisión, sin red ni base de datos.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Intento,
    ResultadoRefresco,
)
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class Inscrito:
    """Un inscrito, con lo que decide si se quedó sin actualizar."""

    user_id: UserId
    handicap_personalizado: bool
    # Si el usuario sigue existiendo: a uno borrado no hay a quién nombrar
    existe: bool
    # Nacionalidad española en su perfil (`country_code == "ES"`)
    espanol: bool


@dataclass(frozen=True)
class SinActualizar:
    """Lo que sale de una actualización, en el orden de las inscripciones."""

    # La lista del organizador (H2)
    para_el_organizador: list[UserId]
    # Los españoles a los que la RFEG no encontró, que reciben su aviso (H3)
    no_encontrados: list[UserId]
    # Los demás inscritos: si tenían el aviso de no encontrado, se les retira (D3)
    sin_aviso: list[UserId]


def sin_actualizar(
    inscritos: Iterable[Inscrito],
    resultados: Mapping[UserId, Intento],
    *,
    en_espana: bool,
    completa: bool,
) -> SinActualizar:
    """
    Args:
        inscritos: Los inscritos de la competición, en orden
        resultados: Lo apuntado por cada uno en la actualización
        en_espana: Si el país principal de la competición es España
        completa: Si la actualización terminó completa: quien no tiene respuesta
            en ella entró después (T4)
    """
    para_el_organizador: list[UserId] = []
    no_encontrados: list[UserId] = []
    sin_aviso: list[UserId] = []
    for inscrito in inscritos:
        if not inscrito.existe:
            continue
        intento = resultados.get(inscrito.user_id)
        if (
            not inscrito.handicap_personalizado
            and inscrito.espanol
            and intento is not None
            and intento.resultado is ResultadoRefresco.NO_ENCONTRADO
        ):
            no_encontrados.append(inscrito.user_id)
        else:
            sin_aviso.append(inscrito.user_id)
        if (
            inscrito.handicap_personalizado
            or (intento is None and completa)
            or (intento is not None and intento.resultado is ResultadoRefresco.ACTUALIZADO)
        ):
            continue
        if inscrito.espanol or en_espana:
            para_el_organizador.append(inscrito.user_id)
    return SinActualizar(
        para_el_organizador=para_el_organizador,
        no_encontrados=no_encontrados,
        sin_aviso=sin_aviso,
    )

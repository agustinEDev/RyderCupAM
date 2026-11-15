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
- **Lo actualizado después ya no cuenta** (H5): si su hándicap se actualizó
  después de la respuesta de la RFEG (lo pidió desde su perfil, o una pasada
  posterior lo encontró), ya no está sin actualizar.
- Quien tiene hándicap personalizado no cuenta: ese lo puso el organizador.

Aquí solo la decisión, sin red ni base de datos.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

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
    # Cuándo se actualizó su hándicap por última vez (UTC)
    actualizado_en: datetime | None


@dataclass(frozen=True)
class SinActualizar:
    """Lo que sale de una actualización, en el orden de las inscripciones."""

    # La lista del organizador (H2)
    para_el_organizador: list[UserId]
    # Los españoles a los que la RFEG no encontró, que reciben su aviso (H3)
    no_encontrados: list[UserId]


def sin_actualizar(
    inscritos: Iterable[Inscrito],
    resultados: Mapping[UserId, Intento],
    *,
    en_espana: bool,
    desde: datetime,
) -> SinActualizar:
    """
    Args:
        inscritos: Los inscritos de la competición, en orden
        resultados: Lo apuntado por cada uno en la actualización
        en_espana: Si el país principal de la competición es España
        desde: Cuándo se creó la actualización: para quien no tiene respuesta,
            lo actualizado después ya no cuenta
    """
    para_el_organizador: list[UserId] = []
    no_encontrados: list[UserId] = []
    for inscrito in inscritos:
        if inscrito.handicap_personalizado or not inscrito.existe:
            continue
        intento = resultados.get(inscrito.user_id)
        if intento is not None and intento.resultado is ResultadoRefresco.ACTUALIZADO:
            continue
        referencia = intento.momento if intento is not None and intento.momento else desde
        if inscrito.actualizado_en is not None and inscrito.actualizado_en > referencia:
            continue
        if inscrito.espanol or en_espana:
            para_el_organizador.append(inscrito.user_id)
        if (
            inscrito.espanol
            and intento is not None
            and intento.resultado is ResultadoRefresco.NO_ENCONTRADO
        ):
            no_encontrados.append(inscrito.user_id)
    return SinActualizar(para_el_organizador=para_el_organizador, no_encontrados=no_encontrados)

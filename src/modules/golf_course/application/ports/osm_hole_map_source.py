"""
Puerto: de dónde sale el mapa de hoyos de un campo en OpenStreetMap (BE #532).

Encontrar en OSM qué contorno es nuestro campo y qué hoyos suyos valen necesita
geometría (`shapely`) y la red (Overpass): es infraestructura, y el caso de uso
solo ve este contrato.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole


class OsmUnavailableError(Exception):
    """OSM no ha respondido o ha respondido algo ilegible: se reintenta otro día."""


class DiscardReason(StrEnum):
    """Por qué un hoyo de OSM no entra en el mapa."""

    NO_NUMBER = "NO_NUMBER"  # sin ref, o un ref que no es un número de 1 a 18
    BEYOND_COURSE = "BEYOND_COURSE"  # número mayor que los hoyos del campo
    PAR_MISMATCH = "PAR_MISMATCH"  # par de OSM distinto del de nuestra tarjeta
    AMBIGUOUS = "AMBIGUOUS"  # número repetido que par y hándicap no distinguen


@dataclass(frozen=True)
class CardHole:
    """Un hoyo de nuestra tarjeta, contra el que se valida lo que trae OSM."""

    number: int
    par: int
    stroke_index: int


@dataclass(frozen=True)
class OsmHoleMapCandidate:
    """
    Lo que OSM tiene del campo, ya validado contra nuestra tarjeta.

    `holes` puede estar vacío: hay contorno, pero ningún hoyo vale. `discarded`
    cuenta los que quedaron fuera por cada motivo (AMBIGUOUS, una vez por
    número de hoyo; los demás, una vez por hoyo de OSM).
    """

    osm_reference: str
    holes: tuple[MappedHole, ...]
    discarded: Mapping[DiscardReason, int] = field(default_factory=dict)


class IOsmHoleMapSource(ABC):
    """Busca en OSM el mapa de hoyos de un campo."""

    @abstractmethod
    async def find(
        self,
        *,
        latitude: float,
        longitude: float,
        card: Sequence[CardHole],
        physical_holes: int,
    ) -> OsmHoleMapCandidate | None:
        """
        El candidato del campo en esa coordenada, o None si OSM no tiene su contorno.

        Raises:
            OsmUnavailableError: si OSM no responde o responde algo ilegible
        """
        raise NotImplementedError

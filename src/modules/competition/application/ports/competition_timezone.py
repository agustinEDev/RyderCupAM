"""
Puerto: de donde sale la zona horaria de una competicion (BE #319).

Las inscripciones se abren a una hora LOCAL del campo donde se juega — «las
nueve» son las nueve de alli—, asi que hace falta saber en que huso esta. La
zona sale de las coordenadas del campo, no del pais: tres puntos espanoles dan
`Europe/Madrid`, `Atlantic/Canary` y `Africa/Ceuta` (BE #305).

Es un puerto y no una consulta suelta porque llegar al campo cruza modulos: la
competicion guarda su identificador, y la zona vive en `golf_course`.
"""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.competition import Competition


class ICompetitionTimezone(ABC):
    """Dice en que huso se juega una competicion."""

    @abstractmethod
    async def for_competition(self, competition: Competition) -> str | None:
        """
        La zona IANA del primer campo que se juega, o `None` si no se sabe.

        Devolver `None` es una respuesta valida y esperada: una competicion sin
        campo todavia —se puede crear, invitar y anadirlo despues— no tiene
        zona, y entonces la apertura programada espera en vez de adivinar.
        """
        raise NotImplementedError

"""
Puerto: de dónde sale la zona horaria de un campo de golf (BE #305).

La anotación de un partido se abre a una hora LOCAL del campo, así que hace
falta saber en qué huso está. El país no vale —España tiene dos, y también
Estados Unidos, Chile o Australia—, pero la ubicación sí: 792 de los 805 campos
que hay traen coordenadas de la RFEG.

Es un puerto y no una función suelta porque resolverlo necesita la base de datos
de husos del mundo, que es infraestructura: los casos de uso no la importan.
"""

from abc import ABC, abstractmethod


class ITimezoneResolver(ABC):
    """Traduce unas coordenadas a su zona horaria IANA."""

    @abstractmethod
    def for_coordinates(self, latitude: float | None, longitude: float | None) -> str | None:
        """
        La zona horaria de ese punto, o `None` si no se puede determinar.

        Devolver `None` es una respuesta válida y esperada: un campo sin zona no
        abre la anotación sola —sigue necesitando START— y la pantalla de la
        competición lo avisa. Nunca se adivina, porque adivinar mal abre la
        anotación a deshora.
        """
        raise NotImplementedError

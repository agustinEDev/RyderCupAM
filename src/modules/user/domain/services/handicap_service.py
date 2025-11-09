"""
Handicap Service Interface - Domain Layer

Define el contrato para servicios de búsqueda de hándicap.
Similar a PasswordHasher, esta es una abstracción que vive en el dominio
pero se implementa en infraestructura.
"""

from abc import ABC, abstractmethod
from typing import Optional


class HandicapService(ABC):
    """
    Servicio de dominio para búsqueda de hándicap.

    Define el contrato que debe cumplir cualquier implementación.
    Esto permite tener múltiples implementaciones (RFEG, EGA, Mock)
    sin que el dominio dependa de detalles de infraestructura.

    Implementaciones esperadas:
    - RFEGHandicapService: Busca en la API de la RFEG
    - MockHandicapService: Para testing
    """

    @abstractmethod
    async def search_handicap(self, full_name: str) -> Optional[float]:
        """
        Busca el hándicap de un jugador por su nombre completo.

        Args:
            full_name: Nombre completo del jugador (ej: "Juan Pérez García")

        Returns:
            El hándicap si se encuentra, None si no existe.

        Raises:
            HandicapServiceError: Si hay un error en la búsqueda.
            HandicapServiceUnavailableError: Si el servicio no está disponible.
        """
        pass

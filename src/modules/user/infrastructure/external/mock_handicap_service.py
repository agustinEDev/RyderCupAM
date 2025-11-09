"""
Mock Handicap Service - Infrastructure Layer

Implementación mock del servicio de hándicap para testing.
Permite configurar respuestas predefinidas sin hacer llamadas HTTP reales.
"""

from typing import Optional, Dict

from src.modules.user.domain.services.handicap_service import HandicapService


class MockHandicapService(HandicapService):
    """
    Implementación mock para testing.

    Permite configurar un diccionario de nombres -> hándicaps
    para simular diferentes escenarios de prueba sin depender
    del servicio externo de la RFEG.

    Examples:
        >>> # Crear mock con hándicaps específicos
        >>> service = MockHandicapService(
        ...     handicaps={"Juan Pérez": 15.0, "María García": 20.5}
        ... )
        >>> await service.search_handicap("Juan Pérez")
        15.0

        >>> # Crear mock con hándicap por defecto
        >>> service = MockHandicapService(default=18.0)
        >>> await service.search_handicap("Cualquier Nombre")
        18.0
    """

    def __init__(
        self,
        handicaps: Optional[Dict[str, float]] = None,
        default: Optional[float] = 15.0
    ):
        """
        Inicializa el servicio mock.

        Args:
            handicaps: Diccionario de nombre completo -> hándicap
            default: Hándicap por defecto si el nombre no está en el diccionario
                    Si es None, devuelve None cuando no encuentra el nombre
        """
        self._handicaps = handicaps or {}
        self._default = default

    async def search_handicap(self, full_name: str) -> Optional[float]:
        """
        Devuelve el hándicap configurado para ese nombre.

        Args:
            full_name: Nombre completo del jugador

        Returns:
            Hándicap del jugador si está configurado,
            el valor por defecto si no está, o None
        """
        return self._handicaps.get(full_name, self._default)

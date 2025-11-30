"""
Update Multiple Handicaps Use Case - Application Layer

Caso de uso para actualizar hándicaps de múltiples usuarios.
Útil para actualizar todos los participantes de una competición.
"""

import logging

from src.modules.user.domain.errors.handicap_errors import HandicapServiceError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)



class UpdateMultipleHandicapsUseCase:
    """
    Caso de uso para actualizar hándicaps de múltiples usuarios.

    Útil para:
    - Actualizar todos los participantes de una competición antes de iniciarla
    - Actualizar jugadores de un partido antes de comenzar
    - Actualizaciones masivas programadas

    El proceso actualiza todos los usuarios en una sola transacción,
    pero si un usuario falla, continúa con los demás.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        handicap_service: HandicapService
    ):
        """
        Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para gestionar transacciones
            handicap_service: Servicio para buscar hándicaps
        """
        self._uow = uow
        self._handicap_service = handicap_service

    async def execute(self, user_ids: list[UserId]) -> dict[str, int]:
        """
        Actualiza los hándicaps de múltiples usuarios.

        Args:
            user_ids: Lista de IDs de usuarios a actualizar

        Returns:
            Diccionario con estadísticas de la operación:
            {
                'total': int,              # Total de usuarios procesados
                'updated': int,            # Usuarios actualizados exitosamente
                'not_found': int,          # Usuarios no encontrados en BD
                'no_handicap_found': int,  # Usuarios encontrados pero sin hándicap en RFEG
                'errors': int              # Errores al buscar hándicap
            }

        Note:
            Todos los cambios se persisten en una sola transacción.
            Si hay errores individuales, continúa con los demás usuarios.
        """
        stats = {
            'total': len(user_ids),
            'updated': 0,
            'not_found': 0,
            'no_handicap_found': 0,
            'errors': 0
        }

        async with self._uow:
            for user_id in user_ids:
                # 1. Buscar usuario
                user = await self._uow.users.find_by_id(user_id)
                if not user:
                    stats['not_found'] += 1
                    continue

                # 2. Intentar actualizar hándicap
                try:
                    handicap_value = await self._handicap_service.search_handicap(
                        user.get_full_name()
                    )

                    if handicap_value is not None:
                        user.update_handicap(handicap_value)
                        await self._uow.users.save(user)
                        stats['updated'] += 1
                    else:
                        # Hándicap no encontrado en RFEG (respuesta válida)
                        stats['no_handicap_found'] += 1
                        logger.info("No se encontró hándicap en RFEG para %s", user.get_full_name())

                except HandicapServiceError as e:
                    stats['errors'] += 1
                    logger.error("Error actualizando hándicap para %s: %s", user.get_full_name(), e)

            # El context manager (__aexit__) hace commit automático al final (transacción única)

        return stats

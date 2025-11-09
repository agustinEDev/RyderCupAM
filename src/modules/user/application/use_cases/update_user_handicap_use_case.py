"""
Update User Handicap Use Case - Application Layer

Caso de uso para actualizar el hándicap de un usuario individual.
"""

from typing import Optional

from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.repositories.user_unit_of_work_interface import UserUnitOfWorkInterface
from src.modules.user.domain.errors.handicap_errors import HandicapServiceError
from src.modules.user.application.dto.user_dto import UserResponseDTO


class UpdateUserHandicapUseCase:
    """
    Caso de uso para actualizar el hándicap de un usuario.

    Este caso de uso es reutilizable en diferentes contextos:
    - Registro inicial de usuario
    - Actualización manual
    - Actualización masiva antes de competiciones
    - Actualización antes de iniciar partidos

    El flujo es:
    1. Buscar el usuario en el repositorio
    2. Consultar el hándicap en el servicio externo
    3. Actualizar el usuario (emitiendo evento de dominio)
    4. Persistir los cambios
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

    async def execute(
        self,
        user_id: UserId,
        manual_handicap: Optional[float] = None
    ) -> Optional[UserResponseDTO]:
        """
        Busca y actualiza el hándicap de un usuario.

        Args:
            user_id: ID del usuario a actualizar
            manual_handicap: Hándicap manual opcional. Se usa si RFEG no devuelve resultado.

        Returns:
            DTO del usuario actualizado o None si no existe

        Note:
            No lanza excepciones si el servicio de hándicap falla.
            Registra el error y devuelve el usuario sin cambios.
        """
        async with self._uow:
            # 1. Obtener el usuario
            user = await self._uow.users.find_by_id(user_id)
            if not user:
                return None

            # 2. Buscar hándicap usando el servicio
            handicap_value = None
            try:
                handicap_value = await self._handicap_service.search_handicap(
                    user.get_full_name()
                )
            except HandicapServiceError as e:
                # Log del error pero no falla
                # TODO: Agregar logging apropiado cuando esté configurado
                print(f"Error buscando hándicap para {user.get_full_name()}: {e}")

            # 3. Si no se encontró en RFEG, usar hándicap manual si fue proporcionado
            if handicap_value is None and manual_handicap is not None:
                handicap_value = manual_handicap

            # 4. Actualizar si se obtuvo un hándicap (de RFEG o manual)
            if handicap_value is not None:
                user.update_handicap(handicap_value)

                # 5. Persistir cambios
                await self._uow.users.save(user)
                await self._uow.commit()

            return UserResponseDTO.model_validate(user)

"""
Caso de Uso: Reordenar Campos de Golf en Competición.

Permite cambiar el orden de visualización de los campos de golf asociados a una competición.
Solo el creador puede realizar esta acción.
"""

from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    ReorderGolfCoursesRequestDTO,
    ReorderGolfCoursesResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotFoundError(Exception):
    """Excepción lanzada cuando la competición no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """Excepción lanzada cuando el usuario no es el creador de la competición."""

    pass


class CompetitionNotDraftError(Exception):
    """Excepción lanzada cuando la competición no está en estado DRAFT."""

    pass


class InvalidReorderError(Exception):
    """Excepción lanzada cuando el reorden no es válido (IDs missing, duplicates, etc.)."""

    pass


class ReorderGolfCoursesUseCase:
    """
    Caso de uso para reordenar los campos de golf de una competición.

    Restricciones:
    - La competición debe estar en estado DRAFT
    - Solo el creador puede reordenar campos
    - La lista de IDs debe incluir TODOS los campos actualmente asociados
    - No puede haber duplicados en la lista
    - Todos los IDs deben existir en la competición

    Orquesta:
    1. Buscar la competición por ID
    2. Verificar que el usuario sea el creador
    3. Verificar que esté en estado DRAFT
    4. Convertir UUIDs a GolfCourseId
    5. Reordenar campos (validación de integridad en el dominio)
    6. Guardar la competición actualizada
    7. Commit de la transacción
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones de Competition
        """
        self._uow = uow

    async def execute(
        self, request: ReorderGolfCoursesRequestDTO, user_id: UserId
    ) -> ReorderGolfCoursesResponseDTO:
        """
        Ejecuta el caso de uso de reordenar campos de golf.

        Args:
            request: DTO con competition_id y lista ordenada de golf_course_ids
            user_id: ID del usuario que solicita la operación

        Returns:
            DTO con confirmación de reordenación

        Raises:
            CompetitionNotFoundError: Si la competición no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotDraftError: Si la competición no está en estado DRAFT
            InvalidReorderError: Si la lista de IDs no es válida (duplicados, missing, extra)
        """
        async with self._uow:
            # 1. Buscar la competición
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el creador puede reordenar campos de golf de la competición"
                )

            # 3. Verificar que esté en estado DRAFT
            if not competition.is_draft():
                raise CompetitionNotDraftError(
                    f"Solo se pueden reordenar campos en estado DRAFT. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Convertir UUIDs a tuplas (GolfCourseId, display_order)
            # El orden en la lista determina el display_order (índice + 1)
            new_order = [
                (GolfCourseId(uuid), idx + 1) for idx, uuid in enumerate(request.golf_course_ids)
            ]

            # 5. Validar que todos los campos existen y no hay duplicados
            if len(new_order) != len(competition._golf_courses):
                raise InvalidReorderError(
                    f"Debes especificar el orden para todos los campos. "
                    f"Esperados: {len(competition._golf_courses)}, Recibidos: {len(new_order)}"
                )

            # Validar que todos los IDs existen en la competición
            competition_gc_ids = {cgc.golf_course_id for cgc in competition._golf_courses}
            new_order_ids = {gc_id for gc_id, _ in new_order}
            if competition_gc_ids != new_order_ids:
                raise InvalidReorderError(
                    "La lista de IDs no coincide con los campos actuales de la competición"
                )

            # 6. Reordenar en dos fases para evitar violaciones de UNIQUE constraint
            # Fase 1: Asignar valores temporales altos (10000+) que no colisionan con 1-N
            for idx, (golf_course_id, _) in enumerate(new_order):
                for cgc in competition._golf_courses:
                    if cgc.golf_course_id == golf_course_id:
                        cgc._display_order = 10000 + idx + 1  # 10001, 10002, 10003, etc.
                        break

            # Flush para persistir valores temporales antes de asignar los finales
            await self._uow.flush()

            # Fase 2: Asignar valores finales (1, 2, 3...) usando change_order() para respetar business rules
            for golf_course_id, new_display_order in new_order:
                for cgc in competition._golf_courses:
                    if cgc.golf_course_id == golf_course_id:
                        cgc.change_order(new_display_order)
                        break

            competition.updated_at = datetime.now()

            # 7. Guardar la competición actualizada
            await self._uow.competitions.update(competition)

        # 8. Construir respuesta
        return ReorderGolfCoursesResponseDTO(
            competition_id=request.competition_id,
            golf_course_count=len(new_order),
            reordered_at=datetime.now(),
        )

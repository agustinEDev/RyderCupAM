"""
Caso de Uso: Elegir Alias o Nombre Real en una Competición (Set Name Preference).

Permite al propio jugador decidir si esta competición le muestra por su
alias o por su nombre legal (BE #254).
"""

from src.modules.competition.application.dto.enrollment_dto import (
    SetNamePreferenceRequestDTO,
    SetNamePreferenceResponseDTO,
)
from src.modules.competition.application.exceptions import EnrollmentNotFoundError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.user.domain.value_objects.user_id import UserId


class NotOwnerError(Exception):
    """Excepción lanzada cuando el usuario no es el dueño de la inscripción."""

    pass


class SetNamePreferenceUseCase:
    """
    Caso de uso para elegir cómo se muestra el nombre en una competición.

    Orquesta:
    1. Validación de existencia del enrollment
    2. Validación de que el solicitante es el DUEÑO de la inscripción
    3. Establecer la preferencia
    4. Persistencia mediante UoW

    Reglas de negocio:
    - Solo el propio jugador decide cómo se le muestra — a diferencia del
      hándicap personalizado, que decide el creador, aquí decide el dueño
    - Se puede cambiar en cualquier estado de la competición, torneo en
      marcha incluido: quien se equivocó al elegir no tiene que esperar a
      que acabe para corregirlo. Es una decisión de producto, no una
      omisión — el precedente del hándicap (congelado tras IN_PROGRESS) se
      consideró y se descartó a propósito para esta preferencia
    - En partida rápida el alias se sigue enseñando siempre: esto es
      exclusivo de las competiciones
    - No hace falta comprobar que la competición exista: la clave foránea
      de `enrollments.competition_id` es `ON DELETE CASCADE`, así que un
      enrollment nunca sobrevive a su competición
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, request: SetNamePreferenceRequestDTO, user_id: UserId
    ) -> SetNamePreferenceResponseDTO:
        """
        Ejecuta el caso de uso de elegir la preferencia de nombre.

        Args:
            request: DTO con enrollment_id y use_real_name
            user_id: ID del usuario que ejecuta la acción (debe ser el dueño)

        Returns:
            DTO con los datos actualizados

        Raises:
            EnrollmentNotFoundError: Si la inscripción no existe
            NotOwnerError: Si el solicitante no es el dueño de la inscripción
        """
        async with self._uow:
            enrollment_id = EnrollmentId(request.enrollment_id)

            # 1. Obtener enrollment
            enrollment = await self._uow.enrollments.find_by_id(enrollment_id)
            if not enrollment:
                raise EnrollmentNotFoundError(f"Inscripción no encontrada: {request.enrollment_id}")

            # 2. Verificar que es el dueño
            if enrollment.user_id != user_id:
                raise NotOwnerError("Solo puedes elegir cómo se te muestra en tu propia inscripción")

            # 3. Establecer preferencia
            enrollment.set_name_preference(request.use_real_name)

            # 4. Persistir cambios
            await self._uow.enrollments.update(enrollment)

        return SetNamePreferenceResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            use_real_name=enrollment.use_real_name,
            updated_at=enrollment.updated_at,
        )

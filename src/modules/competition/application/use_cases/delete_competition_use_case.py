"""
Caso de Uso: Eliminar Competition (eliminacion fisica).

Permite eliminar fisicamente una competicion mientras no este ya montada:
el estado tiene que permitirlo (DRAFT, ACTIVE o CANCELLED) y no puede haber
ni calendario ni equipos sorteados.
Solo el creador o un administrador pueden realizar esta accion.
"""

from datetime import datetime

from src.modules.competition.application.dto.competition_dto import (
    DeleteCompetitionRequestDTO,
    DeleteCompetitionResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotDeletableError(Exception):
    """Excepcion lanzada cuando la competicion ya no se puede borrar."""

    pass


class DeleteCompetitionUseCase:
    """
    Caso de uso para eliminar fisicamente una competicion.

    Restricciones:
    - Solo si el estado lo permite y el torneo no esta ya montado (BE #333)
    - Solo el creador puede eliminar
    - Se elimina permanentemente de la BD (incluyendo enrollments si existieran)

    Orquesta:
    1. Buscar la competicion por ID
    2. Verificar que el usuario sea el creador
    3. Verificar que todavia se pueda borrar
    4. Eliminar la competicion del repositorio
    5. Commit de la transaccion
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: DeleteCompetitionRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> DeleteCompetitionResponseDTO:
        """
        Ejecuta el caso de uso de eliminacion de competicion.

        Args:
            request: DTO con el ID de la competicion a eliminar
            user_id: ID del usuario que solicita la eliminacion

        Returns:
            DTO con confirmacion de eliminacion

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            NotCompetitionCreatorError: Si el usuario no es el creador
            CompetitionNotDeletableError: Si la competicion ya no se puede borrar
        """
        async with self._uow:
            # 1. Buscar la competicion
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede eliminar la competicion")

            # 3. Verificar que todavia se pueda borrar. Las dos mitades se
            #    comprueban por separado para poder decir cual falla: el front
            #    ensena este texto tal cual, y «sin calendario» cuando lo que
            #    sobra es el estado manda al creador a arreglar lo que no es
            if not competition.status.allows_deletion():
                raise CompetitionNotDeletableError(
                    f"Solo se pueden eliminar competiciones mientras las inscripciones "
                    f"siguen abiertas, o si están canceladas. "
                    f"Estado actual: {competition.status.value}"
                )

            # El montaje se consulta porque el estado se puede andar hacia atras
            # sin deshacerlo: un torneo ya preparado puede estar de vuelta en
            # ACTIVE, y la cascada se llevaria calendario, equipos y golpes
            montada = await self._ya_montada(competition_id)
            if not competition.allows_deletion(already_set_up=montada):
                raise CompetitionNotDeletableError(
                    "No se puede eliminar una competición que ya tiene calendario "
                    "o equipos sorteados. Se perderían con ella."
                )

            # 4. Guardar datos para el response antes de eliminar
            competition_id_value = competition.id.value
            competition_name = str(competition.name)

            # 5. Eliminar la competicion
            await self._uow.competitions.delete(competition_id)

        # 7. Retornar DTO de respuesta
        return DeleteCompetitionResponseDTO(
            id=competition_id_value,
            name=competition_name,
            deleted=True,
            deleted_at=datetime.now(),
        )

    async def _ya_montada(self, competition_id: CompetitionId) -> bool:
        """Indica si el torneo llego a prepararse, aunque hoy no lo parezca.

        Dos rastros, y basta con uno: el calendario y el sorteo de equipos. Los
        dos se hacen en CLOSED y ninguna vuelta atras los deshace, asi que
        cualquiera de ellos delata que este torneo paso de ahi. Sortear equipos
        no exige tener rondas, de modo que mirar solo el calendario dejaria el
        sorteo desprotegido.

        El calendario primero porque es lo mas comun: si hay rondas no hace
        falta preguntar por los equipos.
        """
        if await self._uow.rounds.find_by_competition(competition_id):
            return True
        return await self._uow.team_assignments.find_by_competition(competition_id) is not None

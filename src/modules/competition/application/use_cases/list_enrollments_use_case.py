"""
Caso de Uso: Listar Inscripciones (List Enrollments).

Lista las inscripciones de una competicion que puede ver quien pide.
Retorna entidades (NO DTOs) - siguiendo Clean Architecture.
"""

from dataclasses import dataclass

from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.competition.application.services.quien_ve_los_inscritos import (
    Alcance,
    alcance_de,
    lo_que_ve,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Desde que se cierran las inscripciones, el hándicap de cada uno está fijado (#251)
HANDICAP_FIJADO = frozenset(
    {CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS, CompetitionStatus.COMPLETED}
)


@dataclass(frozen=True)
class ListaDeInscritos:
    """Lo que ve quien pide la lista de inscritos (BE #531)."""

    enrollments: list[Enrollment]
    categorias: dict[UserId, int | None]
    # El organizador y los admin ven todos los correos; el resto, solo el suyo
    ve_todos_los_correos: bool


class ListEnrollmentsUseCase:
    """
    Caso de uso para listar inscripciones de una competicion.

    CLEAN ARCHITECTURE: Este use case retorna ENTIDADES de dominio, NO DTOs.
    La conversion a DTOs es responsabilidad de la capa de presentacion (API Layer).

    Un solo punto de entrada, y exige saber quién pide: no hay forma de listar
    sin aplicar quién ve qué (BE #531).
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface, amigos: AmigosInterface | None = None):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
            amigos: De quién es amigo quien mira (release social 2). Sin él,
                no ve a ningún amigo
        """
        self._uow = uow
        self._amigos = amigos

    async def execute(
        self,
        competition_id: str,
        status: EnrollmentStatus | None = None,
        *,
        viewer_id: UserId,
        viewer_is_admin: bool = False,
        viewer_email: str | None = None,
    ) -> ListaDeInscritos:
        """
        Las inscripciones que puede ver quien pide, si ve todos los correos y,
        en un stroke play con el hándicap ya fijado (desde que se cierran las
        inscripciones), la categoría fijada de cada aprobado.

        Quién ve qué (BE #531 y release social 2): el organizador y los admin,
        todas las filas y todos los correos; cualquier otro, sus propias filas
        (en el estado que estén), solo su propio correo, y de los aprobados los
        que le deje `quien_ve_los_inscritos`: todos, sus amigos o ninguno. El
        filtro de estado va encima.

        La categoría se fijó al cerrar, con la regla de los seis: aquí solo se
        lee, y no se mueve aunque alguien se retire (#251).

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
        """
        async with self._uow:
            comp_id = CompetitionId(competition_id)
            competition = await self._uow.competitions.find_by_id(comp_id)
            if not competition:
                raise CompetitionNotFoundError(f"Competicion no encontrada: {competition_id}")
            if status:
                enrollments = await self._uow.enrollments.find_by_competition_and_status(
                    comp_id, status
                )
            else:
                enrollments = await self._uow.enrollments.find_by_competition(comp_id)
            alcance = await alcance_de(
                self._uow, competition, viewer_id, es_admin=viewer_is_admin, email=viewer_email
            )

        ve_todo = alcance is Alcance.TODO
        if not ve_todo:
            ve = await lo_que_ve(alcance, viewer_id, self._amigos)
            enrollments = [
                e
                for e in enrollments
                if e.user_id == viewer_id
                or (e.status is EnrollmentStatus.APPROVED and ve.ve_a(e.user_id))
            ]

        categorias: dict[UserId, int | None] = {}
        if competition.stroke_play is not None and competition.status in HANDICAP_FIJADO:
            categorias = {
                e.user_id: e.fixed_category
                for e in enrollments
                if e.status is EnrollmentStatus.APPROVED
            }
        return ListaDeInscritos(enrollments, categorias, ve_todos_los_correos=ve_todo)

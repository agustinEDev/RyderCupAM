"""
Caso de Uso: Eliminar Competition (eliminacion fisica).

Permite eliminar fisicamente una competicion mientras no se haya jugado nada:
el estado tiene que permitirlo (todos menos IN_PROGRESS y COMPLETED) y no puede
haber un partido terminado ni un hoyo anotado. El calendario no cuenta.
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
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.user.domain.value_objects.user_id import UserId


class CompetitionNotDeletableError(Exception):
    """Excepcion lanzada cuando la competicion ya no se puede borrar."""

    pass


class DeleteCompetitionUseCase:
    """
    Caso de uso para eliminar fisicamente una competicion.

    Restricciones:
    - Solo si el estado lo permite y no hay nada jugado (BE #333, #347)
    - Solo el creador o un administrador pueden eliminar
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
            # 1. Buscar la competicion, con la fila bloqueada. Entre comprobar
            #    que no hay nada jugado y borrar caben milisegundos, y en READ
            #    COMMITTED leer no reserva nada: una ronda creada a la vez desde
            #    otra pestana se colaba y se iba en cascada sin que nadie lo
            #    supiera. Mismo bloqueo que usa handle_enrollment para el cupo.
            #    Anotar, conceder o terminar no pasan por esta fila: de eso se
            #    encarga `_tiene_algo_jugado(bloquear=True)`
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar que el usuario sea el creador
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede eliminar la competicion")

            # 3. Verificar que todavia se pueda borrar. Las dos mitades se
            #    comprueban por separado para poder decir cual falla: el front
            #    ensena este texto tal cual
            if not competition.status.allows_deletion():
                raise CompetitionNotDeletableError(
                    f"No se puede eliminar una competición en juego o terminada. "
                    f"Estado actual: {competition.status.value}"
                )

            # Lo jugado se consulta porque el estado se puede andar hacia atras
            # sin deshacerlo: un torneo ya jugado puede estar de vuelta en
            # ACTIVE, y la cascada se llevaria sus partidos y sus golpes
            jugado = await self._tiene_algo_jugado(competition_id, bloquear=True)
            if not competition.allows_deletion(has_played=jugado):
                raise CompetitionNotDeletableError(
                    "No se puede eliminar una competición con partidos jugados o "
                    "golpes anotados: se irían con ella."
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

    async def puede_borrar(
        self, competition_id: CompetitionId, user_id: UserId, is_admin: bool = False
    ) -> bool:
        """Indica si ese usuario podría borrar la competición ahora (BE #347).

        La ficha lo necesita para enseñar o no el botón. Son las mismas tres
        comprobaciones que `execute` —quién, el estado y lo jugado— y con las
        mismas piezas, pero contestando sí o no en vez de lanzar el error que
        diga cuál falla. Que las dos digan siempre lo mismo lo vigila una tabla
        de equivalencia en los tests. No bloquea la fila: es una pregunta.

        Args:
            competition_id: La competición
            user_id: Quién pregunta
            is_admin: Si es administrador

        Returns:
            True si `execute` la borraría ahora mismo para ese usuario
        """
        async with self._uow:
            competition = await self._uow.competitions.find_by_id(competition_id)
            if not competition:
                return False
            if not is_admin and not competition.is_creator(user_id):
                return False
            # Se ve en todas las fichas: si el estado ya dice que no, sin
            # recorrer el calendario
            if not competition.status.allows_deletion():
                return False
            return competition.allows_deletion(
                has_played=await self._tiene_algo_jugado(competition_id)
            )

    async def _tiene_algo_jugado(
        self, competition_id: CompetitionId, bloquear: bool = False
    ) -> bool:
        """Indica si el torneo llego a jugarse, aunque sea un hoyo (BE #347).

        Es lo unico que hay que proteger aqui: se protege lo jugado, no lo
        montado (decidido con el dueno del producto el 21 y 22 sep). Un
        calendario sin jugar o un sorteo de equipos se rehacen; un golpe no.

        Jugado es un partido terminado —con resultado, walkover o concedido,
        aunque no tenga golpes— o un hoyo anotado en uno abierto. Tener tarjetas
        no basta: se crean vacias al abrir el partido, y la anotacion se abre
        sola a la hora de la sesion (BE #305) sin que nadie haya jugado. Los
        partidos SCHEDULED no se miran: sus tarjetas nacen al empezar, y nada
        devuelve un partido a SCHEDULED.

        Con `bloquear`, que usa el borrado, partidos y tarjetas se leen con su
        fila bloqueada: anotar un hoyo en un partido abierto, conceder o
        terminar no bloquean la competicion. Si el golpe llega antes, el borrado
        lo espera y lo ve; si llega despues, ya no encuentra la fila. Primero
        los partidos y luego sus tarjetas, el mismo orden en que la anotacion
        escribe. La pregunta de la ficha no bloquea: retendria a quien anota.
        """
        partidos_de = (
            self._uow.matches.find_by_round_for_update
            if bloquear
            else self._uow.matches.find_by_round
        )
        tarjetas_de = (
            self._uow.hole_scores.find_by_match_for_update
            if bloquear
            else self._uow.hole_scores.find_by_match
        )
        for ronda in await self._uow.rounds.find_by_competition(competition_id):
            for partido in await partidos_de(ronda.id):
                if partido.status.is_finished():
                    return True
                if partido.status == MatchStatus.IN_PROGRESS:
                    tarjetas = await tarjetas_de(partido.id)
                    if any(tarjeta.is_recorded for tarjeta in tarjetas):
                        return True
        return False

"""Tests para DeleteCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    DeleteCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    CompetitionNotDeletableError,
    DeleteCompetitionUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    montar_calendario,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestDeleteCompetitionUseCase:
    """Suite de tests para el caso de uso DeleteCompetitionUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    @pytest.fixture
    def other_user_id(self) -> UserId:
        """Fixture que proporciona un ID de otro usuario (no creador)."""
        return UserId(uuid4())

    async def test_should_delete_competition_in_draft_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede eliminar una competición en estado DRAFT.

        Given: Una competición en estado DRAFT
        When: El creador solicita eliminarla
        Then: Se elimina correctamente y retorna confirmación
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Eliminar competición
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)
        response = await delete_use_case.execute(delete_request, creator_id)

        # Assert
        assert response.id == created.id
        assert response.name == "Ryder Cup 2025"
        assert response.deleted is True
        assert response.deleted_at is not None

        # Verificar que ya no existe en el repositorio
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition is None

    async def test_should_raise_error_when_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta eliminar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        delete_use_case = DeleteCompetitionUseCase(uow)
        fake_id = uuid4()
        delete_request = DeleteCompetitionRequestDTO(competition_id=fake_id)

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await delete_use_case.execute(delete_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_user_is_not_creator(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Verifica que solo el creador puede eliminar la competición.

        Given: Una competición existente
        When: Un usuario que NO es el creador intenta eliminarla
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Intentar eliminar con otro usuario
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await delete_use_case.execute(delete_request, other_user_id)

        assert "Solo el creador puede eliminar" in str(exc_info.value)

    async def test_should_delete_a_closed_competition_with_nothing_played(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        BE #347: cerradas las inscripciones, se sigue pudiendo borrar.

        Given: Una competición en estado CLOSED sin nada jugado
        When: El creador la elimina
        Then: Se elimina
        """
        created = await self._crear_competicion(uow, creator_id)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        response = await DeleteCompetitionUseCase(uow).execute(
            DeleteCompetitionRequestDTO(competition_id=created.id), creator_id
        )

        assert response.deleted is True
        async with uow:
            assert await uow.competitions.find_by_id(CompetitionId(created.id)) is None

    async def test_should_raise_error_when_trying_to_delete_in_progress_competition(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se pueden eliminar competiciones en curso.

        Given: Una competición en estado IN_PROGRESS
        When: El creador intenta eliminarla
        Then: Se lanza CompetitionNotDeletableError
        """
        # Arrange: Crear competición y llevarla a IN_PROGRESS
        create_use_case = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Llevar a IN_PROGRESS (DRAFT → ACTIVE → CLOSED → IN_PROGRESS)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.close_enrollments()
            competition.start()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar eliminar competición IN_PROGRESS
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionNotDeletableError) as exc_info:
            await delete_use_case.execute(delete_request, creator_id)

        assert "Estado actual: IN_PROGRESS" in str(exc_info.value)

    async def test_should_raise_error_when_trying_to_delete_completed_competition(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se pueden eliminar competiciones completadas.

        Given: Una competición en estado COMPLETED
        When: El creador intenta eliminarla
        Then: Se lanza CompetitionNotDeletableError
        """
        # Arrange: Crear competición y llevarla a COMPLETED
        create_use_case = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Llevar a COMPLETED
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.close_enrollments()
            competition.start()
            competition.complete()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar eliminar competición COMPLETED
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionNotDeletableError) as exc_info:
            await delete_use_case.execute(delete_request, creator_id)

        assert "Estado actual: COMPLETED" in str(exc_info.value)

    async def test_should_delete_competition_with_enrollment_open(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        BE #333: una competición con las inscripciones abiertas se puede borrar.

        Given: Una competición en estado ACTIVE, sin nadie inscrito
        When: El creador la elimina
        Then: Se elimina y deja de existir
        """
        created = await self._crear_competicion(uow, creator_id)
        await self._activar(uow, created.id)

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        response = await delete_use_case.execute(request, creator_id)

        assert response.deleted is True
        async with uow:
            assert await uow.competitions.find_by_id(CompetitionId(created.id)) is None

    async def test_should_delete_active_competition_that_already_has_players(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        BE #333: tener gente dentro no impide borrarla.

        Es justo lo que el creador está deshaciendo a propósito, y la cascada se
        lleva sus inscripciones con ella.

        Given: Una competición ACTIVE con dos jugadores inscritos
        When: El creador la elimina
        Then: Se elimina
        """
        created = await self._crear_competicion(uow, creator_id)
        await self._activar(uow, created.id)
        await self._inscribir(uow, created.id, cuantos=2)

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        response = await delete_use_case.execute(request, creator_id)

        assert response.deleted is True
        async with uow:
            assert await uow.competitions.find_by_id(CompetitionId(created.id)) is None

    async def test_should_let_an_admin_delete_someone_elses_active_competition(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """Un admin puede borrar la de otro: ya podía con un borrador."""
        created = await self._crear_competicion(uow, creator_id)
        await self._activar(uow, created.id)

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        response = await delete_use_case.execute(request, other_user_id, is_admin=True)

        assert response.deleted is True

    async def test_should_delete_a_cancelled_competition_that_never_got_going(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """Una cancelada sin calendario se borra: cancelar no es el destino.

        Given: Una competición cancelada desde borrador, sin nada montado
        When: El creador la elimina
        Then: Se elimina y deja de existir
        """
        created = await self._crear_competicion(uow, creator_id)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.cancel()
            await uow.competitions.update(competition)
            await uow.commit()

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        response = await delete_use_case.execute(request, creator_id)

        assert response.deleted is True
        async with uow:
            assert await uow.competitions.find_by_id(CompetitionId(created.id)) is None

    async def test_should_refuse_to_delete_a_cancelled_competition_that_was_played(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """Cancelar un torneo ya jugado no lo hace desechable.

        Es la otra cara: lo que decide no es el estado sino si se llegó a jugar,
        y una cancelada con un golpe anotado se lo llevaría en la cascada.

        Given: Una competición con un golpe anotado y luego cancelada
        When: El creador intenta eliminarla
        Then: Se lanza CompetitionNotDeletableError
        """
        created = await self._crear_competicion(uow, creator_id)
        await self._activar(uow, created.id)
        await montar_calendario(uow, created.id, "golpe propio")
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.cancel()
            await uow.competitions.update(competition)
            await uow.commit()

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        with pytest.raises(CompetitionNotDeletableError) as exc_info:
            await delete_use_case.execute(request, creator_id)

        assert "golpes anotados" in str(exc_info.value)
        # El calendario ya no es el motivo: decirlo mandaría a deshacerlo en balde
        assert "calendario" not in str(exc_info.value).lower()

    async def test_should_refuse_to_delete_a_reopened_competition_that_was_played(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        BE #333: volver a ACTIVE no vuelve a hacerla borrable.

        El estado se puede andar hacia atrás: `revert-status` devuelve un torneo
        en juego a CLOSED y `reopen-enrollments` lo devuelve a ACTIVE, y ninguna
        de las dos borra rondas ni partidos. Mirando solo el estado, un torneo ya
        jugado acabaría siendo borrable, y la cascada se llevaría los golpes.

        Given: Una competición en ACTIVE con un partido terminado
        When: El creador intenta eliminarla
        Then: Se lanza CompetitionNotDeletableError, que dice por qué
        """
        created = await self._crear_competicion(uow, creator_id)
        await self._activar(uow, created.id)
        await montar_calendario(uow, created.id, "terminado")

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        with pytest.raises(CompetitionNotDeletableError) as exc_info:
            await delete_use_case.execute(request, creator_id)

        assert "golpes anotados" in str(exc_info.value)
        # El calendario ya no es el motivo: decirlo mandaría a deshacerlo en balde
        assert "calendario" not in str(exc_info.value).lower()

    async def test_should_delete_a_competition_whose_schedule_was_never_played(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        BE #347: tener calendario ya no impide borrar; haberlo jugado, sí.

        La cascada se lleva la ronda, sus partidos y sus tarjetas, y todo eso
        estaba vacío: se protege lo jugado, no lo montado (22 sep).

        Given: Una competición con un partido abierto y sus tarjetas vacías
        When: El creador la elimina
        Then: Se elimina, y con ella su calendario
        """
        created = await self._crear_competicion(uow, creator_id)
        await self._activar(uow, created.id)
        await montar_calendario(uow, created.id, "empezado")

        response = await DeleteCompetitionUseCase(uow).execute(
            DeleteCompetitionRequestDTO(competition_id=created.id), creator_id
        )

        assert response.deleted is True

    async def test_should_delete_a_competition_whose_teams_are_drawn_but_has_no_schedule(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        BE #333: el sorteo de equipos no impide borrar (decidido 21 sep).

        Lo que se protege es lo jugado, no lo preparado. Sin rondas no hay
        partidos, y sin partidos no puede haber un solo golpe anotado —anotar
        exige IN_PROGRESS—, asi que aqui no se pierde nada irrecuperable: el
        sorteo se rehace, y `assign_teams` ya reasigna borrando el anterior.

        Given: Una competición en ACTIVE con los equipos sorteados y sin calendario
        When: El creador la elimina
        Then: Se elimina
        """
        created = await self._crear_competicion(uow, creator_id)
        await self._activar(uow, created.id)
        await self._sortear_equipos(uow, created.id)

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        response = await delete_use_case.execute(request, creator_id)

        assert response.deleted is True
        async with uow:
            assert await uow.competitions.find_by_id(CompetitionId(created.id)) is None

    async def test_should_lock_the_competition_row_before_deleting(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        BE #333: la fila se bloquea al leerla, para que nadie monte nada a la vez.

        Entre comprobar que no hay calendario y borrar caben milisegundos, y en
        READ COMMITTED leer no reserva nada. Sin bloqueo, una ronda creada desde
        otra pestaña justo ahí se colaba: el borrado ya había decidido con la
        foto anterior, y la cascada se la llevaba sin que nadie se enterase.

        Se comprueba que la lectura es la bloqueante porque el bloqueo no se
        puede observar de otro modo en memoria: el repositorio en memoria lo
        implementa como un no-op, y contra Postgres el efecto solo se ve con dos
        transacciones a la vez.
        """
        created = await self._crear_competicion(uow, creator_id)

        bloqueadas = []
        sin_bloqueo = []
        original_bloqueante = uow.competitions.find_by_id_for_update
        original_normal = uow.competitions.find_by_id

        async def espia_bloqueante(competition_id):
            bloqueadas.append(competition_id)
            return await original_bloqueante(competition_id)

        async def espia_normal(competition_id):
            sin_bloqueo.append(competition_id)
            return await original_normal(competition_id)

        uow.competitions.find_by_id_for_update = espia_bloqueante
        uow.competitions.find_by_id = espia_normal

        delete_use_case = DeleteCompetitionUseCase(uow)
        request = DeleteCompetitionRequestDTO(competition_id=created.id)

        await delete_use_case.execute(request, creator_id)

        assert len(bloqueadas) == 1
        assert sin_bloqueo == []

    # ===========================================
    # Helpers
    # ===========================================

    async def _crear_competicion(self, uow: InMemoryUnitOfWork, creator_id: UserId):
        """Crea una competición en DRAFT y devuelve la respuesta de creación."""
        create_use_case = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        return await create_use_case.execute(request, creator_id)

    async def _activar(self, uow: InMemoryUnitOfWork, competition_id: str) -> None:
        """Abre las inscripciones de una competición recién creada."""

    async def _inscribir(self, uow: InMemoryUnitOfWork, competition_id: str, cuantos: int) -> None:
        """Mete a `cuantos` jugadores aprobados en la competición."""
        async with uow:
            for _ in range(cuantos):
                enrollment = Enrollment.direct_enroll(
                    id=EnrollmentId(uuid4()),
                    competition_id=CompetitionId(competition_id),
                    user_id=UserId(uuid4()),
                )
                await uow.enrollments.add(enrollment)
            await uow.commit()

    async def _sortear_equipos(self, uow: InMemoryUnitOfWork, competition_id: str) -> None:
        """Deja los equipos sorteados, como haría el reparto antes del calendario."""
        async with uow:
            await uow.team_assignments.add(
                TeamAssignment.create(
                    competition_id=CompetitionId(competition_id),
                    mode=TeamAssignmentMode.MANUAL,
                    team_a_player_ids=[UserId(uuid4())],
                    team_b_player_ids=[UserId(uuid4())],
                )
            )
            await uow.commit()

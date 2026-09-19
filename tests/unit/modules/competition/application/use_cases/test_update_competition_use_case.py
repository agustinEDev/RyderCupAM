"""Tests para UpdateCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestUpdateCompetitionUseCase:
    """Suite de tests para el caso de uso UpdateCompetitionUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    async def test_should_update_competition_name_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede actualizar el nombre de una competición.

        Given: Una competición existente en estado DRAFT
        When: Se actualiza solo el nombre
        Then: El nombre se actualiza correctamente
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        create_request = CreateCompetitionRequestDTO(
            name="Original Name",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Actualizar nombre
        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        update_request = UpdateCompetitionRequestDTO(name="Updated Name")

        response = await update_use_case.execute(
            CompetitionId(created.id), update_request, creator_id
        )

        # Assert
        assert response.name == "Updated Name"
        assert response.id == created.id

        # Verificar en BD
        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.name) == "Updated Name"

    async def test_should_update_accompanying_countries_without_resending_main_country(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que los países acompañantes se pueden cambiar por sí solos.

        Given: Una competición en España, sin acompañantes
        When: Se manda solo `countries`, sin repetir el país principal
        Then: El acompañante queda guardado

        La localización se reconstruía solo si llegaba `main_country`, así que
        una edición de solo los acompañantes devolvía 200 sin cambiar nada.
        """
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        created = await create_use_case.execute(
            CreateCompetitionRequestDTO(
                name="Original",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
            ),
            creator_id,
        )

        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        await update_use_case.execute(
            CompetitionId(created.id),
            UpdateCompetitionRequestDTO(countries=["PT"]),
            creator_id,
        )

        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.location.main_country) == "ES"
        assert str(competition.location.adjacent_country_1) == "PT"

    async def test_should_update_adjacent_country_without_resending_main_country(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """Lo mismo con el nombre canónico del campo, no solo con `countries`."""
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        created = await create_use_case.execute(
            CreateCompetitionRequestDTO(
                name="Original",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
            ),
            creator_id,
        )

        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        await update_use_case.execute(
            CompetitionId(created.id),
            UpdateCompetitionRequestDTO(adjacent_country_1="FR"),
            creator_id,
        )

        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.location.main_country) == "ES"
        assert str(competition.location.adjacent_country_1) == "FR"

    async def test_should_remove_accompanying_countries_with_an_empty_list(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que una lista vacía quita los acompañantes.

        Es como los quita la pantalla: manda `countries: []`, no omite el campo.
        """
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        created = await create_use_case.execute(
            CreateCompetitionRequestDTO(
                name="Original",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                countries=["PT"],
            ),
            creator_id,
        )

        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        await update_use_case.execute(
            CompetitionId(created.id),
            UpdateCompetitionRequestDTO(countries=[]),
            creator_id,
        )

        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.location.main_country) == "ES"
        assert competition.location.adjacent_country_1 is None

    async def test_should_leave_location_untouched_when_no_country_is_sent(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """Lo que no se manda no se toca: una edición de solo el nombre no borra países."""
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        created = await create_use_case.execute(
            CreateCompetitionRequestDTO(
                name="Original",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                countries=["PT"],
            ),
            creator_id,
        )

        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        await update_use_case.execute(
            CompetitionId(created.id),
            UpdateCompetitionRequestDTO(name="Updated"),
            creator_id,
        )

        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.location.main_country) == "ES"
        assert str(competition.location.adjacent_country_1) == "PT"

    async def test_should_update_multiple_fields(self, uow: InMemoryUnitOfWork, creator_id: UserId):
        """
        Verifica que se pueden actualizar múltiples campos a la vez.

        Given: Una competición existente
        When: Se actualizan nombre, fechas y país
        Then: Todos los campos se actualizan correctamente
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        create_request = CreateCompetitionRequestDTO(
            name="Original",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        update_request = UpdateCompetitionRequestDTO(
            name="Updated",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 3),
            main_country="FR",
        )

        await update_use_case.execute(CompetitionId(created.id), update_request, creator_id)

        # Assert
        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.name) == "Updated"
        assert competition.dates.start_date == date(2025, 7, 1)
        assert competition.dates.end_date == date(2025, 7, 3)
        assert competition.location.main_country.value == "FR"

    async def test_should_update_play_mode_from_scratch_to_handicap(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede cambiar el play_mode de SCRATCH a HANDICAP.

        Given: Competición con play_mode SCRATCH
        When: Se actualiza a HANDICAP
        Then: El play_mode se actualiza correctamente
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        update_request = UpdateCompetitionRequestDTO(play_mode="HANDICAP")

        await update_use_case.execute(CompetitionId(created.id), update_request, creator_id)

        # Assert
        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert competition.play_mode.value == "HANDICAP"

    async def test_should_raise_error_when_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta actualizar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        fake_id = CompetitionId(uuid4())
        update_request = UpdateCompetitionRequestDTO(name="Test")

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await update_use_case.execute(fake_id, update_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_not_creator(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que solo el creador puede actualizar.

        Given: Una competición creada por user A
        When: User B intenta actualizar
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear con creator_id
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act & Assert: Intentar actualizar con otro usuario
        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        other_user = UserId(uuid4())
        update_request = UpdateCompetitionRequestDTO(name="Hacked")

        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await update_use_case.execute(CompetitionId(created.id), update_request, other_user)

        assert "Solo el creador" in str(exc_info.value)

    async def test_should_raise_error_when_not_in_draft_state(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que solo se puede actualizar en estado DRAFT.

        Given: Una competición activada (ACTIVE)
        When: Se intenta actualizar
        Then: Se lanza CompetitionNotEditableError
        """
        # Arrange: Crear y activar competición
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar la competición (cambiar a ACTIVE)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act & Assert: Intentar actualizar
        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        update_request = UpdateCompetitionRequestDTO(name="Cannot Update")

        with pytest.raises(CompetitionNotEditableError) as exc_info:
            await update_use_case.execute(CompetitionId(created.id), update_request, creator_id)

        assert "Solo se permite en estado DRAFT" in str(exc_info.value)

    async def test_should_commit_transaction(self, uow: InMemoryUnitOfWork, creator_id: UserId):
        """
        Verifica que la transacción se hace commit correctamente.

        Given: Una actualización válida
        When: Se ejecuta el caso de uso
        Then: Se llama a commit() en el UoW
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        update_use_case = UpdateCompetitionUseCase(uow, LocationBuilder(uow.countries))
        update_request = UpdateCompetitionRequestDTO(name="Updated")

        await update_use_case.execute(CompetitionId(created.id), update_request, creator_id)

        # Assert
        assert uow.committed is True

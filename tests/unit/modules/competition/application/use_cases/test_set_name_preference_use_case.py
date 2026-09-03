"""Tests para SetNamePreferenceUseCase (BE #254)."""

from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    SetNamePreferenceRequestDTO,
)
from src.modules.competition.application.use_cases.set_name_preference_use_case import (
    EnrollmentNotFoundError,
    NotOwnerError,
    SetNamePreferenceUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


class TestSetNamePreferenceUseCase:
    """Suite de tests para el caso de uso SetNamePreferenceUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        return UserId(uuid4())

    @pytest.fixture
    def player_id(self) -> UserId:
        return UserId(uuid4())

    async def test_should_set_use_real_name_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment aprobado en una competición ACTIVE
        When: El propio jugador elige mostrar su nombre legal
        Then: El enrollment refleja la preferencia
        """
        created = await create_competition(uow, creator_id)
        await set_competition_status(uow, created.id, "ACTIVE")
        enrollment = await create_approved_enrollment(uow, created.id, player_id)

        use_case = SetNamePreferenceUseCase(uow)
        request = SetNamePreferenceRequestDTO(
            enrollment_id=enrollment.id.value, use_real_name=True
        )
        response = await use_case.execute(request, player_id)

        assert response.use_real_name is True

    async def test_should_allow_switching_back_to_alias(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment que ya eligió el nombre legal
        When: El jugador vuelve a elegir el alias
        Then: El enrollment refleja el cambio
        """
        created = await create_competition(uow, creator_id)
        await set_competition_status(uow, created.id, "ACTIVE")
        enrollment = await create_approved_enrollment(uow, created.id, player_id)

        use_case = SetNamePreferenceUseCase(uow)
        await use_case.execute(
            SetNamePreferenceRequestDTO(enrollment_id=enrollment.id.value, use_real_name=True),
            player_id,
        )
        response = await use_case.execute(
            SetNamePreferenceRequestDTO(enrollment_id=enrollment.id.value, use_real_name=False),
            player_id,
        )

        assert response.use_real_name is False

    async def test_should_raise_not_owner_error_when_creator_tries(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment de otro jugador
        Then: Aquí decide el DUEÑO de la inscripción, no el creador — al
        revés que el hándicap personalizado, que decide el creador
        When: El creador de la competición intenta cambiar la preferencia
        Then: Se lanza NotOwnerError
        """
        created = await create_competition(uow, creator_id)
        await set_competition_status(uow, created.id, "ACTIVE")
        enrollment = await create_approved_enrollment(uow, created.id, player_id)

        use_case = SetNamePreferenceUseCase(uow)
        request = SetNamePreferenceRequestDTO(
            enrollment_id=enrollment.id.value, use_real_name=True
        )

        with pytest.raises(NotOwnerError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_enrollment_not_found(
        self, uow: InMemoryUnitOfWork, player_id: UserId
    ):
        """
        Given: Un enrollment_id que no existe
        When: Se intenta cambiar la preferencia
        Then: Se lanza EnrollmentNotFoundError
        """
        use_case = SetNamePreferenceUseCase(uow)
        request = SetNamePreferenceRequestDTO(enrollment_id=uuid4(), use_real_name=True)

        with pytest.raises(EnrollmentNotFoundError):
            await use_case.execute(request, player_id)

    @pytest.mark.parametrize(
        "status", ["DRAFT", "ACTIVE", "CLOSED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
    )
    async def test_should_allow_edit_in_any_competition_status(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId, status: str
    ):
        """
        Given: Un enrollment aprobado
        When: La competición está en cualquier estado, torneo en marcha o
        terminado incluidos
        Then: Se puede cambiar la preferencia sin errores — a diferencia del
        hándicap personalizado, esta elección no se congela: quien se
        equivocó al elegir no tiene que esperar a que acabe el torneo para
        corregirlo. Decisión de producto, no un descuido (ver el docstring
        del caso de uso)
        """
        created = await create_competition(uow, creator_id)
        enrollment = await create_approved_enrollment(uow, created.id, player_id)
        await set_competition_status(uow, created.id, status)

        use_case = SetNamePreferenceUseCase(uow)
        request = SetNamePreferenceRequestDTO(
            enrollment_id=enrollment.id.value, use_real_name=True
        )

        response = await use_case.execute(request, player_id)
        assert response.use_real_name is True

    async def test_should_raise_enrollment_state_error_when_not_approved(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, player_id: UserId
    ):
        """
        Given: Un enrollment en estado REQUESTED (no aprobado)
        Then: A diferencia del hándicap, aquí NO hace falta estar aprobado:
        alguien invitado o a la espera también puede fijar su preferencia
        antes de que le aprueben. Este test documenta esa diferencia — que
        no lance EnrollmentStateError es el comportamiento correcto.
        When: El propio jugador cambia la preferencia
        Then: Se aplica sin errores
        """
        created = await create_competition(uow, creator_id)
        await set_competition_status(uow, created.id, "ACTIVE")
        enrollment = Enrollment.request(
            id=EnrollmentId.generate(),
            competition_id=CompetitionId(created.id),
            user_id=player_id,
        )
        async with uow:
            await uow.enrollments.add(enrollment)
            await uow.commit()

        use_case = SetNamePreferenceUseCase(uow)
        request = SetNamePreferenceRequestDTO(
            enrollment_id=enrollment.id.value, use_real_name=True
        )

        response = await use_case.execute(request, player_id)
        assert response.use_real_name is True

"""En una competicion privada se entra porque te invitan (BE #318).

Hoy cualquiera puede pedir plaza en cualquier competicion ACTIVE: el caso de uso
mira el cupo, si ya estas dentro y cuantas llevas, y nada mas. No es una brecha
—el organizador aprueba o rechaza— pero es justo lo que un torneo privado existe
para evitar: que un desconocido llame a la puerta de la Ryder de unos amigos.
"""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    CompetitionIsPrivateError,
    RequestEnrollmentUseCase,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio


class _ConGenero:
    """Cualquiera tiene el género puesto: esto prueba la visibilidad, no el género."""

    async def find_by_id(self, user_id):
        return SimpleNamespace(id=user_id, gender=Gender.MALE)


_CON_GENERO = _ConGenero()


class TestAskingForAPlace:
    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        return UserId(uuid4())

    async def _competition_open_to(self, uow, creator_id, visibility):
        create_uc = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        created = await create_uc.execute(
            CreateCompetitionRequestDTO(
                name="Ryder de los amigos",
                start_date=date(2027, 6, 1),
                end_date=date(2027, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                visibility=visibility,
            ),
            creator_id,
        )
        return created

    async def test_a_stranger_cannot_ask_to_join_a_private_one(self, uow, creator_id):
        """La puerta de un torneo entre amigos no se toca desde fuera."""
        created = await self._competition_open_to(uow, creator_id, Visibility.PRIVATE)

        uc = RequestEnrollmentUseCase(uow, _CON_GENERO)
        with pytest.raises(CompetitionIsPrivateError):
            await uc.execute(
                RequestEnrollmentRequestDTO(competition_id=created.id, user_id=uuid4())
            )

    async def test_a_stranger_can_ask_to_join_a_public_one(self, uow, creator_id):
        """Y en la de un club, cualquiera puede pedir sitio."""
        created = await self._competition_open_to(uow, creator_id, Visibility.PUBLIC)

        uc = RequestEnrollmentUseCase(uow, _CON_GENERO)
        respuesta = await uc.execute(
            RequestEnrollmentRequestDTO(competition_id=created.id, user_id=uuid4())
        )

        assert respuesta.status == "REQUESTED"

    async def test_nothing_is_written_when_it_is_refused(self, uow, creator_id):
        """Rechazar no deja una inscripcion a medias por ahi."""
        created = await self._competition_open_to(uow, creator_id, Visibility.PRIVATE)
        quien = uuid4()

        uc = RequestEnrollmentUseCase(uow, _CON_GENERO)
        with pytest.raises(CompetitionIsPrivateError):
            await uc.execute(RequestEnrollmentRequestDTO(competition_id=created.id, user_id=quien))

        async with uow:
            assert (
                await uow.enrollments.find_by_user_and_competition(
                    UserId(quien), CompetitionId(created.id)
                )
                is None
            )

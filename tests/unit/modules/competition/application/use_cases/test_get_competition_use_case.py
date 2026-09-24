"""Tests para GetCompetitionUseCase."""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

MADRID = "Europe/Madrid"


class FakeZona:
    """Dice la zona del primer campo sin bajar a la base de datos."""

    def __init__(self, zona: str | None):
        self._zona = zona

    async def for_competition(self, competition) -> str | None:
        return self._zona if competition.golf_courses else None

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestGetCompetitionUseCase:
    """Suite de tests para el caso de uso GetCompetitionUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    async def test_should_get_competition_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede obtener una competición por su ID.

        Given: Una competición existente
        When: Se solicita por ID
        Then: Se retorna el DTO completo
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
            adjacent_country_1="PT",
            play_mode="HANDICAP",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Obtener competición
        get_use_case = GetCompetitionUseCase(uow)
        competition = await get_use_case.execute(CompetitionId(created.id))

        # Assert
        assert competition.id.value == created.id
        assert str(competition.name) == "Ryder Cup 2025"
        assert competition.status.value == "ACTIVE"
        assert competition.creator_id.value == creator_id.value
        assert competition.dates.start_date == date(2025, 6, 1)
        assert competition.dates.end_date == date(2025, 6, 3)
        assert competition.location.main_country.value == "ES"
        assert competition.location.adjacent_country_1.value == "PT"
        assert competition.play_mode.value == "HANDICAP"

    async def test_should_get_competition_with_scratch_play_mode(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se obtiene correctamente una competición con play_mode SCRATCH.

        Given: Competición con play_mode SCRATCH
        When: Se solicita por ID
        Then: El DTO muestra play_mode como SCRATCH
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        create_request = CreateCompetitionRequestDTO(
            name="Scratch Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="FR",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        get_use_case = GetCompetitionUseCase(uow)
        competition = await get_use_case.execute(CompetitionId(created.id))

        # Assert
        assert competition.play_mode.value == "SCRATCH"

    async def test_should_raise_error_when_competition_not_found(self, uow: InMemoryUnitOfWork):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta obtener
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        get_use_case = GetCompetitionUseCase(uow)
        fake_id = CompetitionId(uuid4())

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await get_use_case.execute(fake_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_get_competition_without_adjacent_countries(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se obtiene correctamente una competición sin países adyacentes.

        Given: Competición solo con país principal
        When: Se solicita por ID
        Then: Los países adyacentes son None en el DTO
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        create_request = CreateCompetitionRequestDTO(
            name="Single Country Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="IT",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        get_use_case = GetCompetitionUseCase(uow)
        competition = await get_use_case.execute(CompetitionId(created.id))

        # Assert
        assert competition.location.main_country.value == "IT"
        assert competition.location.adjacent_country_1 is None
        assert competition.location.adjacent_country_2 is None


class TestScheduledOpening:
    """BE #319: mirar la competicion despues de su hora es lo que la abre.

    No hay ningun proceso programado en el backend, asi que «se abre sola»
    significa que la abre la primera persona que pasa por ella pasada la hora.
    Mismo criterio que la anotacion, que abre cuando llega el primer golpe.
    """

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        return UserId(uuid4())

    async def _draft_con_apertura(self, uow, creator_id, dias_antes, empieza_en=30, con_campo=True):
        """Una competicion que espera su hora, a tantos dias de empezar.

        La apertura se deriva de la fecha de inicio (BE #332), asi que lo que
        decide si ya toca es cuanto falta para el torneo frente a los dias de
        antelacion: empezando dentro de 3 dias y abriendo 5 antes, la apertura
        quedo atras. Todo relativo a hoy, que si no los tests se estropean solos
        el dia en que la fecha fijada queda por detras.
        """
        empieza = date.today() + timedelta(days=empieza_en)
        create_uc = CreateCompetitionUseCase(
            uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
        )
        created = await create_uc.execute(
            CreateCompetitionRequestDTO(
                name="Torneo del club",
                start_date=empieza,
                end_date=empieza + timedelta(days=2),
                main_country="ES",
                play_mode="SCRATCH",
                enrollment_opens_days_before=dias_antes,
            ),
            creator_id,
        )
        if con_campo:
            async with uow:
                competition = await uow.competitions.find_by_id(CompetitionId(created.id))
                competition.add_golf_course(GolfCourseId.generate(), CountryCode("ES"))
                await uow.competitions.update(competition)
                await uow.commit()
        return created

    async def _status(self, uow, competition_id):
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(competition_id))
            return competition.status

    async def test_looking_at_it_after_the_hour_opens_it(self, uow, creator_id):
        """La hora ya paso: quien mira la competicion la abre."""
        # Empieza en 3 dias y abria 5 antes: hace dos que le tocaba
        created = await self._draft_con_apertura(uow, creator_id, 5, empieza_en=3)

        uc = GetCompetitionUseCase(uow, zona_del_campo=FakeZona(MADRID))
        competition = await uc.execute(CompetitionId(created.id))

        assert competition.status == CompetitionStatus.ACTIVE
        assert await self._status(uow, created.id) == CompetitionStatus.ACTIVE

    async def test_the_opening_gets_saved(self, uow, creator_id):
        """La apertura se persiste, no solo se cambia en memoria.

        El repositorio en memoria devuelve la MISMA instancia que guarda, asi
        que un `update` olvidado pasaria desapercibido aqui y no se escribiria
        nada en Postgres: la competicion volveria a parecer un borrador en la
        siguiente peticion.
        """
        # Empieza en 3 dias y abria 5 antes: hace dos que le tocaba
        created = await self._draft_con_apertura(uow, creator_id, 5, empieza_en=3)

        guardadas = []
        original = uow.competitions.update

        async def espia(competition):
            guardadas.append(competition.status)
            await original(competition)

        uow.competitions.update = espia

        uc = GetCompetitionUseCase(uow, zona_del_campo=FakeZona(MADRID))
        await uc.execute(CompetitionId(created.id))

        assert CompetitionStatus.ACTIVE in guardadas

    async def test_before_the_hour_it_stays_shut(self, uow, creator_id):
        # Empieza dentro de un mes y abre 5 dias antes: todavia falta
        created = await self._draft_con_apertura(uow, creator_id, 5, empieza_en=30)

        uc = GetCompetitionUseCase(uow, zona_del_campo=FakeZona(MADRID))
        competition = await uc.execute(CompetitionId(created.id))

        assert competition.status == CompetitionStatus.DRAFT

    async def test_without_a_course_it_waits(self, uow, creator_id):
        """Sin campo no hay zona, y sin zona no se abre a ciegas (20 sep)."""
        created = await self._draft_con_apertura(uow, creator_id, 5, empieza_en=3, con_campo=False)

        uc = GetCompetitionUseCase(uow, zona_del_campo=FakeZona(MADRID))
        competition = await uc.execute(CompetitionId(created.id))

        assert competition.status == CompetitionStatus.DRAFT

    async def test_calling_the_schedule_off_opens_it(self, uow, creator_id):
        """Quitar los dias es decir «abrela ya».

        Bajo el modelo nuevo «sin programacion» significa «abierta», asi que
        desprogramar no puede dejar la competicion cerrada sin nada que esperar:
        se quedaria varada, sin mas salida que el boton que FE #640 quiere
        retirar.
        """
        created = await self._draft_con_apertura(uow, creator_id, 5, empieza_en=3)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.schedule_enrollment_opening(None)
            await uow.competitions.update(competition)
            await uow.commit()

        uc = GetCompetitionUseCase(uow, zona_del_campo=FakeZona(MADRID))
        competition = await uc.execute(CompetitionId(created.id))

        assert competition.status == CompetitionStatus.ACTIVE

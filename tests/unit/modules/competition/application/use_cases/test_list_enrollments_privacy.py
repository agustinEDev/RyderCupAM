"""
Quién ve qué en la lista de inscritos (BE #531).

- El organizador y los admin: todas las filas y todos los correos.
- Cualquier otro: los aprobados y su propia fila (en el estado que esté), y
  solo su propio correo.
- El filtro `?status=` se aplica encima.
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_enrollments_use_case import (
    ListEnrollmentsUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio

NO_APROBADOS = (
    EnrollmentStatus.REQUESTED,
    EnrollmentStatus.INVITED,
    EnrollmentStatus.REJECTED,
    EnrollmentStatus.CANCELLED,
    EnrollmentStatus.WITHDRAWN,
)


class _Escenario:
    """Un torneo con su creador, dos aprobados y una fila ajena por cada otro estado."""

    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId(uuid4())
        self.aprobados = [UserId(uuid4()), UserId(uuid4())]
        self.ajenos = {estado: UserId(uuid4()) for estado in NO_APROBADOS}
        self.torneo: CompetitionId | None = None

    async def montar(self) -> "_Escenario":
        creada = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), USUARIOS_CON_GENERO
        ).execute(
            CreateCompetitionRequestDTO(
                name="Copa privada",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 3),
                main_country="ES",
                play_mode="SCRATCH",
                max_players=24,
            ),
            self.creador,
        )
        self.torneo = CompetitionId(creada.id)
        for user_id in self.aprobados:
            await self.fila(user_id, EnrollmentStatus.APPROVED)
        for estado, user_id in self.ajenos.items():
            await self.fila(user_id, estado)
        return self

    async def fila(self, user_id: UserId, estado: EnrollmentStatus) -> Enrollment:
        inscripcion = Enrollment(
            id=EnrollmentId.generate(),
            competition_id=self.torneo,
            user_id=user_id,
            status=estado,
        )
        async with self.uow:
            await self.uow.enrollments.add(inscripcion)
            await self.uow.commit()
        return inscripcion

    async def lista(self, viewer: UserId, is_admin: bool = False, status: str | None = None):
        return await ListEnrollmentsUseCase(self.uow).execute(
            str(self.torneo.value),
            EnrollmentStatus(status) if status else None,
            viewer_id=viewer,
            viewer_is_admin=is_admin,
        )

    @property
    def todos(self) -> set[UserId]:
        return {self.creador, *self.aprobados, *self.ajenos.values()}


@pytest.fixture
async def e() -> _Escenario:
    return await _Escenario().montar()


def _quienes(lista) -> set[UserId]:
    return {i.user_id for i in lista.enrollments}


class TestElOrganizador:
    async def test_ve_todas_las_filas_en_todos_los_estados(self, e):
        lista = await e.lista(e.creador)

        assert _quienes(lista) == e.todos
        assert len(lista.enrollments) == 2 + 1 + len(NO_APROBADOS)

    async def test_ve_todos_los_correos(self, e):
        lista = await e.lista(e.creador)

        assert lista.ve_todos_los_correos is True

    async def test_con_filtro_ve_las_filas_ajenas_de_ese_estado(self, e):
        lista = await e.lista(e.creador, status="REJECTED")

        assert _quienes(lista) == {e.ajenos[EnrollmentStatus.REJECTED]}


class TestUnAdmin:
    async def test_ve_todas_las_filas_y_todos_los_correos(self, e):
        admin = UserId(uuid4())

        lista = await e.lista(admin, is_admin=True)

        assert _quienes(lista) == e.todos
        assert lista.ve_todos_los_correos is True

    async def test_con_filtro_ve_las_solicitudes_de_los_demas(self, e):
        lista = await e.lista(UserId(uuid4()), is_admin=True, status="REQUESTED")

        assert _quienes(lista) == {e.ajenos[EnrollmentStatus.REQUESTED]}


class TestUnJugadorInscrito:
    async def test_aprobado_ve_los_aprobados_y_ningun_otro_estado_ajeno(self, e):
        yo = e.aprobados[0]

        lista = await e.lista(yo)

        assert _quienes(lista) == {e.creador, *e.aprobados}
        assert all(i.status is EnrollmentStatus.APPROVED for i in lista.enrollments)

    @pytest.mark.parametrize("estado", NO_APROBADOS)
    async def test_ve_su_propia_fila_en_cualquier_estado(self, e, estado):
        yo = e.ajenos[estado]

        lista = await e.lista(yo)

        assert _quienes(lista) == {e.creador, *e.aprobados, yo}
        mia = [i for i in lista.enrollments if i.user_id == yo]
        assert [i.status for i in mia] == [estado]

    async def test_solo_ve_su_propio_correo(self, e):
        yo = e.ajenos[EnrollmentStatus.REQUESTED]

        lista = await e.lista(yo)

        # El suyo lo pone el mapper con su viewer_id
        assert lista.ve_todos_los_correos is False

    async def test_con_filtro_requested_solo_ve_la_suya(self, e):
        yo = e.ajenos[EnrollmentStatus.REQUESTED]
        otro = UserId(uuid4())
        await e.fila(otro, EnrollmentStatus.REQUESTED)

        lista = await e.lista(yo, status="REQUESTED")

        assert _quienes(lista) == {yo}

    async def test_con_filtro_approved_no_cuela_la_suya_pendiente(self, e):
        yo = e.ajenos[EnrollmentStatus.REQUESTED]

        lista = await e.lista(yo, status="APPROVED")

        assert _quienes(lista) == {e.creador, *e.aprobados}

    async def test_con_filtro_rejected_sin_fila_propia_no_ve_nada(self, e):
        yo = e.aprobados[0]

        lista = await e.lista(yo, status="REJECTED")

        assert lista.enrollments == []

    async def test_quien_se_dio_de_alta_otra_vez_ve_sus_dos_filas(self, e):
        yo = e.ajenos[EnrollmentStatus.WITHDRAWN]
        await e.fila(yo, EnrollmentStatus.REQUESTED)

        lista = await e.lista(yo)

        mias = sorted(i.status.value for i in lista.enrollments if i.user_id == yo)
        assert mias == ["REQUESTED", "WITHDRAWN"]


class TestUnUsuarioSinRelacion:
    async def test_solo_ve_los_aprobados(self, e):
        lista = await e.lista(UserId(uuid4()))

        assert _quienes(lista) == {e.creador, *e.aprobados}

    async def test_no_ve_ningun_correo_ajeno(self, e):
        extrano = UserId(uuid4())

        lista = await e.lista(extrano)

        assert lista.ve_todos_los_correos is False

    async def test_con_filtro_de_un_estado_ajeno_no_ve_nada(self, e):
        for estado in NO_APROBADOS:
            lista = await e.lista(UserId(uuid4()), status=estado.value)

            assert lista.enrollments == [], estado

    async def test_el_admin_a_false_no_abre_nada(self, e):
        lista = await e.lista(UserId(uuid4()), is_admin=False, status="REQUESTED")

        assert lista.enrollments == []


async def test_sin_decir_quien_pide_no_hay_lista(e):
    """El único punto de entrada exige a quien pide: no se lista sin filtrar (BE #531)."""
    with pytest.raises(TypeError):
        await ListEnrollmentsUseCase(e.uow).execute(str(e.torneo.value))  # type: ignore[call-arg]

"""
Quién ve qué en la lista de inscritos (BE #531; release social 2, 27 oct 2026).

- El organizador y los admin: todas las filas y todos los correos.
- Privada: quien no está dentro, solo su fila; el invitado, sus amigos
  aprobados; el aprobado, todos los aprobados.
- Pública: sus amigos aprobados hasta que se publica (equipos o partidas);
  luego, todos los aprobados. Capitanes y vices, todos desde el principio.
- Cada uno ve siempre su propia fila, y solo su propio correo.
- El filtro `?status=` se aplica encima.
"""

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
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
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.visibility import Visibility
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


class _Amigos:
    """El puerto de los amigos, con los que se le digan (amistades aceptadas)."""

    def __init__(self, de: dict[UserId, set[UserId]] | None = None):
        self._de = de or {}

    async def ids_de_los_amigos(self, user_id: UserId) -> frozenset[UserId]:
        return frozenset(self._de.get(user_id, set()))


class _Escenario:
    """Un torneo con su creador, dos aprobados y una fila ajena por cada otro estado."""

    def __init__(self, visibilidad: Visibility = Visibility.PRIVATE):
        self.visibilidad = visibilidad
        self.amigos = _Amigos()
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
                visibility=self.visibilidad,
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

    async def invitar(self, quien: UserId, *, email: str = "x@test.com", **como) -> None:
        datos = {
            "status": InvitationStatus.PENDING,
            "expires_at": datetime.now() + timedelta(days=7),
            "invitee_user_id": quien,
        }
        invitacion = Invitation(
            id=InvitationId.generate(),
            competition_id=self.torneo,
            inviter_id=self.creador,
            invitee_email=email,
            **{**datos, **como},
        )
        async with self.uow:
            await self.uow.invitations.add(invitacion)
            await self.uow.commit()

    def publicar(self) -> None:
        """Los equipos ya formados (una Ryder publicada)."""
        self.uow.team_assignments.find_by_competition = AsyncMock(return_value=object())

    async def lista(
        self,
        viewer: UserId,
        is_admin: bool = False,
        status: str | None = None,
        email: str | None = None,
    ):
        return await ListEnrollmentsUseCase(self.uow, self.amigos).execute(
            str(self.torneo.value),
            EnrollmentStatus(status) if status else None,
            viewer_id=viewer,
            viewer_is_admin=is_admin,
            viewer_email=email,
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

        # En una privada, quien no está dentro (pide, retirado, rechazado...) no
        # ve a nadie más (release social 2)
        assert _quienes(lista) == {yo}
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

        assert _quienes(lista) == set()

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
    async def test_2_en_una_privada_no_ve_a_nadie(self, e):
        lista = await e.lista(UserId(uuid4()))

        assert lista.enrollments == []

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
        await ListEnrollmentsUseCase(e.uow, e.amigos).execute(str(e.torneo.value))  # type: ignore[call-arg]


# --- Release social 2 (tabla del 27 oct 2026) ---------------------------------------


class TestInvitadoAUnaPrivada:
    async def test_4_con_invitacion_pendiente_ve_a_sus_amigos_aprobados(self, e):
        yo, amigo = UserId(uuid4()), e.aprobados[0]
        await e.invitar(yo)
        e.amigos = _Amigos({yo: {amigo, e.ajenos[EnrollmentStatus.REQUESTED]}})

        lista = await e.lista(yo)

        # Su amigo pendiente no: solo los aprobados
        assert _quienes(lista) == {amigo}

    async def test_4_invitado_por_su_correo_tambien(self, e):
        yo, amigo = UserId(uuid4()), e.aprobados[0]
        await e.invitar(None, email="Yo@Test.com")
        e.amigos = _Amigos({yo: {amigo}})

        lista = await e.lista(yo, email="yo@test.com")

        assert _quienes(lista) == {amigo}

    @pytest.mark.parametrize(
        "como",
        [
            {"status": InvitationStatus.DECLINED},
            {"status": InvitationStatus.CANCELLED},
            {"status": InvitationStatus.EXPIRED},
            {"expires_at": datetime.now() - timedelta(minutes=1)},
        ],
    )
    async def test_una_invitacion_que_ya_no_vale_no_deja_ver(self, e, como):
        yo = UserId(uuid4())
        await e.invitar(yo, **como)
        e.amigos = _Amigos({yo: {e.aprobados[0]}})

        lista = await e.lista(yo)

        assert lista.enrollments == []

    async def test_la_invitacion_de_otro_no_le_deja_ver(self, e):
        yo = UserId(uuid4())
        await e.invitar(UserId(uuid4()), email="otro@test.com")
        e.amigos = _Amigos({yo: {e.aprobados[0]}})

        lista = await e.lista(yo, email="yo@test.com")

        assert lista.enrollments == []


@pytest.fixture
async def publica() -> _Escenario:
    return await _Escenario(Visibility.PUBLIC).montar()


class TestUnaPublica:
    async def test_6_sin_estar_dentro_ve_solo_a_sus_amigos_aprobados(self, publica):
        yo, amigo = UserId(uuid4()), publica.aprobados[0]
        publica.amigos = _Amigos({yo: {amigo}})

        lista = await publica.lista(yo)

        assert _quienes(lista) == {amigo}

    async def test_6_inscrito_ve_a_sus_amigos_y_su_fila(self, publica):
        yo, amigo = publica.aprobados
        publica.amigos = _Amigos({yo: {amigo}})

        lista = await publica.lista(yo)

        assert _quienes(lista) == {yo, amigo}

    async def test_6_sin_amigos_solo_su_fila(self, publica):
        yo = publica.ajenos[EnrollmentStatus.WITHDRAWN]

        lista = await publica.lista(yo)

        assert _quienes(lista) == {yo}

    async def test_8_publicada_ve_a_todos_los_aprobados(self, publica):
        publica.publicar()

        lista = await publica.lista(UserId(uuid4()))

        assert _quienes(lista) == {publica.creador, *publica.aprobados}

    async def test_8_publicada_tampoco_ve_las_solicitudes(self, publica):
        publica.publicar()

        lista = await publica.lista(UserId(uuid4()), status="REQUESTED")

        assert lista.enrollments == []

    async def test_sin_puerto_de_amigos_no_ve_a_nadie_mas(self, publica):
        yo = UserId(uuid4())

        lista = await ListEnrollmentsUseCase(publica.uow).execute(
            str(publica.torneo.value), viewer_id=yo
        )

        assert lista.enrollments == []

    async def test_el_organizador_sigue_viendolo_todo(self, publica):
        lista = await publica.lista(publica.creador)

        assert _quienes(lista) == publica.todos

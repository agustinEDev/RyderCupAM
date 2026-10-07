"""
Para jugar un Stableford o un Medal hace falta hándicap (#251, decidido el 7 oct 2026).

Como en los torneos de la RFEG: sin hándicap no se entra. El del perfil, o uno
personalizado que ponga el organizador. Se exige por los mismos caminos que el
género: crear la competición (el organizador queda inscrito), pedir plaza,
aceptar una invitación, la inscripción directa y aprobar una solicitud. Y el
organizador nunca puede dejar a nadie sin ninguno, ni tocarlo con las
inscripciones cerradas. La Ryder no cambia.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    StrokePlaySettingsDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    HandleEnrollmentRequestDTO,
    RequestEnrollmentRequestDTO,
    SetCustomHandicapRequestDTO,
)
from src.modules.competition.application.exceptions import HandicapEditNotAllowedError
from src.modules.competition.application.services.handicap_obligatorio import (
    HandicapRequiredError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.remove_custom_handicap_use_case import (
    RemoveCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    SetCustomHandicapUseCase,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


class _Usuarios:
    """Perfiles con género y, a veces, hándicap."""

    def __init__(self):
        self.handicaps: dict[UserId, float | None] = {}

    def alta(self, handicap: float | None) -> UserId:
        user_id = UserId(uuid4())
        self.handicaps[user_id] = handicap
        return user_id

    def _perfil(self, user_id):
        h = self.handicaps[user_id]
        return SimpleNamespace(
            id=user_id,
            gender=Gender.MALE,
            handicap=None if h is None else SimpleNamespace(value=h),
        )

    async def find_by_id(self, user_id):
        return self._perfil(user_id) if user_id in self.handicaps else None

    async def find_by_ids(self, ids):
        return [self._perfil(i) for i in ids if i in self.handicaps]


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = _Usuarios()
        self.creador = self.usuarios.alta(10.0)

    async def torneo(self, tipo="STABLEFORD", creador=None) -> CompetitionId:
        extra = {"tournament_type": tipo}
        if tipo != "RYDER_CUP":
            extra["stroke_play"] = StrokePlaySettingsDTO(category_limits=[Decimal("12.0")])
        respuesta = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), self.usuarios
        ).execute(
            CreateCompetitionRequestDTO(
                name="Medal de octubre",
                start_date=date(2030, 10, 12),
                end_date=date(2030, 10, 12),
                main_country="ES",
                play_mode="HANDICAP",
                visibility="PUBLIC",
                **extra,
            ),
            creador or self.creador,
        )
        return CompetitionId(respuesta.id)

    async def inscripcion(self, torneo, user_id, personalizado=None) -> Enrollment:
        inscripcion = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=torneo,
            user_id=user_id,
            custom_handicap=personalizado,
        )
        async with self.uow:
            await self.uow.enrollments.add(inscripcion)
        return inscripcion

    async def cerrar(self, torneo):
        async with self.uow:
            competicion = await self.uow.competitions.find_by_id(torneo)
            competicion.close_enrollments()
            await self.uow.competitions.update(competicion)


@pytest.fixture
def e():
    return _Escenario()


class TestParaEntrarHaceFaltaHandicap:
    async def test_crear_un_stableford_sin_handicap_no_se_puede(self, e):
        """Al crearla, el organizador queda inscrito como jugador."""
        sin = e.usuarios.alta(None)

        with pytest.raises(HandicapRequiredError, match="perfil"):
            await e.torneo(creador=sin)

    async def test_crear_una_ryder_sin_handicap_si(self, e):
        await e.torneo(tipo="RYDER_CUP", creador=e.usuarios.alta(None))

    async def test_pedir_plaza_sin_handicap_no_se_puede(self, e):
        torneo = await e.torneo()
        sin = e.usuarios.alta(None)

        with pytest.raises(HandicapRequiredError, match="perfil"):
            await RequestEnrollmentUseCase(e.uow, e.usuarios).execute(
                RequestEnrollmentRequestDTO(competition_id=torneo.value, user_id=sin.value)
            )

    async def test_pedir_plaza_con_handicap_si(self, e):
        torneo = await e.torneo()
        con = e.usuarios.alta(14.2)

        await RequestEnrollmentUseCase(e.uow, e.usuarios).execute(
            RequestEnrollmentRequestDTO(competition_id=torneo.value, user_id=con.value)
        )

    async def test_la_inscripcion_directa_sin_handicap_pide_uno_personalizado(self, e):
        torneo = await e.torneo()
        sin = e.usuarios.alta(None)

        with pytest.raises(HandicapRequiredError, match="personalizado"):
            await DirectEnrollPlayerUseCase(e.uow, e.usuarios).execute(
                DirectEnrollPlayerRequestDTO(competition_id=torneo.value, user_id=sin.value),
                e.creador,
            )

    async def test_la_inscripcion_directa_con_personalizado_si(self, e):
        torneo = await e.torneo()
        sin = e.usuarios.alta(None)

        await DirectEnrollPlayerUseCase(e.uow, e.usuarios).execute(
            DirectEnrollPlayerRequestDTO(
                competition_id=torneo.value, user_id=sin.value, custom_handicap=Decimal("18.0")
            ),
            e.creador,
        )

    async def test_aprobar_una_solicitud_de_quien_no_tiene_handicap_no_se_puede(self, e):
        torneo = await e.torneo()
        sin = e.usuarios.alta(None)
        solicitud = Enrollment.request(
            id=EnrollmentId.generate(), competition_id=torneo, user_id=sin
        )
        async with e.uow:
            await e.uow.enrollments.add(solicitud)

        with pytest.raises(HandicapRequiredError):
            await HandleEnrollmentUseCase(e.uow, e.usuarios).execute(
                HandleEnrollmentRequestDTO(enrollment_id=solicitud.id.value, action="APPROVE"),
                e.creador,
            )

    async def test_en_una_ryder_se_entra_sin_handicap_como_siempre(self, e):
        torneo = await e.torneo(tipo="RYDER_CUP")
        sin = e.usuarios.alta(None)

        await RequestEnrollmentUseCase(e.uow, e.usuarios).execute(
            RequestEnrollmentRequestDTO(competition_id=torneo.value, user_id=sin.value)
        )


class TestElHandicapPersonalizado:
    async def test_no_se_quita_si_se_queda_sin_ninguno(self, e):
        torneo = await e.torneo()
        sin = e.usuarios.alta(None)
        inscripcion = await e.inscripcion(torneo, sin, personalizado=Decimal("18.0"))

        with pytest.raises(HandicapRequiredError, match="sin hándicap"):
            await RemoveCustomHandicapUseCase(e.uow, e.usuarios).execute(
                str(inscripcion.id.value), e.creador
            )

    async def test_se_quita_si_tiene_el_del_perfil(self, e):
        torneo = await e.torneo()
        con = e.usuarios.alta(14.2)
        inscripcion = await e.inscripcion(torneo, con, personalizado=Decimal("18.0"))

        await RemoveCustomHandicapUseCase(e.uow, e.usuarios).execute(
            str(inscripcion.id.value), e.creador
        )

    async def test_con_las_inscripciones_cerradas_no_se_toca(self, e):
        torneo = await e.torneo()
        con = e.usuarios.alta(14.2)
        inscripcion = await e.inscripcion(torneo, con)
        await e.cerrar(torneo)

        with pytest.raises(HandicapEditNotAllowedError):
            await SetCustomHandicapUseCase(e.uow).execute(
                SetCustomHandicapRequestDTO(
                    enrollment_id=inscripcion.id.value, custom_handicap=Decimal("9.0")
                ),
                e.creador,
            )

    async def test_en_una_ryder_cerrada_si_como_siempre(self, e):
        torneo = await e.torneo(tipo="RYDER_CUP")
        inscripcion = await e.inscripcion(torneo, e.usuarios.alta(None))
        await e.cerrar(torneo)

        await SetCustomHandicapUseCase(e.uow).execute(
            SetCustomHandicapRequestDTO(
                enrollment_id=inscripcion.id.value, custom_handicap=Decimal("9.0")
            ),
            e.creador,
        )

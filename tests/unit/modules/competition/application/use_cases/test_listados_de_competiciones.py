"""
Los listados de competiciones que armaba la ruta, ahora en el caso de uso (fase 5, PR 3b).

`GET /competitions` juntaba en la ruta «mis competiciones» (creadas, inscritas e
invitaciones pendientes) y «las de los demás» (el listado sin las mías), leyendo
inscripciones e invitaciones con la unidad de trabajo. Ahora lo hace
`ListCompetitionsUseCase`, con las mismas reglas (L1-L7).
"""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

YO = UserId(uuid4())
OTRO = UserId(uuid4())


class _Zona:
    """Todas las competiciones se juegan en Madrid."""

    async def for_competition(self, competition: Competition) -> str | None:
        return "Europe/Madrid"


def _competicion(
    nombre: str,
    *,
    creador: UserId = OTRO,
    visibility: Visibility = Visibility.PUBLIC,
    estado: CompetitionStatus = CompetitionStatus.DRAFT,
    abre_dias_antes: int | None = None,
    empieza_en: int = 30,
) -> Competition:
    """Una competición en el estado pedido (DRAFT, ACTIVE o CLOSED)."""
    empieza = date.today() + timedelta(days=empieza_en)
    competicion = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creador,
        name=CompetitionName(nombre),
        dates=DateRange(empieza, empieza + timedelta(days=2)),
        location=Location(main_country="ES"),
        team_1_name="A",
        team_2_name="B",
        play_mode=PlayMode.SCRATCH,
        enrollment_opens_days_before=abre_dias_antes,
        visibility=visibility,
    )
    if estado in (CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED):
        competicion.activate()
    if estado is CompetitionStatus.CLOSED:
        competicion.close_enrollments()
    return competicion


async def _bd(*competiciones, inscripciones=(), invitaciones=()) -> InMemoryUnitOfWork:
    """La BD en memoria con esas competiciones, inscripciones (comp, estado) e invitaciones."""
    uow = InMemoryUnitOfWork()
    async with uow:
        for c in competiciones:
            await uow.competitions.add(c)
        for c, estado in inscripciones:
            await uow.enrollments.save(
                Enrollment(
                    id=EnrollmentId.generate(), competition_id=c.id, user_id=YO, status=estado
                )
            )
        for c in invitaciones:
            await uow.invitations.add(
                Invitation(
                    id=InvitationId.generate(),
                    competition_id=c.id,
                    inviter_id=c.creator_id,
                    invitee_email="yo@t.com",
                    invitee_user_id=YO,
                    status=InvitationStatus.PENDING,
                    expires_at=datetime.now() + timedelta(days=7),
                )
            )
        await uow.commit()
    return uow


def _nombres(competiciones) -> list[str]:
    return sorted(str(c.name) for c in competiciones)


class TestMisCompeticiones:
    async def test_l1_las_creadas_y_las_inscritas_sin_repetir_las_creadas(self):
        """Given una mía (en la que también estoy inscrito) y otra en la que estoy, When pido las mías, Then las dos, una vez cada una."""
        mia = _competicion("Mía", creador=YO)
        ajena = _competicion("Ajena")
        uow = await _bd(
            mia,
            ajena,
            _competicion("De nadie"),
            inscripciones=[(mia, EnrollmentStatus.APPROVED), (ajena, EnrollmentStatus.APPROVED)],
        )

        resultado = await ListCompetitionsUseCase(uow).mis_competiciones(YO, None)

        assert _nombres(resultado) == ["Ajena", "Mía"]
        assert next(str(c.name) for c in resultado) == "Mía"  # las creadas, primero

    async def test_l2_una_rechazada_sale_salvo_si_la_competicion_esta_activa(self):
        """Given rechazado en una cerrada y en una activa, When pido las mías, Then solo la activa."""
        cerrada = _competicion("Cerrada", estado=CompetitionStatus.CLOSED)
        activa = _competicion("Activa", estado=CompetitionStatus.ACTIVE)
        uow = await _bd(
            cerrada,
            activa,
            inscripciones=[
                (cerrada, EnrollmentStatus.REJECTED),
                (activa, EnrollmentStatus.REJECTED),
            ],
        )

        resultado = await ListCompetitionsUseCase(uow).mis_competiciones(YO, None)

        assert _nombres(resultado) == ["Activa"]

    async def test_l3_una_privada_con_invitacion_pendiente_entra(self):
        """Given una privada a la que me invitaron sin contestar, When pido las mías, Then sale."""
        privada = _competicion("Privada", visibility=Visibility.PRIVATE)
        uow = await _bd(privada, invitaciones=[privada])

        resultado = await ListCompetitionsUseCase(uow).mis_competiciones(
            YO, None, viewer_email="yo@t.com"
        )

        assert _nombres(resultado) == ["Privada"]

    @pytest.mark.parametrize(
        ("estados", "esperado"), [(["ACTIVE"], ["Programada"]), (["DRAFT"], [])]
    )
    async def test_l4_el_filtro_de_estado_va_despues_de_abrir(self, estados, esperado):
        """Given inscrito en una programada a la que ya le toca abrir, When filtro por estado, Then cuenta el estado ya abierto (BE #331)."""
        programada = _competicion("Programada", abre_dias_antes=5, empieza_en=3)
        uow = await _bd(programada, inscripciones=[(programada, EnrollmentStatus.APPROVED)])

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).mis_competiciones(
            YO, estados
        )

        assert _nombres(resultado) == esperado

    async def test_l5_una_privada_de_la_que_me_echaron_no_sale_aunque_este_activa(self):
        """Given rechazado en una privada activa, When pido las mías, Then no sale (BE #318)."""
        privada = _competicion(
            "Privada", visibility=Visibility.PRIVATE, estado=CompetitionStatus.ACTIVE
        )
        uow = await _bd(privada, inscripciones=[(privada, EnrollmentStatus.REJECTED)])

        resultado = await ListCompetitionsUseCase(uow).mis_competiciones(YO, None)

        assert resultado == []


class TestLasDeLosDemas:
    async def test_l6_sin_las_mias_las_inscritas_ni_las_invitadas(self):
        """Given una mía, una inscrita, una invitada y otra, When pido las de los demás, Then solo la otra."""
        mia = _competicion("Mía", creador=YO)
        inscrita = _competicion("Inscrita")
        invitada = _competicion("Invitada")
        uow = await _bd(
            mia,
            inscrita,
            invitada,
            _competicion("Otra"),
            inscripciones=[(inscrita, EnrollmentStatus.REQUESTED)],
            invitaciones=[invitada],
        )

        resultado = await ListCompetitionsUseCase(uow).las_de_los_demas(
            YO, None, viewer_email="yo@t.com"
        )

        assert _nombres(resultado) == ["Otra"]


class TestVariosEstados:
    async def test_l7_unidas_y_sin_duplicados(self):
        """Given una en borrador y otra activa, When pido los dos estados (uno repetido), Then las dos, una vez."""
        uow = await _bd(
            _competicion("Borrador"), _competicion("Activa", estado=CompetitionStatus.ACTIVE)
        )

        resultado = await ListCompetitionsUseCase(uow).listar(
            ["DRAFT", "ACTIVE", "active"], viewer_id=str(YO.value)
        )

        assert [str(c.name) for c in resultado].count("Activa") == 1
        assert _nombres(resultado) == ["Activa", "Borrador"]

    async def test_l7_sin_estados_trae_todas(self):
        """Given dos competiciones, When no filtro por estado, Then las dos."""
        uow = await _bd(
            _competicion("Borrador"), _competicion("Activa", estado=CompetitionStatus.ACTIVE)
        )

        resultado = await ListCompetitionsUseCase(uow).listar(None, viewer_id=str(YO.value))

        assert _nombres(resultado) == ["Activa", "Borrador"]


class TestLasProgramadasConFiltroDeEstado:
    """BE #814: con filtro de estado, la programada a la que le toca abrir salía o no según el orden."""

    def _programada(self, **como) -> Competition:
        return _competicion("Programada", abre_dias_antes=5, empieza_en=3, **como)

    @pytest.mark.parametrize(
        "estados",
        [["ACTIVE"], ["ACTIVE", "DRAFT"], ["DRAFT", "ACTIVE"], ["active"]],
        ids=["P1-activas", "P2-activas-y-borradores", "P3-borradores-y-activas", "P10-minusculas"],
    )
    async def test_p1_p2_p3_p10_la_que_toca_abrir_sale_abierta_y_una_vez(self, estados):
        """Given una programada a la que ya le toca abrir, When pido activas (con o sin borradores, en cualquier orden), Then sale una vez, abierta."""
        programada = self._programada()
        uow = await _bd(programada)

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
            estados, viewer_id=str(YO.value)
        )

        assert [(str(c.name), c.status) for c in resultado] == [
            ("Programada", CompetitionStatus.ACTIVE)
        ]
        async with uow:
            guardada = await uow.competitions.find_by_id(programada.id)
        assert guardada.status is CompetitionStatus.ACTIVE

    async def test_p4_pidiendo_borradores_ya_no_sale(self):
        """Given una programada a la que ya le toca abrir, When pido solo borradores, Then no sale: ya está abierta."""
        uow = await _bd(self._programada())

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
            ["DRAFT"], viewer_id=str(YO.value)
        )

        assert resultado == []

    async def test_p5_la_que_todavia_espera_no_sale_en_activas(self):
        """Given una programada que aún espera, When pido activas, Then no sale y sigue en borrador."""
        espera = _competicion("Espera", abre_dias_antes=5, empieza_en=30)
        uow = await _bd(espera)

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
            ["ACTIVE"], viewer_id=str(YO.value)
        )

        assert resultado == []
        assert espera.status is CompetitionStatus.DRAFT

    async def test_p6_el_creador_no_inscrito_la_ve_en_sus_activas(self):
        """Given mi programada, sin inscribirme, a la que ya le toca abrir, When pido mis activas, Then sale."""
        uow = await _bd(self._programada(creador=YO))

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).mis_competiciones(
            YO, ["ACTIVE"]
        )

        assert _nombres(resultado) == ["Programada"]

    async def test_p7_la_privada_ajena_ni_sale_ni_se_abre(self):
        """Given una privada ajena programada, When pido activas, Then ni sale ni se abre (BE #318)."""
        privada = self._programada(visibility=Visibility.PRIVATE)
        uow = await _bd(privada)

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
            ["ACTIVE"], viewer_id=str(YO.value)
        )

        assert resultado == []
        assert privada.status is CompetitionStatus.DRAFT

    async def test_p8_tambien_buscando_por_nombre(self):
        """Given la programada y otra activa que no coincide, When pido activas buscando por su nombre, Then solo sale la programada."""
        uow = await _bd(
            self._programada(), _competicion("Copa del club", estado=CompetitionStatus.ACTIVE)
        )

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
            ["ACTIVE"], search_name="Progra", viewer_id=str(YO.value)
        )

        assert _nombres(resultado) == ["Programada"]

    async def test_p9_sin_programadas_el_mismo_resultado_y_orden(self):
        """Given activas y cerradas, When pido activas y cerradas, Then primero las activas y luego las cerradas, como antes."""
        uow = await _bd(
            _competicion("Cerrada", estado=CompetitionStatus.CLOSED),
            _competicion("Activa 1", estado=CompetitionStatus.ACTIVE),
            _competicion("Borrador"),
            _competicion("Activa 2", estado=CompetitionStatus.ACTIVE),
        )

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
            ["ACTIVE", "CLOSED"], viewer_id=str(YO.value)
        )

        assert [str(c.name) for c in resultado] == ["Activa 1", "Activa 2", "Cerrada"]

    async def test_p11_pidiendo_solo_cerradas_no_se_abre_la_programada(self):
        """Given una programada a la que ya le toca abrir, When pido solo cerradas, Then ni sale ni se abre de paso."""
        programada = self._programada()
        uow = await _bd(programada)

        resultado = await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
            ["CLOSED"], viewer_id=str(YO.value)
        )

        assert resultado == []
        assert programada.status is CompetitionStatus.DRAFT

    @pytest.mark.parametrize("busqueda", [None, "Progra"], ids=["sin-busqueda", "con-busqueda"])
    async def test_p12_un_estado_que_no_existe_sigue_siendo_un_error(self, busqueda):
        """Given un estado que no existe entre los pedidos, When pido el listado, Then ValueError (la ruta da 400) sin abrir nada."""
        programada = self._programada()
        uow = await _bd(programada)

        with pytest.raises(ValueError):
            await ListCompetitionsUseCase(uow, zona_del_campo=_Zona()).listar(
                ["ACTIVE", "NO_EXISTE"], search_name=busqueda, viewer_id=str(YO.value)
            )

        assert programada.status is CompetitionStatus.DRAFT

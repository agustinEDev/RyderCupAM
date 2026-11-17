"""
Lo que decidió Agustín el 15 nov sobre el plazo de inscripción, tras la primera tanda.

| Caso | Situación                                                       | Qué pasa                                     |
|------|-----------------------------------------------------------------|----------------------------------------------|
| R3   | cerrada POR EL PLAZO, se mueve el torneo y el plazo nuevo es futuro | se reabre sola (como al reabrir) y se cerrará |
|      |                                                                 | en el plazo nuevo                            |
| R3   | cerrada por el plazo, se mueve pero el plazo nuevo ya pasó      | cambian las fechas, sigue CLOSED             |
| R3   | cerrada A MANO, se mueve el torneo                              | no se puede: hay que reabrir antes            |
| R3   | cerrada por el plazo, se toca otra cosa además de las fechas    | no se puede: en CLOSED solo las fechas        |
| R3   | sin plazo en el caso de uso                                     | como siempre: en CLOSED no se edita           |
| R3   | la mueve otro que no es el organizador (ni administrador)       | no                                            |
| R3   | ya en juego (IN_PROGRESS)                                       | no se mueve por este camino                   |
| R2   | apertura programada antes del plazo, abierta tarde al mirarla   | cuenta desde la hora programada: no exenta    |
| C4   | se cierra por fin (por el plazo o a mano) tras avisar           | se retira el aviso de «no se puede cerrar»    |
| C4   | se cierra sin haber avisado (D7, 16 nov)                        | no se retira nada                             |
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.exceptions import NotCompetitionCreatorError
from src.modules.competition.application.services.plazo_de_inscripcion import (
    EnrollmentDeadlinePassedError,
    PlazoDeInscripcion,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import (
    Competition,
    CompetitionStateError,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.instante_utc import ahora_en_utc
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio

# Se juega pasado mañana: el plazo es mañana a las 12:00 de Madrid
HOY = ahora_en_utc().date()
TORNEO = HOY + timedelta(days=2)
MANANA = datetime.combine(TORNEO - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
ANTES = MANANA - timedelta(days=5)
# Mañana a las 14:00 UTC: pasadas las 12:00 de Madrid en cualquier época del año
DESPUES = MANANA + timedelta(hours=14)
TODAVIA = MANANA + timedelta(hours=8)


class _Zonas:
    async def for_competition(self, competition):
        return "Europe/Madrid"

    async def for_course(self, golf_course_id):
        return "Europe/Madrid"


class _Avisos:
    def __init__(self):
        self.avisos: list[tuple] = []

    async def enrollments_closed(self, competition):
        self.avisos.append(("closed", competition.id))

    async def close_block_withdrawn(self, competition):
        self.avisos.append(("withdrawn", competition.id))

    def __getattr__(self, _nombre):
        async def nada(*_args, **_kwargs):
            return None

        return nada


class _Campos:
    async def find_by_id(self, _id):
        return None


def _plazo(ahora: datetime) -> PlazoDeInscripcion:
    return PlazoDeInscripcion(_Zonas(), reloj=lambda: ahora)


async def _competicion(uow, abierta: datetime | None = ANTES, dias: int | None = None):
    competition = Competition.create(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName(f"Copa {uuid4().hex[:6]}"),
        dates=DateRange(TORNEO, TORNEO + timedelta(days=1)),
        location=Location(main_country="ES"),
        team_1_name="Europa",
        team_2_name="USA",
        play_mode=PlayMode.SCRATCH,
        max_players=24,
        visibility=Visibility.PUBLIC,
        enrollment_opens_days_before=dias,
    )
    if abierta is not None:
        competition.activate(now=abierta)
    async with uow:
        await uow.competitions.add(competition)
    return competition


async def _cerrada(uow, por_el_plazo: bool) -> Competition:
    competition = await _competicion(uow)
    async with uow:
        competition.close_enrollments(by_deadline=por_el_plazo)
        await uow.competitions.update(competition)
    return competition


def _mover(uow, ahora: datetime, plazo=True) -> UpdateCompetitionUseCase:
    return UpdateCompetitionUseCase(
        uow,
        LocationBuilder(uow.countries),
        _Campos(),
        plazo=_plazo(ahora) if plazo else None,
    )


def _fechas(dias: int, **mas) -> UpdateCompetitionRequestDTO:
    inicio = TORNEO + timedelta(days=dias)
    return UpdateCompetitionRequestDTO(
        start_date=inicio, end_date=inicio + timedelta(days=1), **mas
    )


class TestMoverUnaCerradaPorElPlazo:
    async def test_con_el_plazo_nuevo_en_el_futuro_se_reabre_sola(self):
        """
        R3. Given cerrada por el plazo
        When el organizador mueve el torneo una semana más tarde
        Then se reabre (ya no «cerrada por el plazo»), abierta ahora y se cerrará en el
        plazo nuevo
        """
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)

        await _mover(uow, DESPUES).execute(competition.id, _fechas(7), competition.creator_id)

        async with uow:
            movida = await uow.competitions.find_by_id(competition.id)
        assert movida.status is CompetitionStatus.ACTIVE
        assert movida.dates.start_date == TORNEO + timedelta(days=7)
        assert movida.enrollment_closed_by_deadline is False
        assert movida.enrollment_opened_at == DESPUES.replace(tzinfo=None)
        assert await _plazo(DESPUES + timedelta(days=1)).le_toca_cerrarse(movida) is False
        assert await _plazo(DESPUES + timedelta(days=7)).le_toca_cerrarse(movida) is True

    async def test_con_el_plazo_nuevo_ya_pasado_cambian_las_fechas_y_sigue_cerrada(self):
        """R3. Given cerrada por el plazo / When se mueve pero su plazo nuevo ya pasó / Then CLOSED."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)

        await _mover(uow, DESPUES + timedelta(days=30)).execute(
            competition.id, _fechas(7), competition.creator_id
        )

        assert competition.status is CompetitionStatus.CLOSED
        assert competition.dates.start_date == TORNEO + timedelta(days=7)
        assert competition.enrollment_closed_by_deadline is True

    async def test_cerrada_a_mano_no_se_mueve(self):
        """R3. Given cerrada a mano / When se mueve el torneo / Then no: hay que reabrir antes."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=False)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow, DESPUES).execute(competition.id, _fechas(7), competition.creator_id)

        assert competition.status is CompetitionStatus.CLOSED
        assert competition.dates.start_date == TORNEO

    @pytest.mark.parametrize(
        "mas",
        [
            {"name": "Otro nombre"},
            {"max_players": 30},
            {"enrollment_opens_days_before": 5},
            {"visibility": "PRIVATE"},
        ],
    )
    async def test_en_cerrada_solo_las_fechas(self, mas):
        """R3. Given cerrada por el plazo / When llega algo más que las fechas / Then no."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow, DESPUES).execute(
                competition.id, _fechas(7, **mas), competition.creator_id
            )

        assert competition.status is CompetitionStatus.CLOSED
        assert competition.dates.start_date == TORNEO

    async def test_sin_fechas_tampoco(self):
        """R3. Given cerrada por el plazo / When no llegan fechas (solo el nombre) / Then no."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow, DESPUES).execute(
                competition.id, UpdateCompetitionRequestDTO(name="Otro"), competition.creator_id
            )

    async def test_sin_plazo_en_el_caso_de_uso_como_siempre(self):
        """R3. Given el caso de uso sin plazo / Then en CLOSED no se edita nada, como antes."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow, DESPUES, plazo=False).execute(
                competition.id, _fechas(7), competition.creator_id
            )

    async def test_la_entidad_no_deja_si_la_cerro_el_organizador(self):
        """R3. Given cerrada a mano / When se le piden fechas nuevas / Then CompetitionStateError."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=False)

        with pytest.raises(CompetitionStateError):
            competition.move_dates_closed_by_deadline(
                DateRange(TORNEO + timedelta(days=7), TORNEO + timedelta(days=8))
            )

    async def test_otro_que_no_es_el_organizador_no(self):
        """R3. Given cerrada por el plazo / When la mueve otro / Then no es el organizador."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)

        with pytest.raises(NotCompetitionCreatorError):
            await _mover(uow, DESPUES).execute(competition.id, _fechas(7), UserId.generate())

        assert competition.dates.start_date == TORNEO

    async def test_el_administrador_si(self):
        """R3. Given cerrada por el plazo / When la mueve un administrador / Then se mueve."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)

        await _mover(uow, DESPUES).execute(
            competition.id, _fechas(7), UserId.generate(), is_admin=True
        )

        assert competition.status is CompetitionStatus.ACTIVE

    async def test_la_entidad_no_deja_si_ya_esta_en_juego(self):
        """R3. Given cerrada por el plazo y ya empezada / Then no se mueve por este camino."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada(uow, por_el_plazo=True)
        competition.start()

        with pytest.raises(CompetitionStateError):
            competition.move_dates_closed_by_deadline(
                DateRange(TORNEO + timedelta(days=7), TORNEO + timedelta(days=8))
            )

    async def test_la_entidad_no_deja_si_no_esta_cerrada(self):
        """R3. Given ACTIVE / When se usa el camino de las cerradas / Then CompetitionStateError."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)

        with pytest.raises(CompetitionStateError):
            competition.move_dates_closed_by_deadline(
                DateRange(TORNEO + timedelta(days=7), TORNEO + timedelta(days=8))
            )


class TestAperturaProgramadaTardia:
    async def test_cuenta_desde_la_hora_programada(self):
        """
        R2. Given programada a 5 días (abre antes del plazo) y nadie la mira hasta pasado
        el plazo
        When alguien intenta apuntarse (y eso la abre)
        Then se abre con la hora programada: no queda exenta y no entra
        """
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow, abierta=None, dias=5)

        with pytest.raises(EnrollmentDeadlinePassedError):
            await RequestEnrollmentUseCase(
                uow, USUARIOS_CON_GENERO, zonas=_Zonas(), plazo=_plazo(DESPUES)
            ).execute(
                RequestEnrollmentRequestDTO(
                    competition_id=competition.id.value, user_id=UserId.generate().value
                )
            )

    async def test_la_apertura_queda_a_su_hora(self):
        """R2. Given la misma / When se abre al mirarla / Then abierta a las 0:00 de hace 3 días."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow, abierta=None, dias=5)
        programada = competition.scheduled_opening_at("Europe/Madrid")

        from src.modules.competition.application.services.enrollment_opener import (
            EnrollmentOpener,
        )

        async with uow:
            await EnrollmentOpener.abrir_las_que_toquen([competition], uow, _Zonas())

        assert competition.status is CompetitionStatus.ACTIVE
        assert competition.enrollment_opened_at == programada.astimezone(UTC).replace(tzinfo=None)
        assert programada.date() == TORNEO - timedelta(days=5)

    async def test_sin_programar_no_hay_hora(self):
        """R2. Given sin apertura programada / Then no hay hora programada."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)

        assert competition.scheduled_opening_at("Europe/Madrid") is None


class TestRetirarElAvisoDeBloqueo:
    async def _cerrar(self, uow, competition, avisos, ahora=DESPUES, por_el_plazo=True):
        caso = CloseEnrollmentsUseCase(
            uow, USUARIOS_CON_GENERO, actividad=avisos, plazo=_plazo(ahora)
        )
        if por_el_plazo:
            return await caso.cerrar_por_el_plazo(competition.id)
        return await caso.execute(
            CloseEnrollmentsRequestDTO(competition_id=competition.id.value),
            competition.creator_id,
        )

    async def test_cerrada_por_el_plazo_tras_avisar_se_retira_y_se_avisa_del_cierre(self):
        """C4, C5. Given avisada de que no se podía / When el plazo la cierra / Then las dos cosas."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        competition.mark_close_blocked_notified()
        avisos = _Avisos()

        await self._cerrar(uow, competition, avisos)

        assert ("withdrawn", competition.id) in avisos.avisos
        assert ("closed", competition.id) in avisos.avisos

    async def test_cerrada_a_mano_tras_avisar_tambien_se_retira(self):
        """C4. Given avisada / When la cierra el organizador / Then el aviso se retira."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        competition.mark_close_blocked_notified()
        avisos = _Avisos()

        await self._cerrar(uow, competition, avisos, por_el_plazo=False)

        assert avisos.avisos == [("withdrawn", competition.id)]

    async def test_sin_aviso_previo_no_se_retira_nada(self):
        """C4/D7 (16 nov). Given nunca apuntada / When se cierra / Then no se retira nada."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        avisos = _Avisos()

        await self._cerrar(uow, competition, avisos)

        assert ("withdrawn", competition.id) not in avisos.avisos

"""
Avisos de horario: cada jugador se entera de su salida o su partido (G, 22 oct 2026).

Tabla aprobada por Agustin. Aqui, DONDE avisa `competition` y A QUIEN; que se
publica y como lo prueban los tests del modulo social.

| #   | Caso                                                 | Aviso                                   |
|-----|------------------------------------------------------|-----------------------------------------|
| G1  | Generar las partidas de una franja                   | Cada jugador, su hora y su grupo        |
| G2  | Generar los partidos de una sesion Ryder, a mano     | Cada jugador, su partido, sin hora      |
| G2  | ... o al abrirse los sobres (mirar, entregar, abrir, | Igual, despues de guardar               |
|     | la agenda)                                           |                                         |
| G3  | Mover a una con hueco                                | Solo los de las dos partidas tocadas    |
| G3  | Mover a una nueva al final                           | El movido y los que pierden compañero   |
| G3  | Colocar a quien no tenia partida                     | Aviso nuevo para el, cambio para el resto|
| G3  | Reordenar                                            | Quien cambia de hora; sin cambio, nadie |
| G3  | Cambiar la hoja de salidas                           | Quien cambia de hora; sin cambio, nadie |
| G3  | Regenerar igual / distinto                           | Nadie / quien cambia                    |
| G3  | Reasignar los jugadores de un partido                | Los de ese partido, y fuera el que sale |
| G4  | Borrar las partidas / rehacer los sobres             | Se retiran todos los de la ronda        |
| G4  | Reabrir inscripciones (borra las partidas sin salir) | Se retiran                              |
| G3  | Cambiar a alguien de franja                          | Se le retira el de la franja que deja   |
| G5  | Cambiar los marcadores                               | Nada                                    |
| G8  | El feed falla                                        | La accion se guarda; WARNING            |
|     | Fourball / singles                                   | Compañero y rivales de cada lado        |
"""

import logging
from contextlib import asynccontextmanager
from datetime import date, time
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    ReopenEnrollmentsRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import WithdrawEnrollmentRequestDTO
from src.modules.competition.application.dto.partidas_dto import GenerateTeeGroupsRequestDTO
from src.modules.competition.application.dto.round_match_dto import (
    GenerateMatchesRequestDTO,
    GetScheduleRequestDTO,
    ManualPairingDTO,
    ReassignMatchPlayersRequestDTO,
    TeeSheetDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
    TeeTimeAssignment,
)
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.services.salidas_de_la_ronda import de_las_partidas
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    MarcarNoPresentadoUseCase,
)
from src.modules.competition.application.use_cases.partidas_use_case import (
    BorrarPartidasUseCase,
    CambiarMarcadoresUseCase,
    GenerarPartidasUseCase,
    MoverJugadorUseCase,
    ReordenarPartidasUseCase,
)
from src.modules.competition.application.use_cases.plazas_en_franjas_use_case import (
    CogerPlazaUseCase,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    ReassignMatchPlayersUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.reset_envelopes_use_case import (
    ResetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    RevealEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.orden_de_salida import OrdenDeSalida
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import (
    TeamAssignment as TeamAssignmentVO,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
    CompetitionActivityPublisher,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
)
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    VIERNES,
    _Escenario,
)
from tests.unit.modules.competition.application.use_cases.test_partidos_al_abrir_los_sobres import (
    _PASADO_EL_PLAZO,
    _montar,
    _Reloj,
    _Zona,
)

pytestmark = pytest.mark.asyncio


class _Salidas(CompetitionActivityPublisherInterface):
    """Apunta cada aviso de salida; lo demas no interesa aqui."""

    def __init__(self):
        self.llamadas: list[tuple[RoundId, dict[UserId, TeeTimeAssignment], list[UserId]]] = []

    async def tee_times(self, competition, round_id, assigned, withdrawn):
        self.llamadas.append((round_id, {s.user_id: s for s in assigned}, list(withdrawn)))

    @property
    def avisados(self) -> dict[UserId, TeeTimeAssignment]:
        """Todos los avisos, de todas las llamadas."""
        return {u: s for _, avisos, _ in self.llamadas for u, s in avisos.items()}

    @property
    def retirados(self) -> list[UserId]:
        return [u for _, _, fuera in self.llamadas for u in fuera]

    async def _nada(self, *_args, **_kwargs):
        return None

    enrolled = left = cancelled = invited = invitation_withdrawn = _nada  # type: ignore[assignment]
    requests_closed = request_rejected = match_finished = completed = _nada  # type: ignore[assignment]
    reopened = made_private = deleted = _nada  # type: ignore[assignment]


class _Roto(_Salidas):
    """El feed caido."""

    async def tee_times(self, competition, round_id, assigned, withdrawn):
        raise RuntimeError("feed caido")


# === Stroke play ===


def _casos(escenario: _Escenario, actividad) -> dict:
    jugadores = JugadoresDeLaPartida(escenario.campos, escenario.usuarios)
    comun = {
        "uow": escenario.uow,
        "zonas": escenario.zonas,
        "user_repository": escenario.usuarios,
        "reloj": lambda: escenario.ahora,
        "actividad": actividad,
    }
    return {
        "generar": GenerarPartidasUseCase(jugadores=jugadores, **comun),
        "mover": MoverJugadorUseCase(jugadores=jugadores, **comun),
        "reordenar": ReordenarPartidasUseCase(**comun),
        "marcadores": CambiarMarcadoresUseCase(**comun),
        "borrar": BorrarPartidasUseCase(**comun),
    }


async def _con_plazas(n: int) -> tuple[_Escenario, list[UserId]]:
    """N jugadores con plaza en la mañana, de hándicap N a 1."""
    escenario = _Escenario()
    escenario.competicion.add_golf_course(escenario.manana.golf_course_id, CountryCode("ES"))
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in range(n, 0, -1)]
    return escenario, jugadores


async def _generar(escenario, actividad, orden=OrdenDeSalida.HIGH_FIRST):
    return await _casos(escenario, actividad)["generar"].execute(
        escenario.manana.id.value,
        GenerateTeeGroupsRequestDTO(order=orden),
        escenario.creador,
        False,
    )


async def _generadas(n: int) -> tuple[_Escenario, list[UserId]]:
    """Generadas sin avisar: el punto de partida de los cambios."""
    escenario, jugadores = await _con_plazas(n)
    await _generar(escenario, None)
    return escenario, jugadores


async def _partidas(escenario):
    return await escenario.uow.partidas.de_la_franja(escenario.manana.id)


async def _mover(escenario, actividad, jugador, destino=None, intercambiar_con=None):
    return await _casos(escenario, actividad)["mover"].execute(
        escenario.manana.id.value,
        jugador.value,
        destino.value if destino else None,
        intercambiar_con.value if intercambiar_con else None,
        escenario.creador,
        False,
    )


def _hoja(primera=time(9, 0), ultima=time(10, 0), intervalo=10, tamano=4) -> TeeSheetDTO:
    return TeeSheetDTO(
        first_tee_time=primera, last_tee_time=ultima, interval_minutes=intervalo, group_size=tamano
    )


async def _cambiar_hoja(escenario, actividad, hoja: TeeSheetDTO):
    return await UpdateRoundUseCase(
        escenario.uow,
        jugadores=JugadoresDeLaPartida(escenario.campos, escenario.usuarios),
        actividad=actividad,
    ).execute(
        UpdateRoundRequestDTO(round_id=escenario.manana.id.value, tee_sheet=hoja),
        escenario.creador,
    )


class TestG1GenerarPartidas:
    async def test_every_player_gets_its_tee_time_and_group_in_one_batch(self):
        escenario, _ = await _con_plazas(6)
        salidas = _Salidas()

        await _generar(escenario, salidas)

        primera, segunda = await _partidas(escenario)
        assert len(salidas.llamadas) == 1
        round_id, avisos, fuera = salidas.llamadas[0]
        assert round_id == escenario.manana.id
        assert fuera == []
        assert set(avisos) == set(primera.user_ids) | set(segunda.user_ids)
        quien = primera.user_ids[0]
        assert avisos[quien] == TeeTimeAssignment(
            user_id=quien,
            round_date=VIERNES,
            session_type=SessionType.MORNING,
            tee_time=time(9, 0),
            partner_ids=tuple(primera.user_ids[1:]),
            opponent_ids=(),
            match_id=None,
            changed=False,
        )
        assert {avisos[u].tee_time for u in segunda.user_ids} == {time(9, 10)}

    async def test_regenerating_the_same_groups_notifies_nobody(self):
        escenario, _ = await _generadas(6)
        salidas = _Salidas()

        await _generar(escenario, salidas)

        assert salidas.llamadas == []

    async def test_regenerating_other_groups_notifies_who_changes(self):
        escenario, jugadores = await _generadas(8)
        salidas = _Salidas()

        await _generar(escenario, salidas, OrdenDeSalida.LOW_FIRST)

        # Los dos grupos siguen juntos, pero cambian de hora: todos cambian
        assert set(salidas.avisados) == set(jugadores)
        assert all(s.changed for s in salidas.avisados.values())
        assert salidas.retirados == []

    async def test_without_publisher_nothing_breaks(self):
        escenario, _ = await _con_plazas(4)

        vista = await _generar(escenario, None)

        assert len(vista.groups) == 1

    async def test_g8_a_broken_feed_does_not_undo_the_groups(self, caplog):
        escenario, _ = await _con_plazas(4)

        with caplog.at_level(logging.WARNING):
            await _generar(escenario, _Roto())

        assert len(await _partidas(escenario)) == 1
        assert "Could not publish activity notice tee_times" in caplog.text


class TestG3Mover:
    async def test_to_one_with_room_only_both_groups(self):
        # 10 de 4: 4 + 4 + 2
        escenario, _ = await _generadas(10)
        primera, segunda, tercera = await _partidas(escenario)
        quien = primera.user_ids[0]
        salidas = _Salidas()

        await _mover(escenario, salidas, quien, tercera.id)

        assert set(salidas.avisados) == set(primera.user_ids) | set(tercera.user_ids)
        assert not set(salidas.avisados) & set(segunda.user_ids)
        assert salidas.avisados[quien].tee_time == time(9, 20)
        assert set(salidas.avisados[quien].partner_ids) == set(tercera.user_ids)
        assert all(s.changed for s in salidas.avisados.values())
        assert salidas.retirados == []

    async def test_swapping_only_both_groups(self):
        escenario, _ = await _generadas(12)
        primera, segunda, tercera = await _partidas(escenario)
        a, x = primera.user_ids[0], segunda.user_ids[0]
        salidas = _Salidas()

        await _mover(escenario, salidas, a, segunda.id, intercambiar_con=x)

        assert set(salidas.avisados) == set(primera.user_ids) | set(segunda.user_ids)
        assert salidas.avisados[x].tee_time == time(9, 0)
        assert not set(salidas.avisados) & set(tercera.user_ids)

    async def test_to_a_new_one_the_untouched_group_is_not_notified(self):
        # 5 de 4: 3 + 2
        escenario, _ = await _generadas(5)
        primera, segunda = await _partidas(escenario)
        quien = primera.user_ids[0]
        salidas = _Salidas()

        await _mover(escenario, salidas, quien)

        assert set(salidas.avisados) == set(primera.user_ids)
        assert salidas.avisados[quien].tee_time == time(9, 20)
        assert salidas.avisados[quien].partner_ids == ()
        assert not set(salidas.avisados) & set(segunda.user_ids)

    async def test_placing_someone_without_a_group(self):
        escenario, _ = await _generadas(3)
        tarde = await escenario.con_plaza("9.0")
        (partida,) = await _partidas(escenario)
        salidas = _Salidas()

        await _mover(escenario, salidas, tarde, partida.id)

        assert salidas.avisados[tarde].changed is False
        assert {u for u, s in salidas.avisados.items() if s.changed} == set(partida.user_ids)


class TestG3Reordenar:
    async def test_swapping_two_groups_notifies_both(self):
        escenario, _ = await _generadas(8)
        primera, segunda = await _partidas(escenario)
        salidas = _Salidas()

        await _casos(escenario, salidas)["reordenar"].execute(
            escenario.manana.id.value,
            [segunda.id.value, primera.id.value],
            escenario.creador,
            False,
        )

        assert {u: s.tee_time for u, s in salidas.avisados.items()} == {
            **{u: time(9, 10) for u in primera.user_ids},
            **{u: time(9, 0) for u in segunda.user_ids},
        }
        assert all(s.changed for s in salidas.avisados.values())

    async def test_same_order_notifies_nobody(self):
        escenario, _ = await _generadas(8)
        salidas = _Salidas()

        await _casos(escenario, salidas)["reordenar"].execute(
            escenario.manana.id.value,
            [p.id.value for p in await _partidas(escenario)],
            escenario.creador,
            False,
        )

        assert salidas.llamadas == []


class TestG3HojaDeSalidas:
    async def test_moving_the_first_tee_time_notifies_everyone(self):
        escenario, jugadores = await _generadas(8)
        salidas = _Salidas()

        await _cambiar_hoja(escenario, salidas, _hoja(primera=time(9, 30)))

        assert set(salidas.avisados) == set(jugadores)
        primera, segunda = await _partidas(escenario)
        assert {salidas.avisados[u].tee_time for u in primera.user_ids} == {time(9, 30)}
        assert {salidas.avisados[u].tee_time for u in segunda.user_ids} == {time(9, 40)}
        assert all(s.changed for s in salidas.avisados.values())

    async def test_only_who_changes_hour(self):
        escenario, _ = await _generadas(8)
        _, segunda = await _partidas(escenario)
        salidas = _Salidas()

        # La primera sigue a las 9:00; la segunda pasa de 9:10 a 9:05
        await _cambiar_hoja(escenario, salidas, _hoja(intervalo=5))

        assert set(salidas.avisados) == set(segunda.user_ids)
        assert {s.tee_time for s in salidas.avisados.values()} == {time(9, 5)}

    async def test_a_sheet_that_changes_nobodys_hour_notifies_nobody(self):
        escenario, _ = await _generadas(8)
        salidas = _Salidas()

        await _cambiar_hoja(escenario, salidas, _hoja(ultima=time(11, 0)))

        assert salidas.llamadas == []


class TestG4yG5:
    async def test_g4_deleting_the_groups_withdraws_every_notice(self):
        escenario, jugadores = await _generadas(6)
        salidas = _Salidas()

        await _casos(escenario, salidas)["borrar"].execute(
            escenario.manana.id.value, escenario.creador, False
        )

        assert len(salidas.llamadas) == 1
        round_id, avisos, fuera = salidas.llamadas[0]
        assert round_id == escenario.manana.id
        assert avisos == {}
        assert set(fuera) == set(jugadores)

    async def test_g5_changing_the_markers_notifies_nobody(self):
        escenario, _ = await _generadas(3)
        (partida,) = await _partidas(escenario)
        a, b, c = partida.user_ids
        salidas = _Salidas()

        await _casos(escenario, salidas)["marcadores"].execute(
            partida.id.value,
            [(a.value, c.value), (c.value, b.value), (b.value, a.value)],
            escenario.creador,
            False,
        )

        assert salidas.llamadas == []

    async def test_g4_reopening_enrollments_withdraws_the_deleted_groups(self):
        escenario, jugadores = await _generadas(5)
        salidas = _Salidas()

        await ReopenEnrollmentsUseCase(escenario.uow, actividad=salidas).execute(
            ReopenEnrollmentsRequestDTO(competition_id=escenario.competicion.id.value),
            escenario.creador,
        )

        assert [(r, a) for r, a, _ in salidas.llamadas] == [(escenario.manana.id, {})]
        assert set(salidas.retirados) == set(jugadores)

    async def test_g3_changing_someone_to_another_window_withdraws_his_old_notice(self):
        """Y a los que se quedan sin él en su grupo, «ha cambiado tu salida» (22 oct)."""
        escenario, jugadores = await _generadas(3)
        quien = jugadores[0]
        salidas = _Salidas()

        await CogerPlazaUseCase(escenario.uow, actividad=salidas).execute(
            escenario.tarde.id, quien, escenario.creador, en_lugar_de=escenario.manana.id
        )

        (llamada,) = salidas.llamadas
        assert llamada[0] == escenario.manana.id
        assert llamada[2] == [quien]
        assert set(llamada[1]) == set(jugadores[1:])
        assert all(s.changed and quien not in s.partner_ids for s in llamada[1].values())

    async def test_taking_a_place_without_leaving_one_withdraws_nothing(self):
        escenario, _ = await _generadas(3)
        nuevo = await escenario.con_plaza("9.0")
        # Inscrito y sin franja: la coge en la de tarde sin dejar ninguna
        await escenario.uow.plazas.quitar(escenario.manana.id, nuevo)
        salidas = _Salidas()

        await CogerPlazaUseCase(escenario.uow, actividad=salidas).execute(
            escenario.tarde.id, nuevo, escenario.creador
        )

        assert salidas.llamadas == []


class TestG3Recolocados:
    """
    Decidido por Agustin el 22 oct: quien se ve recolocado por la baja, el
    cambio de franja o el no presentado de otro recibe «ha cambiado tu salida»,
    con el mismo criterio de cambio real.
    """

    @staticmethod
    async def _en_partidas(*tamanos: int) -> tuple[_Escenario, list[Partida]]:
        """Partidas de esos tamaños en la mañana, sin salir ninguna."""
        escenario = _Escenario()
        await escenario.guardar()
        for h in range(sum(tamanos), 0, -1):
            await escenario.con_plaza(f"{h}.0")
        await escenario.generar()
        jugadores = [j for p in await _partidas(escenario) for j in p.jugadores]
        partidas, desde = [], 0
        for numero, tamano in enumerate(tamanos, start=1):
            partidas.append(
                Partida.crear(
                    escenario.competicion.id,
                    escenario.manana.id,
                    numero,
                    jugadores[desde : desde + tamano],
                )
            )
            desde += tamano
        await escenario.uow.partidas.reemplazar_franja(escenario.manana.id, partidas)
        return escenario, partidas

    async def test_leaving_a_lone_group_moves_up_the_ones_behind(self):
        escenario, (sola, detras) = await self._en_partidas(1, 3)
        (quien,) = sola.user_ids
        salidas = _Salidas()

        await CogerPlazaUseCase(escenario.uow, actividad=salidas).execute(
            escenario.tarde.id, quien, escenario.creador, en_lugar_de=escenario.manana.id
        )

        assert salidas.retirados == [quien]
        assert set(salidas.avisados) == set(detras.user_ids)
        assert {(s.tee_time, s.changed) for s in salidas.avisados.values()} == {(time(9, 0), True)}

    async def test_leaving_a_group_only_tells_its_group(self):
        escenario, (primera, segunda) = await self._en_partidas(3, 2)
        quien = primera.user_ids[0]
        salidas = _Salidas()

        await CogerPlazaUseCase(escenario.uow, actividad=salidas).execute(
            escenario.tarde.id, quien, escenario.creador, en_lugar_de=escenario.manana.id
        )

        assert set(salidas.avisados) == set(primera.user_ids[1:])
        assert not set(salidas.avisados) & set(segunda.user_ids)

    async def test_withdrawing_moves_up_the_ones_behind(self):
        escenario, (sola, detras) = await self._en_partidas(1, 3)
        (quien,) = sola.user_ids
        (inscripcion,) = await escenario.uow.enrollments.find_by_user_ids_and_competition(
            [quien], escenario.competicion.id
        )
        salidas = _Salidas()

        await WithdrawEnrollmentUseCase(escenario.uow, actividad=salidas).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), quien
        )

        assert quien in salidas.retirados
        assert set(salidas.avisados) == set(detras.user_ids)
        assert all(s.tee_time == time(9, 0) and s.changed for s in salidas.avisados.values())

    async def test_a_no_show_brings_company_and_both_groups_are_told(self):
        escenario, (sola, cuatro, ultima) = await self._en_partidas(2, 4, 4)
        escenario.ahora = A_LAS_NUEVE_Y_CINCO
        falta, queda = sola.user_ids
        viene = cuatro.user_ids[-1]
        salidas = _Salidas()

        await MarcarNoPresentadoUseCase(
            uow=escenario.uow,
            zonas=escenario.zonas,
            reloj=lambda: escenario.ahora,
            actividad=salidas,
        ).execute(sola.id.value, falta.value, escenario.creador, False)

        assert set(salidas.avisados) == {queda, viene, *cuatro.user_ids[:-1]}
        assert salidas.avisados[viene].tee_time == time(9, 0)
        assert set(salidas.avisados[queda].partner_ids) == {viene}
        assert falta not in salidas.avisados
        assert not set(salidas.avisados) & set(ultima.user_ids)
        assert all(s.changed for s in salidas.avisados.values())

    async def test_a_no_show_without_anyone_to_bring_tells_nobody(self):
        escenario, (sola, _) = await self._en_partidas(3, 2)
        escenario.ahora = A_LAS_NUEVE_Y_CINCO
        salidas = _Salidas()

        await MarcarNoPresentadoUseCase(
            uow=escenario.uow,
            zonas=escenario.zonas,
            reloj=lambda: escenario.ahora,
            actividad=salidas,
        ).execute(sola.id.value, sola.user_ids[0].value, escenario.creador, False)

        assert salidas.llamadas == []


class TestG3OrdenDeLasPublicaciones:
    """
    Revision del 22 oct: cada publicacion va tras su commit, en su sesion y sin
    orden garantizado. Si la de una accion vieja llega la ultima, el aviso que
    queda tiene que ser el de ahora, no el de su foto.
    """

    async def test_publications_in_reverse_order_leave_the_current_state(self):
        escenario, _ = await _con_plazas(8)
        social_uow = InMemorySocialUnitOfWork()
        actividad = CompetitionActivityPublisher(
            PublishCompetitionNoticesUseCase(social_uow, InMemoryUserUnitOfWork()),
            standings=None,
            competition_uow=escenario.uow,
        )
        generar, mover = _Llamadas(), _Llamadas()
        await _generar(escenario, generar)
        primera, segunda = await _partidas(escenario)
        await _mover(escenario, mover, primera.user_ids[0], segunda.id, segunda.user_ids[0])

        # La de mover llega antes que la de generar
        for llamada in [*mover.llamadas, *generar.llamadas]:
            await actividad.tee_times(*llamada)

        async with social_uow:
            guardados = {
                e.user_id: e.payload
                for e in await social_uow.activity_events.find_in(
                    [
                        ActivitySlice(
                            user_ids=tuple(u for p in (primera, segunda) for u in p.user_ids),
                            types=frozenset(ActivityEventType),
                        )
                    ],
                    limit=100,
                )
            }
        ahora = de_las_partidas(escenario.manana, await _partidas(escenario))
        assert set(guardados) == set(ahora)
        for jugador, salida in ahora.items():
            assert guardados[jugador]["tee_time"] == salida.tee_time.strftime("%H:%M")
            assert set(guardados[jugador]["partner_ids"]) == {
                str(u.value) for u in salida.partner_ids
            }


class _Llamadas(_Salidas):
    """Apunta las llamadas tal cual, para repetirlas en otro orden."""

    async def tee_times(self, competition, round_id, assigned, withdrawn):
        self.llamadas.append((competition, round_id, assigned, withdrawn))


# === Ryder ===


class _Ryder:
    """Una cerrada en modo manual con dos equipos y una sesion de su formato."""

    def __init__(self, formato: MatchFormat, por_equipo: int):
        self.uow = InMemoryUnitOfWork()
        self.organizador = UserId(uuid4())
        self.equipo_a = [UserId(uuid4()) for _ in range(por_equipo)]
        self.equipo_b = [UserId(uuid4()) for _ in range(por_equipo)]
        self.campos = AsyncMock()
        self.campos.find_by_id.return_value = None
        self.usuarios = AsyncMock()
        self.usuarios.find_by_id.return_value = None
        self.competicion = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=self.organizador,
            name=CompetitionName("Ryder de los sabados"),
            dates=DateRange(start_date=date(2026, 10, 25), end_date=date(2026, 10, 26)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            max_players=24,
            team_assignment=TeamAssignmentVO.MANUAL,
            team_1_name="Europa",
            team_2_name="Estados Unidos",
        )
        self.competicion.activate()
        self.competicion.close_enrollments()
        self.ronda = Round.create(
            competition_id=self.competicion.id,
            golf_course_id=GolfCourseId(uuid4()),
            round_date=date(2026, 10, 25),
            session_type=SessionType.MORNING,
            match_format=formato,
        )
        self.ronda.mark_teams_assigned()

    async def guardar(self):
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
            await self.uow.rounds.add(self.ronda)
            await self.uow.team_assignments.add(
                TeamAssignment.create(
                    competition_id=self.competicion.id,
                    mode=TeamAssignmentMode.MANUAL,
                    team_a_player_ids=self.equipo_a,
                    team_b_player_ids=self.equipo_b,
                )
            )
            for uid in self.equipo_a + self.equipo_b:
                await self.uow.enrollments.add(
                    Enrollment(
                        id=EnrollmentId.generate(),
                        competition_id=self.competicion.id,
                        user_id=uid,
                        status=EnrollmentStatus.APPROVED,
                    )
                )
        return self

    def generador(self, actividad=None) -> GenerateMatchesUseCase:
        return GenerateMatchesUseCase(
            uow=self.uow,
            golf_course_repository=self.campos,
            user_repository=self.usuarios,
            actividad=actividad,
        )

    async def generar(self, actividad=None, emparejamientos=None, regenerar=False):
        return await self.generador(actividad).execute(
            GenerateMatchesRequestDTO(
                round_id=self.ronda.id.value,
                manual_pairings=[
                    ManualPairingDTO(
                        team_a_player_ids=[u.value for u in a],
                        team_b_player_ids=[u.value for u in b],
                    )
                    for a, b in emparejamientos
                ]
                if emparejamientos
                else None,
            ),
            self.organizador,
            allow_regeneration=regenerar,
        )

    async def partidos(self):
        return sorted(
            await self.uow.matches.find_by_round(self.ronda.id), key=lambda m: m.match_number
        )


class TestG2GenerarPartidos:
    async def test_singles_each_player_its_rival_without_hour(self):
        ryder = await _Ryder(MatchFormat.SINGLES, 2).guardar()
        salidas = _Salidas()

        await ryder.generar(salidas)

        primero, _ = await ryder.partidos()
        a, b = ryder.equipo_a[0], ryder.equipo_b[0]
        assert len(salidas.llamadas) == 1
        assert set(salidas.avisados) == set(ryder.equipo_a + ryder.equipo_b)
        assert salidas.avisados[a] == TeeTimeAssignment(
            user_id=a,
            round_date=date(2026, 10, 25),
            session_type=SessionType.MORNING,
            tee_time=None,
            partner_ids=(),
            opponent_ids=(b,),
            match_id=primero.id,
            changed=False,
        )
        assert salidas.avisados[b].opponent_ids == (a,)

    async def test_fourball_partner_and_both_rivals(self):
        ryder = await _Ryder(MatchFormat.FOURBALL, 4).guardar()
        salidas = _Salidas()

        await ryder.generar(salidas)

        a1, a2 = ryder.equipo_a[:2]
        b1, b2 = ryder.equipo_b[:2]
        assert salidas.avisados[a1].partner_ids == (a2,)
        assert salidas.avisados[a1].opponent_ids == (b1, b2)
        assert salidas.avisados[b2].partner_ids == (b1,)
        assert salidas.avisados[b2].opponent_ids == (a1, a2)

    async def test_regenerating_the_same_pairings_notifies_nobody(self):
        ryder = await _Ryder(MatchFormat.SINGLES, 2).guardar()
        await ryder.generar()
        salidas = _Salidas()

        await ryder.generar(salidas, regenerar=True)

        assert salidas.llamadas == []

    async def test_regenerating_other_pairings_notifies_who_changes(self):
        ryder = await _Ryder(MatchFormat.SINGLES, 3).guardar()
        (a1, a2, a3), (b1, b2, b3) = ryder.equipo_a, ryder.equipo_b
        await ryder.generar(emparejamientos=[([a1], [b1]), ([a2], [b2]), ([a3], [b3])])
        salidas = _Salidas()

        await ryder.generar(
            salidas,
            emparejamientos=[([a1], [b2]), ([a2], [b1]), ([a3], [b3])],
            regenerar=True,
        )

        assert set(salidas.avisados) == {a1, a2, b1, b2}
        assert all(s.changed for s in salidas.avisados.values())
        assert salidas.avisados[a1].opponent_ids == (b2,)

    async def test_g8_a_broken_feed_does_not_undo_the_matches(self, caplog):
        ryder = await _Ryder(MatchFormat.SINGLES, 2).guardar()

        with caplog.at_level(logging.WARNING):
            respuesta = await ryder.generar(_Roto())

        assert respuesta.matches_generated == 2
        assert len(await ryder.partidos()) == 2
        assert "Could not publish activity notice tee_times" in caplog.text

    async def test_a_failed_generation_notifies_nobody(self):
        ryder = await _Ryder(MatchFormat.FOURBALL, 1).guardar()
        salidas = _Salidas()

        with pytest.raises(Exception):
            await ryder.generar(salidas)

        assert salidas.llamadas == []


class TestG3Reasignar:
    async def test_the_match_players_and_out_who_leaves(self):
        ryder = await _Ryder(MatchFormat.SINGLES, 3).guardar()
        (a1, a2, a3), (b1, b2, _) = ryder.equipo_a, ryder.equipo_b
        await ryder.generar(emparejamientos=[([a1], [b1]), ([a2], [b2])])
        primero, _ = await ryder.partidos()
        salidas = _Salidas()

        await ReassignMatchPlayersUseCase(
            ryder.uow, ryder.campos, ryder.usuarios, actividad=salidas
        ).execute(
            ReassignMatchPlayersRequestDTO(
                match_id=primero.id.value,
                team_a_player_ids=[a3.value],
                team_b_player_ids=[b1.value],
            ),
            ryder.organizador,
        )

        assert set(salidas.avisados) == {a3, b1}
        assert salidas.avisados[a3].changed is False
        assert salidas.avisados[b1].changed is True
        assert salidas.avisados[b1].opponent_ids == (a3,)
        assert salidas.retirados == [a1]
        assert not {a2, b2} & set(salidas.avisados)


class TestG4RehacerLosSobres:
    async def test_resetting_withdraws_every_notice_of_the_session(self):
        torneo = await _montar()
        await torneo.entregan_los_dos()
        await torneo.abrir().execute(torneo.ronda_id.value, torneo.organizador)
        salidas = _Salidas()

        await ResetEnvelopesUseCase(torneo.uow, torneo.usuarios, actividad=salidas).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        assert [(r, a) for r, a, _ in salidas.llamadas] == [(torneo.ronda_id, {})]
        assert set(salidas.retirados) == set(torneo.equipo_a + torneo.equipo_b)


class TestG2AlAbrirLosSobres:
    """Los partidos que crea la apertura avisan igual, despues de guardar."""

    @staticmethod
    def _con_avisos(torneo, salidas):
        def generador():
            return GenerateMatchesUseCase(
                uow=torneo.uow,
                golf_course_repository=torneo.campos,
                user_repository=torneo.usuarios,
                handicap_service=torneo.rfeg,
                actividad=salidas,
            )

        torneo.generador = generador
        return torneo

    async def test_looking_after_the_deadline(self):
        salidas = _Salidas()
        torneo = self._con_avisos(await _montar(), salidas)
        await torneo.entregan_los_dos()

        await torneo.mirar(_Reloj(_PASADO_EL_PLAZO)).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        assert len(salidas.llamadas) == 1
        assert set(salidas.avisados) == set(torneo.equipo_a + torneo.equipo_b)
        assert salidas.avisados[torneo.equipo_a[0]].opponent_ids == (torneo.equipo_b[0],)

    async def test_automatic_envelopes_when_nobody_submitted(self):
        salidas = _Salidas()
        torneo = self._con_avisos(await _montar(), salidas)

        await torneo.mirar(_Reloj(_PASADO_EL_PLAZO)).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        assert len(await torneo.partidos()) == 2
        assert set(salidas.avisados) == set(torneo.equipo_a + torneo.equipo_b)
        assert all(not s.changed for s in salidas.avisados.values())

    async def test_the_second_captain_submitting(self):
        salidas = _Salidas()
        torneo = self._con_avisos(await _montar(), salidas)

        await torneo.entregan_los_dos(sin_esperar=(True, True))

        assert set(salidas.avisados) == set(torneo.equipo_a + torneo.equipo_b)

    async def test_opening_by_hand(self):
        salidas = _Salidas()
        torneo = self._con_avisos(await _montar(), salidas)
        await torneo.entregan_los_dos()

        await RevealEnvelopesUseCase(
            torneo.uow, torneo.usuarios, _Zona(None), generador=torneo.generador()
        ).execute(torneo.ronda_id.value, torneo.organizador)

        assert set(salidas.avisados) == set(torneo.equipo_a + torneo.equipo_b)

    async def test_reading_the_schedule(self):
        salidas = _Salidas()
        torneo = self._con_avisos(await _montar(), salidas)
        await torneo.entregan_los_dos()
        mesa = EnvelopeDesk(
            torneo.uow, torneo.usuarios, _Reloj(_PASADO_EL_PLAZO), _Zona(), torneo.generador()
        )

        await GetScheduleUseCase(torneo.uow, sobres=mesa).execute(
            GetScheduleRequestDTO(competition_id=torneo.comp_id.value)
        )

        assert set(salidas.avisados) == set(torneo.equipo_a + torneo.equipo_b)

    async def test_generation_undone_when_saving_fails_notifies_nobody(self, monkeypatch):
        """
        Generar termina bien pero el SAVEPOINT no se puede cerrar: lo generado se
        deshace y la apertura sigue con el motivo apuntado. No hay partidos que contar.
        """
        salidas = _Salidas()
        torneo = self._con_avisos(await _montar(), salidas)
        await torneo.entregan_los_dos()

        @asynccontextmanager
        async def _savepoint_que_no_cierra():
            yield
            # Lo que haria Postgres al deshacerlo: en memoria no se deshace solo
            ronda = await torneo.uow.rounds.find_by_id(torneo.ronda_id)
            ronda.reset_to_pending_matches()
            for partido in await torneo.uow.matches.find_by_round(torneo.ronda_id):
                await torneo.uow.matches.delete(partido.id)
            raise RuntimeError("el SAVEPOINT no se pudo liberar")

        monkeypatch.setattr(torneo.uow, "savepoint", _savepoint_que_no_cierra)

        await torneo.mirar(_Reloj(_PASADO_EL_PLAZO)).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        assert (await torneo.ronda()).match_generation_block.reason == "UNEXPECTED"
        assert salidas.llamadas == []

    async def test_a_failing_session_keeps_the_notices_of_the_one_before(self):
        """
        Revision del 22 oct: la agenda abre dos sesiones; la primera se genera
        y la segunda falla en su SAVEPOINT. Descartar lo de la segunda no puede
        llevarse los avisos de la primera.
        """
        ryder = await _Ryder(MatchFormat.SINGLES, 2).guardar()
        tarde = Round.create(
            competition_id=ryder.competicion.id,
            golf_course_id=ryder.ronda.golf_course_id,
            round_date=date(2026, 10, 25),
            session_type=SessionType.AFTERNOON,
            match_format=MatchFormat.SINGLES,
        )
        tarde.mark_teams_assigned()
        async with ryder.uow:
            await ryder.uow.rounds.add(tarde)
        salidas = _Salidas()
        generador = ryder.generador(salidas)
        mesa = EnvelopeDesk(ryder.uow, ryder.usuarios, generador=generador)
        await mesa.generar_los_partidos(ryder.ronda, ryder.competicion)
        original = ryder.uow.savepoint

        @asynccontextmanager
        async def _savepoint_que_no_cierra():
            async with original():
                yield
            # Lo que haria Postgres al deshacerlo: en memoria no se deshace solo
            sesion = await ryder.uow.rounds.find_by_id(tarde.id)
            sesion.reset_to_pending_matches()
            for partido in await ryder.uow.matches.find_by_round(tarde.id):
                await ryder.uow.matches.delete(partido.id)
            raise RuntimeError("el SAVEPOINT no se pudo liberar")

        ryder.uow.savepoint = _savepoint_que_no_cierra
        await mesa.generar_los_partidos(tarde, ryder.competicion)

        await mesa.avisar_salidas()

        assert [r for r, _, _ in salidas.llamadas] == [ryder.ronda.id]
        assert set(salidas.avisados) == set(ryder.equipo_a + ryder.equipo_b)

    async def test_a_failed_automatic_generation_notifies_nobody(self):
        salidas = _Salidas()
        torneo = self._con_avisos(await _montar(sexos=[None, None, None, None]), salidas)
        await torneo.entregan_los_dos()

        await torneo.mirar(_Reloj(_PASADO_EL_PLAZO)).execute(
            torneo.ronda_id.value, torneo.organizador
        )

        assert await torneo.partidos() == []
        assert salidas.llamadas == []

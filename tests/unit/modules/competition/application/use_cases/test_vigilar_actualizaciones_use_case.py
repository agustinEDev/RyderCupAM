"""
La vuelta del vigilante de las actualizaciones de hándicaps (#251, 7 oct 2026).

Solo hace dos cosas: lanzar las programadas que llegan a su hora y recuperar
las que un reinicio dejó en curso.

| Caso                                                  | Resultado                                     |
|-------------------------------------------------------|-----------------------------------------------|
| Programada a su hora, ventana abierta                 | Se lanza (programada) y deja de estar programada |
| La última quedó incompleta                            | Se reanuda                                    |
| Programada a su hora, ventana cerrada                 | No se lanza, se quita y se avisa con el motivo|
| Programada con una ya en marcha                       | Espera: se lanza al acabar la otra            |
| La anularon o cambiaron mientras tanto                | Se respeta: no se lanza                       |
| Reanudada hace poco                                   | No cuenta como cortada                        |
| Programada para más tarde                             | Nada                                          |
| En curso sin actividad desde hace 10 min              | Incompleta, y aviso con quién falta           |
| En curso sin actividad pero sin nadie pendiente       | Completa, sin aviso                           |
| En curso con actividad reciente                       | Intacta                                       |
"""

from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.use_cases.refrescar_handicaps_use_case import (
    Herramientas,
)
from src.modules.competition.application.use_cases.vigilar_actualizaciones_use_case import (
    SIN_ACTIVIDAD,
    VigilarActualizacionesUseCase,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from tests.unit.modules.competition.application.use_cases.test_actualizar_handicaps_use_case import (  # noqa: F401
    A_TIEMPO,
    CERCA,
    _Escenario,
    e,
)

pytestmark = pytest.mark.asyncio


class _Usuarios:
    async def find_by_id(self, user_id):
        usuario = MagicMock()
        usuario.email = MagicMock(value="org@test.com")
        usuario.get_full_name.return_value = "Org Anizador"
        return usuario

    async def find_by_ids(self, ids):
        return [
            MagicMock(id=i, display_name_or_legal=MagicMock(return_value=f"Jugador {i}"))
            for i in ids
        ]


def _vuelta(e, ahora):  # noqa: F811
    e.avisos = MagicMock()
    e.avisos.send_handicaps_pending_email = AsyncMock(return_value=True)
    e.avisos.send_scheduled_handicaps_update_skipped_email = AsyncMock(return_value=True)

    @asynccontextmanager
    async def herramientas():
        yield Herramientas(competiciones=e.uow, usuarios=_Usuarios(), zonas=e.zonas)

    return VigilarActualizacionesUseCase(
        herramientas=herramientas, lanzador=e.lanzador, avisos=e.avisos, reloj=lambda: ahora
    )


async def _programar(e, para):  # noqa: F811
    async with e.uow:
        await e.uow.handicap_updates.programar(e.competicion.id, para, A_TIEMPO)


class TestLasProgramadas:
    async def test_a_su_hora_con_la_ventana_abierta_se_lanza(self, e):  # noqa: F811
        await e.torneo()
        await _programar(e, A_TIEMPO)

        await _vuelta(e, A_TIEMPO).execute()

        ultima = await e.ultima()
        assert ultima.origen is OrigenActualizacion.PROGRAMADA
        assert e.lanzador.lanzadas == [ultima.id]
        assert await e.uow.handicap_updates.programada_de(e.competicion.id) is None

    async def test_si_la_ultima_quedo_incompleta_la_reanuda(self, e):  # noqa: F811
        await e.torneo()
        incompleta = ActualizacionDeHandicaps.crear(
            e.competicion.id, OrigenActualizacion.CIERRE, A_TIEMPO
        )
        incompleta.terminar(pendientes=1, momento=A_TIEMPO)
        async with e.uow:
            await e.uow.handicap_updates.add(incompleta)
        await _programar(e, A_TIEMPO)

        await _vuelta(e, A_TIEMPO).execute()

        assert e.lanzador.lanzadas == [incompleta.id]

    async def test_con_la_ventana_cerrada_no_se_lanza_y_se_avisa(self, e):  # noqa: F811
        await e.torneo()
        await _programar(e, CERCA)
        vuelta = _vuelta(e, CERCA)

        await vuelta.execute()

        assert e.lanzador.lanzadas == []
        assert await e.uow.handicap_updates.programada_de(e.competicion.id) is None
        aviso = e.avisos.send_scheduled_handicaps_update_skipped_email.await_args.kwargs
        assert aviso["to_email"] == "org@test.com"
        assert "salida" in aviso["reason"]

    async def test_en_una_cancelada_o_terminada_se_quita_sin_avisar(self, e):  # noqa: F811
        from src.modules.competition.domain.value_objects.competition_status import (
            CompetitionStatus,
        )

        for status in (CompetitionStatus.CANCELLED, CompetitionStatus.COMPLETED):
            await e.torneo(status=status)
            await _programar(e, A_TIEMPO)
            vuelta = _vuelta(e, A_TIEMPO)

            await vuelta.execute()

            assert await e.uow.handicap_updates.programada_de(e.competicion.id) is None
            e.avisos.send_scheduled_handicaps_update_skipped_email.assert_not_awaited()

    async def test_con_una_en_marcha_espera_a_que_acabe(self, e, caplog):  # noqa: F811
        """Se lanzará al acabar la otra (Agustín, 8 oct 2026), y sin error en la vuelta."""
        await e.torneo()
        await e.pulsar()
        await _programar(e, A_TIEMPO)

        await _vuelta(e, A_TIEMPO).execute()

        assert "no pudo atender" not in caplog.text
        assert len(e.lanzador.lanzadas) == 1
        assert await e.uow.handicap_updates.programada_de(e.competicion.id) == A_TIEMPO

    async def test_si_la_cambiaron_mientras_tanto_se_respeta(self, e):  # noqa: F811
        await e.torneo()
        await _programar(e, A_TIEMPO)
        # El vigilante la leyó vencida; antes de bloquear, el organizador la pasa a mañana
        manana = A_TIEMPO + timedelta(days=1)
        original = e.uow.handicap_updates.programadas_vencidas

        async def la_leyo_y_la_cambiaron(ahora):
            vencidas = await original(ahora)
            await e.uow.handicap_updates.programar(e.competicion.id, manana, ahora)
            return vencidas

        e.uow.handicap_updates.programadas_vencidas = la_leyo_y_la_cambiaron

        await _vuelta(e, A_TIEMPO).execute()

        assert e.lanzador.lanzadas == []
        assert await e.uow.handicap_updates.programada_de(e.competicion.id) == manana

    async def test_la_de_mas_tarde_espera(self, e):  # noqa: F811
        await e.torneo()
        await _programar(e, A_TIEMPO + timedelta(minutes=1))

        await _vuelta(e, A_TIEMPO).execute()

        assert e.lanzador.lanzadas == []
        assert await e.uow.handicap_updates.programada_de(e.competicion.id) is not None


class TestLasCortadas:
    async def _en_curso(self, e, actividad=None):  # noqa: F811
        actualizacion = ActualizacionDeHandicaps.crear(
            e.competicion.id, OrigenActualizacion.CIERRE, A_TIEMPO
        )
        async with e.uow:
            await e.uow.handicap_updates.add(actualizacion)
            if actividad is not None:
                (inscripcion, *_) = await e.uow.enrollments.find_by_competition(e.competicion.id)
                await e.uow.handicap_updates.apuntar(
                    actualizacion.id, inscripcion.user_id, ResultadoRefresco.ACTUALIZADO, actividad
                )
        return actualizacion

    async def test_sin_actividad_queda_incompleta_y_avisa(self, e):  # noqa: F811
        await e.torneo()
        cortada = await self._en_curso(e)

        await _vuelta(e, A_TIEMPO + SIN_ACTIVIDAD + timedelta(seconds=1)).execute()

        guardada = await e.uow.handicap_updates.find_by_id(cortada.id)
        assert guardada.estado is EstadoActualizacion.INCOMPLETA
        aviso = e.avisos.send_handicaps_pending_email.await_args.kwargs
        assert len(aviso["pending_names"]) == 6

    async def test_sin_pendientes_queda_completa_sin_aviso(self, e):  # noqa: F811
        await e.torneo()
        cortada = await self._en_curso(e)
        async with e.uow:
            for inscripcion in await e.uow.enrollments.find_by_competition(e.competicion.id):
                await e.uow.handicap_updates.apuntar(
                    cortada.id, inscripcion.user_id, ResultadoRefresco.ACTUALIZADO, A_TIEMPO
                )

        await _vuelta(e, A_TIEMPO + SIN_ACTIVIDAD + timedelta(seconds=1)).execute()

        guardada = await e.uow.handicap_updates.find_by_id(cortada.id)
        assert guardada.estado is EstadoActualizacion.COMPLETA
        e.avisos.send_handicaps_pending_email.assert_not_awaited()

    async def test_con_actividad_reciente_intacta(self, e):  # noqa: F811
        await e.torneo()
        viva = await self._en_curso(e, actividad=A_TIEMPO + SIN_ACTIVIDAD)

        await _vuelta(e, A_TIEMPO + SIN_ACTIVIDAD + timedelta(minutes=1)).execute()

        guardada = await e.uow.handicap_updates.find_by_id(viva.id)
        assert guardada.estado is EstadoActualizacion.EN_CURSO

    async def test_una_reanudada_hace_poco_no_cuenta_como_cortada(self, e):  # noqa: F811
        """Se reanudó tras horas incompleta: su actividad es la de ahora (code-review 3b-2)."""
        await e.torneo()
        vieja = await self._en_curso(e)
        vieja.terminar(pendientes=1, momento=A_TIEMPO)
        luego = A_TIEMPO + timedelta(hours=5)
        vieja.reanudar(luego)
        async with e.uow:
            await e.uow.handicap_updates.update(vieja)

        await _vuelta(e, luego + timedelta(minutes=1)).execute()

        guardada = await e.uow.handicap_updates.find_by_id(vieja.id)
        assert guardada.estado is EstadoActualizacion.EN_CURSO

    async def test_si_entre_tanto_termino_no_se_toca(self, e):  # noqa: F811
        await e.torneo()
        terminada = await self._en_curso(e)
        vista = await e.uow.handicap_updates.find_by_id(terminada.id)
        terminada.terminar(pendientes=0, momento=A_TIEMPO)
        async with e.uow:
            await e.uow.handicap_updates.update(terminada)

        # La consulta la vio en curso; al bloquear, ya ha terminado
        async def la_vio_en_curso(_limite):
            return [vista]

        e.uow.handicap_updates.en_curso_sin_actividad_desde = la_vio_en_curso
        vuelta = _vuelta(e, A_TIEMPO + SIN_ACTIVIDAD + timedelta(seconds=1))

        await vuelta.execute()

        guardada = await e.uow.handicap_updates.find_by_id(terminada.id)
        assert guardada.estado is EstadoActualizacion.COMPLETA
        e.avisos.send_handicaps_pending_email.assert_not_awaited()

    async def test_si_revivio_antes_del_candado_no_se_toca(self, e):  # noqa: F811
        """Vuelve a mirar la actividad con la competición bloqueada (CodeRabbit, #510)."""
        await e.torneo()
        viva = await self._en_curso(e)
        ahora = A_TIEMPO + SIN_ACTIVIDAD + timedelta(seconds=1)
        original = e.uow.handicap_updates.en_curso_sin_actividad_desde
        llamadas = []

        async def la_vio_parada_y_revivio(limite):
            llamadas.append(limite)
            parada = await original(limite)
            if len(llamadas) == 1:
                # Entre la consulta y el candado, la pasada apuntó a alguien
                (inscripcion, *_) = await e.uow.enrollments.find_by_competition(e.competicion.id)
                await e.uow.handicap_updates.apuntar(
                    viva.id, inscripcion.user_id, ResultadoRefresco.ACTUALIZADO, ahora
                )
            return parada

        e.uow.handicap_updates.en_curso_sin_actividad_desde = la_vio_parada_y_revivio

        await _vuelta(e, ahora).execute()

        guardada = await e.uow.handicap_updates.find_by_id(viva.id)
        assert guardada.estado is EstadoActualizacion.EN_CURSO

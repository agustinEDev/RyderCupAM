"""
Mover, reordenar, cambiar marcadores y borrar las partidas de una franja (#251, PR 4).

Del organizador (o un admin), con el plazo de generar: del cierre a la primera
salida, sin ninguna empezada (D11). Las reglas de cada cambio, en el dominio.

| Caso                                                   | Resultado                           |
|--------------------------------------------------------|-------------------------------------|
| Mover a una con hueco / intercambiar / a una nueva     | En la vista y guardado              |
| Mover a quien tiene plaza y no partida                 | Foto nueva; antes, en `unassigned`  |
| Mover a quien no tiene plaza en la franja              | PLAYER_NOT_IN_WINDOW                |
| Mover a una llena sin intercambio                      | GROUP_FULL, nada guardado           |
| Reordenar / con un orden que no vale                   | Renumeradas / INVALID_GROUP_ORDER   |
| Marcadores válidos / inválidos / partida que no existe | Guardados / error / no existe       |
| Borrar                                                 | Franja sin partidas                 |
| Fuera de plazo / quien no organiza                     | PlazoCerradoError / 403             |

Con la franja ya empezada (#544, 13 oct 2026): se tocan las que no han salido.

| Caso                                                   | Resultado                           |
|--------------------------------------------------------|-------------------------------------|
| Marcadores de una sin salir / de una que ya salió      | Guardados / PartidaYaSalidaError    |
| Mover de una sin salir a una nueva                     | Detrás de la última, sin renumerar  |
| Mover desde una que ya salió                           | PartidaYaSalidaError                |
| Reordenar las que no han salido / moviendo una fuera   | Renumeradas / PartidaYaSalidaError  |
| Colocar a quien no tiene partida                       | En la primera salida libre aún por  |
|                                                        |   llegar; sin ninguna, NO_FREE_...  |
| Generar o borrar                                       | PlazoCerradoError, como antes       |
| El campo sin zona horaria                              | ZonaDesconocidaError, como antes    |
| A una nueva con una salida libre aún por llegar        | Ocupa esa salida                    |
| Cambiar marcadores                                     | Solo bloquea su partida             |
| Reordenar                                              | Solo guarda las que cambian         |
"""

from datetime import timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    PartidaNotFoundError,
)
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.use_cases.partidas_use_case import (
    BorrarPartidasUseCase,
    CambiarMarcadoresUseCase,
    MoverJugadorUseCase,
    ReordenarPartidasUseCase,
)
from src.modules.competition.domain.services.marcadores_en_cadena import (
    MarcadoresInvalidosError,
)
from src.modules.competition.domain.services.movimientos_de_partidas import (
    MovimientoImposibleError,
)
from src.modules.competition.domain.services.plazo_de_partidas import (
    PartidaYaSalidaError,
    PlazoCerradoError,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    A_LA_PRIMERA_SALIDA,
    _Escenario,
)

pytestmark = pytest.mark.asyncio


async def _generadas(*handicaps: str) -> tuple[_Escenario, list[UserId]]:
    """Con los jugadores en ese orden de hándicap; generadas de más altos a más bajos."""
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(h) for h in handicaps]
    await escenario.generar()
    return escenario, jugadores


def _casos(escenario: _Escenario) -> dict:
    jugadores = JugadoresDeLaPartida(escenario.campos, escenario.usuarios)
    comun = {
        "uow": escenario.uow,
        "zonas": escenario.zonas,
        "user_repository": escenario.usuarios,
        "reloj": lambda: escenario.ahora,
    }
    return {
        "mover": MoverJugadorUseCase(jugadores=jugadores, **comun),
        "reordenar": ReordenarPartidasUseCase(**comun),
        "marcadores": CambiarMarcadoresUseCase(**comun),
        "borrar": BorrarPartidasUseCase(**comun),
    }


async def _mover(escenario, jugador, destino=None, intercambiar_con=None, quien=None):
    return await _casos(escenario)["mover"].execute(
        escenario.manana.id.value,
        jugador.value,
        destino,
        intercambiar_con.value if intercambiar_con else None,
        quien or escenario.creador,
        False,
    )


async def _guardadas(escenario):
    return await escenario.uow.partidas.de_la_franja(escenario.manana.id)


class TestMover:
    async def test_to_one_with_room(self):
        # 6 de 4: 4 + 2 -> la segunda tiene hueco
        escenario, _ = await _generadas("6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        primera, segunda = await _guardadas(escenario)
        quien = primera.user_ids[0]

        vista = await _mover(escenario, quien, segunda.id.value)

        assert [len(g.players) for g in vista.groups] == [3, 3]
        assert quien in (await _guardadas(escenario))[1].user_ids

    async def test_the_view_says_who_is_a_no_show(self):
        # El front cuenta solo a los que juegan (2.ª pasada del QA, 12 oct 2026)
        escenario, _ = await _generadas("6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        primera, segunda = await _guardadas(escenario)
        falta = primera.user_ids[0]
        primera.no_presentado(falta, [])
        await escenario.uow.partidas.guardar([primera])

        vista = await _mover(escenario, primera.user_ids[1], segunda.id.value)

        estados = {p.user_id: p.card_status for g in vista.groups for p in g.players}
        assert estados[falta.value] == "NO_PRESENTADO"
        assert set(estados.values()) == {"NO_PRESENTADO", "JUGANDO"}

    async def test_swapping(self):
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(8, 0, -1)])
        primera, segunda = await _guardadas(escenario)
        a, x = primera.user_ids[0], segunda.user_ids[0]

        await _mover(escenario, a, segunda.id.value, intercambiar_con=x)

        primera, segunda = await _guardadas(escenario)
        assert x in primera.user_ids and a in segunda.user_ids

    async def test_to_a_new_one_at_the_end(self):
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(5, 0, -1)])
        primera, _ = await _guardadas(escenario)

        vista = await _mover(escenario, primera.user_ids[0])

        assert [g.incomplete for g in vista.groups] == [False, False, True]
        assert vista.groups[-1].tee_time == "09:20"
        assert [len(p.user_ids) for p in await _guardadas(escenario)] == [2, 2, 1]

    async def test_emptying_a_group_removes_it_and_the_next_ones_move_up(self):
        """Quien se quedó solo vuelve a otra partida: la suya desaparece (M3)."""
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(6, 0, -1)])
        primera, _ = await _guardadas(escenario)
        solo = primera.user_ids[0]
        await _mover(escenario, solo)
        _, segunda, nueva = await _guardadas(escenario)

        vista = await _mover(escenario, solo, segunda.id.value)

        assert [p.id for p in await _guardadas(escenario)] == [primera.id, segunda.id]
        assert nueva.id.value not in {g.id for g in vista.groups}

    async def test_someone_with_a_place_and_no_group(self):
        escenario, _ = await _generadas("6.0", "5.0", "4.0")
        tarde = await escenario.con_plaza("9.0")
        antes = await _casos(escenario)["reordenar"].execute(
            escenario.manana.id.value,
            [p.id.value for p in await _guardadas(escenario)],
            escenario.creador,
            False,
        )
        (partida,) = await _guardadas(escenario)

        vista = await _mover(escenario, tarde, partida.id.value)

        assert [p.user_id for p in antes.unassigned_players] == [tarde.value]
        assert [p.user_id for p in vista.unassigned_players] == []
        nuevo = next(p for p in vista.groups[0].players if p.user_id == tarde.value)
        assert nuevo.handicap == 9

    async def test_someone_without_a_place_in_the_window(self):
        escenario, _ = await _generadas("6.0", "5.0")
        de_tarde = await escenario.con_plaza("9.0", franja=escenario.tarde)
        (partida,) = await _guardadas(escenario)

        with pytest.raises(MovimientoImposibleError) as error:
            await _mover(escenario, de_tarde, partida.id.value)
        assert error.value.codigo == "PLAYER_NOT_IN_WINDOW"

    async def test_to_a_full_one_saves_nothing(self):
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(8, 0, -1)])
        primera, segunda = await _guardadas(escenario)

        with pytest.raises(MovimientoImposibleError) as error:
            await _mover(escenario, primera.user_ids[0], segunda.id.value)
        assert error.value.codigo == "GROUP_FULL"
        assert [p.user_ids for p in await _guardadas(escenario)] == [
            primera.user_ids,
            segunda.user_ids,
        ]


class TestReordenar:
    async def test_reordering(self):
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(8, 0, -1)])
        primera, segunda = await _guardadas(escenario)

        vista = await _casos(escenario)["reordenar"].execute(
            escenario.manana.id.value,
            [segunda.id.value, primera.id.value],
            escenario.creador,
            False,
        )

        assert [g.id for g in vista.groups] == [segunda.id.value, primera.id.value]
        assert [p.id for p in await _guardadas(escenario)] == [segunda.id, primera.id]

    async def test_an_order_that_does_not_take_them_all(self):
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(8, 0, -1)])
        primera, _ = await _guardadas(escenario)

        with pytest.raises(MovimientoImposibleError) as error:
            await _casos(escenario)["reordenar"].execute(
                escenario.manana.id.value, [primera.id.value], escenario.creador, False
            )
        assert error.value.codigo == "INVALID_GROUP_ORDER"


class TestMarcadores:
    async def _cambiar(self, escenario, partida_id, marcadores, quien=None):
        pares = marcadores.items() if isinstance(marcadores, dict) else marcadores
        return await _casos(escenario)["marcadores"].execute(
            partida_id,
            [(a.value, b.value) for a, b in pares],
            quien or escenario.creador,
            False,
        )

    async def test_valid_markers_are_saved(self):
        escenario, _ = await _generadas("4.0", "3.0", "2.0", "1.0")
        (partida,) = await _guardadas(escenario)
        a, b, c, d = partida.user_ids

        vista = await self._cambiar(escenario, partida.id.value, {a: b, b: a, c: d, d: c})

        assert {p.user_id: p.marks_user_id for p in vista.groups[0].players} == {
            a.value: b.value,
            b.value: a.value,
            c.value: d.value,
            d.value: c.value,
        }
        assert (await _guardadas(escenario))[0].marcadores == {a: b, b: a, c: d, d: c}

    async def test_invalid_markers(self):
        escenario, _ = await _generadas("3.0", "2.0", "1.0")
        (partida,) = await _guardadas(escenario)
        a, b, c = partida.user_ids

        with pytest.raises(MarcadoresInvalidosError):
            await self._cambiar(escenario, partida.id.value, {a: a, b: c, c: b})

    async def test_the_same_player_twice_is_refused(self):
        """Contradictorio: A marca a C y a B. Antes se quedaba con el último (revisión)."""
        escenario, _ = await _generadas("3.0", "2.0", "1.0")
        (partida,) = await _guardadas(escenario)
        a, b, c = partida.user_ids

        with pytest.raises(MarcadoresInvalidosError):
            await self._cambiar(escenario, partida.id.value, [(a, c), (a, b), (b, c), (c, a)])

    async def test_a_group_gone_while_waiting_for_the_lock(self):
        """Otra petición la borró entre leerla y bloquear: 404, no un 500 (revisión)."""
        escenario, _ = await _generadas("2.0", "1.0")
        (partida,) = await _guardadas(escenario)
        original = escenario.uow.partidas.find_by_id

        async def y_se_borra(partida_id):
            encontrada = await original(partida_id)
            await escenario.uow.partidas.borrar([encontrada])
            return encontrada

        escenario.uow.partidas.find_by_id = y_se_borra

        with pytest.raises(PartidaNotFoundError):
            await self._cambiar(escenario, partida.id.value, {})

    async def test_a_group_that_does_not_exist(self):
        escenario, _ = await _generadas("2.0", "1.0")

        with pytest.raises(PartidaNotFoundError):
            await self._cambiar(escenario, uuid4(), {})


class TestBorrar:
    async def test_deleting_leaves_the_window_without_groups(self):
        escenario, _ = await _generadas("2.0", "1.0")

        await _casos(escenario)["borrar"].execute(
            escenario.manana.id.value, escenario.creador, False
        )

        assert await _guardadas(escenario) == []


class TestQuienYCuando:
    async def test_deleting_out_of_time(self):
        escenario, _ = await _generadas("2.0", "1.0")
        escenario.ahora = A_LA_PRIMERA_SALIDA
        with pytest.raises(PlazoCerradoError):
            await _llamar(escenario, "borrar", escenario.creador)

    @pytest.mark.parametrize("caso", ["mover", "marcadores"])
    async def test_touching_the_only_group_once_out(self, caso):
        # Antes era «fuera de plazo»; ahora, que esa partida ya salió (#544)
        escenario, _ = await _generadas("2.0", "1.0")
        escenario.ahora = A_LA_PRIMERA_SALIDA
        with pytest.raises(PartidaYaSalidaError):
            await _llamar(escenario, caso, escenario.creador)

    @pytest.mark.parametrize("caso", ["mover", "reordenar", "marcadores", "borrar"])
    async def test_only_the_organiser(self, caso):
        escenario, jugadores = await _generadas("2.0", "1.0")
        with pytest.raises(NotCompetitionCreatorError):
            await _llamar(escenario, caso, jugadores[0])

    async def test_a_closed_competition_that_started_still_can(self):
        escenario, _ = await _generadas("2.0", "1.0")
        escenario.competicion.start()  # IN_PROGRESS, antes de la primera salida
        assert escenario.competicion.status == CompetitionStatus.IN_PROGRESS

        await _llamar(escenario, "borrar", escenario.creador)


async def _llamar(escenario: _Escenario, caso: str, quien: UserId):
    (partida,) = await _guardadas(escenario)
    franja = escenario.manana.id.value
    if caso == "mover":
        return await _mover(escenario, partida.user_ids[0], quien=quien)
    if caso == "reordenar":
        return await _casos(escenario)["reordenar"].execute(
            franja, [partida.id.value], quien, False
        )
    if caso == "marcadores":
        return await _casos(escenario)["marcadores"].execute(
            partida.id.value,
            [(u.value, m.value) for u, m in partida.marcadores.items()],
            quien,
            False,
        )
    return await _casos(escenario)["borrar"].execute(franja, quien, False)


# 9:00 (7:00 UTC) la primera, 9:10 la segunda, 9:20 la tercera
CON_LA_PRIMERA_FUERA = A_LA_PRIMERA_SALIDA + timedelta(minutes=5)


class TestConLaFranjaEmpezada:
    async def test_markers_of_one_not_out(self):
        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        _, segunda = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA
        invertidos = [(b.value, a.value) for a, b in segunda.marcadores.items()]

        await _casos(escenario)["marcadores"].execute(
            segunda.id.value, invertidos, escenario.creador, False
        )

        (_, guardada) = await _guardadas(escenario)
        assert guardada.marcadores == {UserId(a): UserId(b) for a, b in invertidos}

    async def test_markers_of_one_already_out(self):
        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        primera, _ = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA

        with pytest.raises(PartidaYaSalidaError):
            await _casos(escenario)["marcadores"].execute(
                primera.id.value,
                [(u.value, m.value) for u, m in primera.marcadores.items()],
                escenario.creador,
                False,
            )

    async def test_moving_from_one_not_out_to_a_new_one(self):
        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        primera, segunda = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA

        await _mover(escenario, segunda.user_ids[0])

        guardadas = sorted(await _guardadas(escenario), key=lambda p: p.numero)
        assert [p.numero for p in guardadas] == [1, 2, 3]
        assert guardadas[0].user_ids == primera.user_ids

    async def test_moving_from_one_already_out(self):
        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        primera, segunda = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA

        with pytest.raises(PartidaYaSalidaError):
            await _mover(escenario, primera.user_ids[0], segunda.id.value)

    async def test_reordering_the_not_out(self):
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(10, 0, -1)])
        primera, segunda, tercera = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA

        await _casos(escenario)["reordenar"].execute(
            escenario.manana.id.value,
            [primera.id.value, tercera.id.value, segunda.id.value],
            escenario.creador,
            False,
        )

        numeros = {p.id: p.numero for p in await _guardadas(escenario)}
        assert (numeros[primera.id], numeros[tercera.id], numeros[segunda.id]) == (1, 2, 3)

    async def test_reordering_one_already_out(self):
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(10, 0, -1)])
        primera, segunda, tercera = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA

        with pytest.raises(PartidaYaSalidaError):
            await _casos(escenario)["reordenar"].execute(
                escenario.manana.id.value,
                [segunda.id.value, primera.id.value, tercera.id.value],
                escenario.creador,
                False,
            )

    async def test_placing_someone_goes_to_the_first_free_tee_time_still_ahead(self):
        # Las dos ya salieron (9:00 y 9:10) y las 9:20 ya pasaron: a las 9:30
        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        sin_partida = await escenario.con_plaza("0.5")
        escenario.ahora = A_LA_PRIMERA_SALIDA + timedelta(minutes=25)

        await _mover(escenario, sin_partida)

        nueva = next(p for p in await _guardadas(escenario) if sin_partida in p.user_ids)
        assert nueva.numero == 4

    async def test_placing_someone_with_no_tee_time_left(self):
        # La hoja acaba a las 10:00 (7 salidas): a las 10:05 no queda ninguna
        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        sin_partida = await escenario.con_plaza("0.5")
        escenario.ahora = A_LA_PRIMERA_SALIDA + timedelta(minutes=65)

        with pytest.raises(MovimientoImposibleError) as error:
            await _mover(escenario, sin_partida)

        assert error.value.codigo == "NO_FREE_TEE_TIME"

    async def test_generating_once_started_is_still_out_of_time(self):
        escenario, _ = await _generadas("2.0", "1.0")
        escenario.ahora = CON_LA_PRIMERA_FUERA

        with pytest.raises(PlazoCerradoError):
            await escenario.generar()

    async def test_scored_between_reading_and_moving(self, monkeypatch):
        # Revisor: anotar y mover ya pueden coincidir. Con las partidas bloqueadas
        # antes de decidir, la que empezó mientras se ve como salida
        from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
            cambiada_al_bloquear,
        )

        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        _, segunda = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA
        cambiada_al_bloquear(
            monkeypatch, lambda p: p.empezar() if p.id == segunda.id and not p.empezada else None
        )

        with pytest.raises(PartidaYaSalidaError):
            await _mover(escenario, segunda.user_ids[0])

    @pytest.mark.parametrize("caso", ["mover", "reordenar", "marcadores"])
    async def test_a_course_without_time_zone(self, caso):
        # /code-review: sin zona no se sabe qué salió; se rechaza, como antes
        from src.modules.competition.application.services.jornadas_de_la_competicion import (
            ZonaDesconocidaError,
        )

        escenario, _ = await _generadas("2.0", "1.0")
        escenario.zonas.zona = None
        escenario.ahora = CON_LA_PRIMERA_FUERA

        with pytest.raises(ZonaDesconocidaError):
            await _llamar(escenario, caso, escenario.creador)

    async def test_a_new_group_takes_a_free_tee_time_still_ahead(self):
        # /code-review: 1 fuera, la 3 vacía (sus 9:20 aún por llegar), la 4 ocupada
        escenario, _ = await _generadas(*[f"{h}.0" for h in range(12, 0, -1)])
        _, segunda, tercera = await _guardadas(escenario)
        guardada = await escenario.uow.partidas.find_by_id(tercera.id)
        guardada.renumerar(4)
        await escenario.uow.partidas.guardar([guardada])
        escenario.ahora = CON_LA_PRIMERA_FUERA

        await _mover(escenario, segunda.user_ids[0])

        numeros = sorted(p.numero for p in await _guardadas(escenario))
        assert numeros == [1, 2, 3, 4]

    async def test_changing_markers_locks_only_that_group(self, monkeypatch):
        from src.modules.competition.infrastructure.persistence.in_memory.in_memory_partida_repository import (
            InMemoryPartidaRepository,
        )

        escenario, _ = await _generadas("7.0", "6.0", "5.0", "4.0", "3.0", "2.0", "1.0")
        _, segunda = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA
        bloqueadas = []
        bloquear = InMemoryPartidaRepository.find_by_id_for_update

        async def espia(self, partida_id):
            bloqueadas.append(partida_id)
            return await bloquear(self, partida_id)

        monkeypatch.setattr(InMemoryPartidaRepository, "find_by_id_for_update", espia)

        await _casos(escenario)["marcadores"].execute(
            segunda.id.value,
            [(b.value, a.value) for a, b in segunda.marcadores.items()],
            escenario.creador,
            False,
        )

        assert bloqueadas == [segunda.id]

    async def test_reordering_saves_only_the_ones_that_change(self, monkeypatch):
        from src.modules.competition.infrastructure.persistence.in_memory.in_memory_partida_repository import (
            InMemoryPartidaRepository,
        )

        escenario, _ = await _generadas(*[f"{h}.0" for h in range(10, 0, -1)])
        primera, segunda, tercera = await _guardadas(escenario)
        escenario.ahora = CON_LA_PRIMERA_FUERA
        guardadas = []
        guardar = InMemoryPartidaRepository.guardar

        async def espia(self, partidas):
            guardadas.extend(p.id for p in partidas)
            return await guardar(self, partidas)

        monkeypatch.setattr(InMemoryPartidaRepository, "guardar", espia)

        await _casos(escenario)["reordenar"].execute(
            escenario.manana.id.value,
            [primera.id.value, tercera.id.value, segunda.id.value],
            escenario.creador,
            False,
        )

        assert set(guardadas) == {segunda.id, tercera.id}

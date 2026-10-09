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
"""

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
from src.modules.competition.domain.services.plazo_de_partidas import PlazoCerradoError
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
    @pytest.mark.parametrize("caso", ["mover", "reordenar", "marcadores", "borrar"])
    async def test_out_of_time(self, caso):
        escenario, _ = await _generadas("2.0", "1.0")
        escenario.ahora = A_LA_PRIMERA_SALIDA
        with pytest.raises(PlazoCerradoError):
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

"""
Si un marcador se retira o no se presenta (QA del 11 oct 2026, decidido con Agustín).

| Caso                                                     | Resultado                                     |
|----------------------------------------------------------|-----------------------------------------------|
| No presentado deja a uno solo sin salir; la 2 es de 4    | El último de la 2 pasa a acompañarle, traído  |
| La siguiente de 4 ya salió por su hora                   | De la siguiente de 4 que no haya salido       |
| La siguiente de 4 ya salió por su estado                 | Igual                                         |
| Ninguna de 4 detrás; una de 3                            | De la de 3                                    |
| Detrás solo partidas de 2                                | Nadie: se queda solo                          |
| Solo, pero su partida ya empezó                          | Nadie: valida el organizador                  |
| Solo en una de 4 con tres no presentados                 | Viene uno: el NP no ocupa sitio (QA 2)        |
| El traído se queda solo por otro no presentado           | Viene otro de la siguiente partida            |
| Las partidas de antes no cuentan, aunque no hayan salido | Nadie                                         |
| Detrás una de 3 y luego una de 4                         | De la de 4                                    |
| La de 4 empieza mientras se bloquea                      | De la siguiente                               |
| C se retira: B (que marcaba a C) ya no le anota          | NotYourMarkedPlayerError                      |
| El nuevo marcador anota un hoyo pendiente del que se fue | Validado                                      |
| Validar lo anotado, solo                                 | Valida los hoyos con su golpe; el ✗ no        |
| Validar lo anotado con marcador                          | TieneMarcadorError                            |
| Validar lo anotado si su marcador ya entregó             | Valida                                        |
| Validar lo anotado con la competición sin jugarse        | PartidaNoAnotableError                        |
| El último que juega de la de 4, no el último de la fila  | Se salta a un no presentado                   |
| Baja que deja a uno solo, ya pasada la 1.ª salida        | Le acompaña el último de la siguiente de 4    |
| Baja que deja a uno solo antes de la 1.ª salida          | Nadie: lo arregla el organizador (D4)         |
| El no presentado bloquea la competición antes            | Como la baja: no se cruzan                    |
| Validar lo anotado siendo jugador                        | NotCompetitionCreatorError                    |
| Validar lo anotado con la tarjeta cerrada                | TarjetaCerradaError                           |
| Validar lo anotado antes de la 1.ª salida                | ScoringNotOpenYetError                        |
"""

from datetime import UTC, datetime

import pytest

from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    NotYourMarkedPlayerError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.services.partidas_del_jugador import (
    sacar_de_sus_partidas,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    PartidaNoAnotableError,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    MarcarNoPresentadoUseCase,
    TieneMarcadorError,
    ValidarLoAnotadoUseCase,
)
from src.modules.competition.domain.entities.partida import Partida, TarjetaCerradaError
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    A_LAS_NUEVE_Y_CINCO,
    _anotar,
    _golpes,
    _partida,
    cambiada_al_bloquear,
)
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio

# Salidas cada 10 minutos desde las 9:00 en Madrid: la 2 sale a las 9:10
A_LAS_NUEVE_Y_CUARTO = datetime(2030, 10, 11, 7, 15, tzinfo=UTC)


async def _franja(*tamanos: int) -> tuple[_Escenario, list[Partida]]:
    """Partidas de esos tamaños, en orden, con jugadores de verdad de la franja."""
    escenario = _Escenario()
    await escenario.guardar()
    for h in range(sum(tamanos), 0, -1):
        await escenario.con_plaza(f"{h}.0")
    await escenario.generar()
    generadas = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    jugadores = [j for p in generadas for j in p.jugadores]
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
    escenario.ahora = A_LAS_NUEVE_Y_CINCO
    return escenario, partidas


async def _no_presentado(escenario, partida, jugador):
    await MarcarNoPresentadoUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    ).execute(partida.id.value, jugador.value, escenario.creador, False)


async def _leidas(escenario) -> list[Partida]:
    return await escenario.uow.partidas.de_la_franja(escenario.manana.id)


async def _empezar(escenario, partida):
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida.empezar()
    await escenario.uow.partidas.guardar([leida])


async def test_the_last_of_the_next_group_of_four_keeps_company():
    escenario, (sola, cuatro, _) = await _franja(2, 4, 4)
    falta, queda = sola.user_ids
    viene = cuatro.user_ids[-1]

    await _no_presentado(escenario, sola, falta)

    una, dos, _ = await _leidas(escenario)
    assert una.user_ids == [falta, queda, viene]
    assert una.traidos == {viene}
    assert una.marcadores == {queda: viene, viene: queda}
    assert dos.user_ids == cuatro.user_ids[:-1]
    assert len(dos.marcadores) == 3


async def test_a_group_of_four_already_out_by_its_time_is_skipped():
    escenario, (sola, _, tercera) = await _franja(2, 4, 4)
    escenario.ahora = A_LAS_NUEVE_Y_CUARTO

    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, _, tres = await _leidas(escenario)
    assert una.traidos == {tercera.user_ids[-1]}
    assert len(tres.user_ids) == 3


async def test_a_group_of_four_already_out_by_its_state_is_skipped():
    escenario, (sola, cuatro, tercera) = await _franja(2, 4, 4)
    await _empezar(escenario, cuatro)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, dos, _ = await _leidas(escenario)
    assert una.traidos == {tercera.user_ids[-1]}
    assert len(dos.user_ids) == 4


async def test_without_a_group_of_four_behind_one_of_three():
    escenario, (sola, tres, _) = await _franja(2, 3, 3)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, dos, _ = await _leidas(escenario)
    assert una.traidos == {tres.user_ids[-1]}
    assert len(dos.user_ids) == 2


async def test_with_only_groups_of_two_behind_nobody_comes():
    escenario, (sola, _) = await _franja(2, 2)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, dos = await _leidas(escenario)
    assert una.traidos == set()
    assert una.sin_marcador_en_juego == [sola.user_ids[1]]
    assert una.incompleta
    assert len(dos.user_ids) == 2


async def test_alone_in_a_group_already_started_nobody_comes():
    escenario, (sola, _) = await _franja(2, 4)
    await _empezar(escenario, sola)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, dos = await _leidas(escenario)
    assert una.traidos == set()
    assert len(dos.user_ids) == 4


async def test_alone_among_three_no_shows_someone_still_comes():
    # Los no presentados no ocupan sitio (2.ª pasada del QA, 12 oct 2026)
    escenario, (sola, cuatro) = await _franja(4, 4)
    for jugador in sola.user_ids[:3]:
        await _no_presentado(escenario, sola, jugador)

    una, dos = await _leidas(escenario)
    assert una.traidos == {cuatro.user_ids[-1]}
    assert len(una.user_ids) == 5
    assert len(dos.user_ids) == 3


async def test_who_was_brought_in_left_alone_by_another_no_show_gets_company():
    # De 3: con la segunda compañía la partida llega a 5 filas
    escenario, (sola, cuatro, otra) = await _franja(3, 4, 4)
    falta, otro, queda = sola.user_ids
    await _no_presentado(escenario, sola, falta)
    await _no_presentado(escenario, sola, otro)
    diana = cuatro.user_ids[-1]

    await _no_presentado(escenario, sola, queda)

    # La 2 ya es de 3: viene el último de la 3, que sigue siendo de 4
    una, dos, tres = await _leidas(escenario)
    viene = otra.user_ids[-1]
    assert una.user_ids == [falta, otro, queda, diana, viene]
    assert una.traidos == {diana, viene}
    assert una.marcadores == {diana: viene, viene: diana}
    assert dos.user_ids == cuatro.user_ids[:-1]
    assert tres.user_ids == otra.user_ids[:-1]


async def test_earlier_groups_do_not_count():
    escenario, (_, sola) = await _franja(4, 2)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    uno, dos = await _leidas(escenario)
    assert dos.traidos == set()
    assert len(uno.user_ids) == 4


async def test_earlier_groups_not_out_yet_do_not_count_either():
    # A las 9:05 la 2 (9:10) aún no ha salido, pero va antes que la 3
    escenario, (_, _, sola) = await _franja(4, 4, 2)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    _, dos, tres = await _leidas(escenario)
    assert tres.traidos == set()
    assert len(dos.user_ids) == 4


async def test_a_group_of_four_further_behind_comes_before_one_of_three():
    escenario, (sola, _, cuatro) = await _franja(2, 3, 4)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, dos, tres = await _leidas(escenario)
    assert una.traidos == {cuatro.user_ids[-1]}
    assert len(dos.user_ids) == 3
    assert len(tres.user_ids) == 3


async def test_a_group_that_starts_while_locking_is_skipped(monkeypatch):
    escenario, (sola, cuatro, tercera) = await _franja(2, 4, 4)
    cambiada_al_bloquear(monkeypatch, lambda p: p.empezar() if p.id == cuatro.id else None)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, _, _ = await _leidas(escenario)
    assert una.traidos == {tercera.user_ids[-1]}


async def test_who_marked_the_withdrawn_player_no_longer_scores_them():
    escenario, partida = await _partida(3)
    a, b, c = partida.user_ids
    assert partida.marcadores == {a: b, b: c, c: a}
    await _anotar(escenario, partida, c, own_score=4)
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida.retirar(c)
    await escenario.uow.partidas.guardar([leida])

    with pytest.raises(NotYourMarkedPlayerError):
        await _anotar(escenario, partida, b, marked_player_id=str(c.value), marked_score=4)


async def test_the_new_marker_validates_what_the_old_one_left_pending():
    escenario, partida = await _partida(3)
    a, b, c = partida.user_ids
    await _anotar(escenario, partida, a, own_score=5)
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida.retirar(c)
    await escenario.uow.partidas.guardar([leida])

    await _anotar(escenario, partida, b, marked_player_id=str(a.value), marked_score=5)

    assert (await _golpes(escenario, partida))[(a, 1)].validado


def _validar(escenario):
    return ValidarLoAnotadoUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


async def _solo_en_juego(escenario, partida):
    """A y B; A anota 3 hoyos, B le marca distinto el 3 y se retira."""
    a, b = partida.user_ids
    for hoyo in (1, 2, 3):
        await _anotar(escenario, partida, a, hoyo=hoyo, own_score=4)
    await _anotar(escenario, partida, b, hoyo=3, marked_player_id=str(a.value), marked_score=6)
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida.retirar(b)
    await escenario.uow.partidas.guardar([leida])
    return a


async def test_validating_what_the_lone_player_scored():
    escenario, partida = await _partida(2)
    a = await _solo_en_juego(escenario, partida)

    await _validar(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    golpes = await _golpes(escenario, partida)
    assert golpes[(a, 1)].validado and golpes[(a, 2)].validado
    assert golpes[(a, 1)].marcador_por == escenario.creador
    assert not golpes[(a, 3)].validado


async def test_validating_someone_who_has_a_marker():
    escenario, partida = await _partida(3)
    a = partida.user_ids[0]

    with pytest.raises(TieneMarcadorError):
        await _validar(escenario).execute(partida.id.value, a.value, escenario.creador, False)


async def test_validating_as_a_player():
    escenario, partida = await _partida(2)
    a = await _solo_en_juego(escenario, partida)

    with pytest.raises(NotCompetitionCreatorError):
        await _validar(escenario).execute(partida.id.value, a.value, a, False)


async def test_validating_a_closed_card():
    escenario, partida = await _partida(2)
    a, b = partida.user_ids

    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida.empezar()
    leida.retirar(b)
    leida.retirar(a)
    await escenario.uow.partidas.guardar([leida])
    assert leida.estados_de_tarjeta[a] == EstadoDeTarjeta.RETIRADO

    with pytest.raises(TarjetaCerradaError):
        await _validar(escenario).execute(partida.id.value, a.value, escenario.creador, False)


async def test_validating_before_the_first_tee_time():
    escenario, partida = await _partida(2)
    escenario.ahora = datetime(2030, 10, 11, 6, 59, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError):
        await _validar(escenario).execute(
            partida.id.value, partida.user_ids[0].value, escenario.creador, False
        )


async def test_validating_someone_whose_marker_handed_in():
    escenario, partida = await _partida(3)
    a, b, c = partida.user_ids
    await _anotar(escenario, partida, b, own_score=4)
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida.entregar(a)
    leida.retirar(c)
    await escenario.uow.partidas.guardar([leida])

    await _validar(escenario).execute(partida.id.value, b.value, escenario.creador, False)

    assert (await _golpes(escenario, partida))[(b, 1)].validado


async def test_validating_with_the_competition_not_in_play():
    from src.modules.competition.domain.value_objects.competition_status import (
        CompetitionStatus,
    )

    escenario, partida = await _partida(2)
    escenario.competicion._status = CompetitionStatus.COMPLETED
    async with escenario.uow:
        await escenario.uow.competitions.update(escenario.competicion)

    with pytest.raises(PartidaNoAnotableError):
        await _validar(escenario).execute(
            partida.id.value, partida.user_ids[0].value, escenario.creador, False
        )


async def test_the_last_one_playing_comes_skipping_a_no_show_at_the_end():
    escenario, (sola, cuatro, _) = await _franja(2, 4, 3)
    ultimo = cuatro.user_ids[-1]
    await _no_presentado(escenario, cuatro, ultimo)
    await _no_presentado(escenario, sola, sola.user_ids[0])

    una, dos, _ = await _leidas(escenario)
    # La 2 tiene 3 que juegan, como la 3: viene el último que juega de la 2
    assert una.traidos == {cuatro.user_ids[2]}
    assert ultimo in dos.user_ids


async def _baja(escenario, jugador):
    async with escenario.uow:
        await sacar_de_sus_partidas(
            escenario.uow,
            escenario.competicion.id,
            jugador,
            zonas=escenario.zonas,
            ahora=escenario.ahora,
        )


async def test_a_withdrawal_after_the_first_tee_time_also_brings_company():
    # A las 9:05 la 1 ya salió; la 2 (9:10) y la 3 (9:20), no
    escenario, (_, sola, cuatro) = await _franja(4, 2, 4)

    await _baja(escenario, sola.user_ids[0])

    _, dos, tres = await _leidas(escenario)
    assert dos.user_ids == [sola.user_ids[1], cuatro.user_ids[-1]]
    assert dos.traidos == {cuatro.user_ids[-1]}
    assert len(tres.user_ids) == 3


async def test_a_withdrawal_right_at_the_first_tee_time_brings_company():
    escenario, (_, sola, cuatro) = await _franja(4, 2, 4)
    escenario.ahora = datetime(2030, 10, 11, 7, 0, tzinfo=UTC)

    await _baja(escenario, sola.user_ids[0])

    _, dos, _ = await _leidas(escenario)
    assert dos.traidos == {cuatro.user_ids[-1]}


async def test_a_withdrawal_before_the_first_tee_time_is_for_the_organiser():
    escenario, (_, sola, _) = await _franja(4, 2, 4)
    escenario.ahora = datetime(2030, 10, 11, 6, 55, tzinfo=UTC)

    await _baja(escenario, sola.user_ids[0])

    _, dos, tres = await _leidas(escenario)
    assert dos.user_ids == [sola.user_ids[1]]
    assert len(tres.user_ids) == 4


async def test_the_no_show_locks_the_competition_first(monkeypatch):
    """La baja bloquea la competición: el no presentado también, y antes que las partidas."""
    escenario, (sola, _) = await _franja(2, 4)
    orden = []
    competiciones = type(escenario.uow.competitions)
    partidas = type(escenario.uow.partidas)
    bloquear_competicion = competiciones.find_by_id_for_update
    bloquear_partida = partidas.find_by_id_for_update

    async def competicion(self, *args):
        orden.append("competicion")
        return await bloquear_competicion(self, *args)

    async def partida(self, *args):
        orden.append("partida")
        return await bloquear_partida(self, *args)

    monkeypatch.setattr(competiciones, "find_by_id_for_update", competicion)
    monkeypatch.setattr(partidas, "find_by_id_for_update", partida)

    await _no_presentado(escenario, sola, sola.user_ids[0])

    assert orden[0] == "competicion"

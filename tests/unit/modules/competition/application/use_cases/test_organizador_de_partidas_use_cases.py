"""
Lo que hace el organizador con la anotación de las partidas (#251, PR 5; P3, P4, P6, P9, P11).

| Caso                                              | Resultado                              |
|---------------------------------------------------|----------------------------------------|
| Corregir siendo jugador                           | NotCompetitionCreatorError             |
| Corregir a quien movieron mientras tanto          | PartidaNotFoundError, no un 500        |
| Corregir los dos lados                            | Validado, metido por él                |
| Partida de 1: el jugador y él de marcador         | Validado (P11)                         |
| Antes de la 1.ª salida                            | ScoringNotOpenYetError                 |
| Una tarjeta entregada                             | TarjetaCerradaError: se reabre antes   |
| Raya en Medal                                     | RayaNoPermitidaError                   |
| En una partida sin empezar                        | La empieza                             |
| Reabrir una entregada                             | JUGANDO                                |
| No presentado                                     | NO_PRESENTADO                          |
| Cerrar la franja                                  | Completa ENTREGADA, a medias RETIRADO, |
|                                                   | sin hoyos NO_PRESENTADO                |
| Cerrar con hoyos anotados y ninguno validado      | RETIRADO, no NO_PRESENTADO: jugó       |
|   (suyos, solo del marcador, los 18, ✗, raya)     |                                        |
| Cerrar con un hoyo creado y nada enviado          | NO_PRESENTADO                          |
| Cerrar la franja siendo jugador                   | NotCompetitionCreatorError             |
| Cerrar la franja antes de su 1.ª salida           | ScoringNotOpenYetError: nada cambia    |
| Cerrar la franja con la competición sin jugarse   | PartidaNoAnotableError                 |
| Cerrar la franja                                  | Relee cada partida bloqueándola        |
| Reabrir / no presentado con el torneo acabado     | PartidaNoAnotableError                 |
| Reabrir / no presentado antes de la 1.ª salida    | ScoringNotOpenYetError                 |
| Corregir sin ningún lado                          | ValidationError: no toca nada          |
| Corregir con un lado nulo (raya)                  | Se acepta                              |
| Reabrir una tarjeta ya abierta (#545)             | TarjetaYaAbiertaError: nada cambia     |
| No presentado con golpes en su partida (#550):    | TieneGolpesError: nada cambia          |
|   suyos, solo del marcador, una raya              |                                        |
| No presentado con golpes solo en otra partida     | NO_PRESENTADO                          |
| No presentado con golpes solo de otro de la       | NO_PRESENTADO (cuentan sus filas, como |
|   partida, o una fila sin nada enviado            |   al cerrar la franja)                 |
| No presentado con la tarjeta ya cerrada y golpes  | TarjetaCerradaError, no TieneGolpes    |
| Sin golpes suyos pero anotó a quien marca         | Jugó: TieneGolpesError, y al cerrar la |
|   (12 oct 2026)                                   |   franja, RETIRADO                     |
| El organizador retira a un jugador (#550)         | RETIRADO, círculo rehecho              |
| Retirar en una partida sin empezar / ya cerrada   | PartidaNoEmpezadaError / Cerrada       |
| Retirar siendo jugador                            | NotCompetitionCreatorError             |
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.partidas_dto import CorrectHoleBodyDTO
from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    PartidaNotFoundError,
    ScoringNotOpenYetError,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    PartidaNoAnotableError,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    CerrarFranjaUseCase,
    CorregirHoyoDePartidaUseCase,
    MarcarNoPresentadoUseCase,
    ReabrirTarjetaUseCase,
    RetirarJugadorUseCase,
)
from src.modules.competition.domain.entities.golpe_de_partida import (
    GolpeDePartida,
    RayaNoPermitidaError,
)
from src.modules.competition.domain.entities.partida import (
    PartidaNoEmpezadaError,
    TarjetaCerradaError,
    TarjetaYaAbiertaError,
    TieneGolpesError,
)
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_anotar_hoyo_de_partida_use_case import (
    _partida,
    cambiada_al_bloquear,
)
from tests.unit.modules.competition.application.use_cases.test_entregar_tarjeta_de_partida_use_case import (
    _en_juego,
    _validar,
    con_estado,
)

pytestmark = pytest.mark.asyncio


def _corregir(escenario):
    return CorregirHoyoDePartidaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


def _reabrir(escenario):
    return ReabrirTarjetaUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


def _no_presentado(escenario):
    return MarcarNoPresentadoUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


def _retirar(escenario):
    return RetirarJugadorUseCase(
        uow=escenario.uow, zonas=escenario.zonas, reloj=lambda: escenario.ahora
    )


async def _corrige(escenario, partida, jugador, hoyo=1, quien=None, **body):
    await _corregir(escenario).execute(
        partida.id.value,
        jugador.value,
        hoyo,
        CorrectHoleBodyDTO(**body),
        quien or escenario.creador,
        False,
    )


async def _golpe(escenario, partida, jugador, hoyo=1):
    golpes = await escenario.uow.golpes_de_partida.de_la_partida(partida.id)
    return next(g for g in golpes if g.user_id == jugador and g.hoyo == hoyo)


async def _tarjetas(escenario, partida):
    return (await escenario.uow.partidas.find_by_id(partida.id)).estados_de_tarjeta


async def test_correcting_someone_moved_meanwhile(monkeypatch):
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    cambiada_al_bloquear(monkeypatch, lambda p: p.quitar(a))

    with pytest.raises(PartidaNotFoundError):
        await _corrige(escenario, partida, a, own_score=4)


async def test_a_player_cannot_correct():
    escenario, partida = await _partida()
    a, b, _ = partida.user_ids

    with pytest.raises(NotCompetitionCreatorError):
        await _corrige(escenario, partida, b, quien=a, own_score=4)


async def test_both_sides_validate_and_say_who():
    escenario, partida = await _partida()
    a = partida.user_ids[0]

    await _corrige(escenario, partida, a, own_score=5, marker_score=5)

    golpe = await _golpe(escenario, partida, a)
    assert golpe.validado and golpe.golpes_validados == 5
    assert golpe.propio_por == golpe.marcador_por == escenario.creador


async def test_a_group_of_one_validated_by_the_organiser():
    escenario, partida = await _partida(n=2)
    a, b = partida.user_ids
    sola = await escenario.uow.partidas.find_by_id(partida.id)
    sola.quitar(b)
    await escenario.uow.partidas.guardar([sola])
    await _corrige(escenario, sola, a, own_score=4)

    await _corrige(escenario, sola, a, marker_score=4)

    assert (await _golpe(escenario, sola, a)).validado


async def test_before_the_first_tee_time():
    escenario, partida = await _partida()
    escenario.ahora = datetime(2030, 10, 11, 6, 0, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError):
        await _corrige(escenario, partida, partida.user_ids[0], own_score=4)


async def test_a_delivered_card_has_to_be_reopened_first():
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]
    entregada = await escenario.uow.partidas.find_by_id(partida.id)
    entregada.entregar(a)
    await escenario.uow.partidas.guardar([entregada])

    with pytest.raises(TarjetaCerradaError):
        await _corrige(escenario, partida, a, own_score=4)
    await _reabrir(escenario).execute(partida.id.value, a.value, escenario.creador, False)
    await _corrige(escenario, partida, a, own_score=4)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.JUGANDO
    assert (await _golpe(escenario, partida, a)).propio == 4


async def test_no_pick_up_in_medal():
    escenario, partida = await _partida(tipo=TournamentType.MEDAL)

    with pytest.raises(RayaNoPermitidaError):
        await _corrige(escenario, partida, partida.user_ids[0], own_score=None)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.SCHEDULED


async def test_it_starts_a_group_not_started():
    escenario, partida = await _partida()

    await _corrige(escenario, partida, partida.user_ids[0], own_score=4)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.IN_PROGRESS


async def test_no_show():
    escenario, partida = await _partida()
    a = partida.user_ids[0]

    await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.NO_PRESENTADO


async def test_reopening_a_no_show_in_a_full_three_ball_window():
    # En una franja de 3, con 3 jugando, el NP no vuelve (/code-review, 12 oct 2026)
    from datetime import time

    from src.modules.competition.domain.entities.partida import PartidaLlenaError
    from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
    from tests.unit.modules.competition.domain.entities.test_partida import _jugador

    escenario, partida = await _partida()
    escenario.manana._hoja_de_salidas = HojaDeSalidas(time(9, 0), time(10, 0), 10, 3)
    a = partida.user_ids[0]
    await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)
    leida = await escenario.uow.partidas.find_by_id(partida.id)
    leida.meter(_jugador(), 3)
    await escenario.uow.partidas.guardar([leida])

    with pytest.raises(PartidaLlenaError):
        await _reabrir(escenario).execute(partida.id.value, a.value, escenario.creador, False)


async def test_closing_the_window():
    escenario, partida = await _en_juego(n=4)
    completa, a_medias, sin_hoyos, entregada = partida.user_ids
    # El lado del marcador lo mete el organizador: así `sin_hoyos` no anotó a nadie
    organizador = escenario.creador
    await _validar(escenario, partida, completa, marcador=organizador)
    await _validar(escenario, partida, a_medias, hoyos=range(1, 10), marcador=organizador)
    await _validar(escenario, partida, entregada, marcador=organizador)
    antes = await escenario.uow.partidas.find_by_id(partida.id)
    antes.entregar(entregada)
    await escenario.uow.partidas.guardar([antes])

    await CerrarFranjaUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    ).execute(escenario.manana.id.value, escenario.creador, False)

    assert await _tarjetas(escenario, partida) == {
        completa: EstadoDeTarjeta.ENTREGADA,
        a_medias: EstadoDeTarjeta.RETIRADO,
        sin_hoyos: EstadoDeTarjeta.NO_PRESENTADO,
        entregada: EstadoDeTarjeta.ENTREGADA,
    }
    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.COMPLETED


async def _anotar(
    escenario, partida, user_id, hoyos, propio=None, del_marcador=None, partida_id=None
):
    """Cada lado se envía solo si se pasa; RAYA es levantar bola."""
    # `marcadores` va de marcador a marcado
    marcador = next(m for m, marcado in partida.marcadores.items() if marcado == user_id)
    for hoyo in hoyos:
        golpe = GolpeDePartida.crear(
            partida_id or partida.id,
            partida.round_id,
            partida.competition_id,
            user_id,
            hoyo,
            escenario.ahora,
        )
        if propio is not None:
            golpe.anotar_propio(_golpes(propio), True, user_id, escenario.ahora)
        if del_marcador is not None:
            golpe.anotar_del_marcador(_golpes(del_marcador), True, marcador, escenario.ahora)
        await escenario.uow.golpes_de_partida.guardar(golpe)


RAYA = "raya"


def _golpes(valor):
    return None if valor == RAYA else valor


@pytest.mark.parametrize(
    ("hoyos", "propio", "del_marcador"),
    [
        pytest.param(range(1, 11), 4, None, id="solo-los-suyos"),
        pytest.param(range(1, 2), None, 5, id="solo-los-del-marcador"),
        pytest.param(range(1, 19), 4, None, id="los-18-sin-validar"),
        pytest.param(range(1, 4), 4, 5, id="solo-desacuerdos"),
        pytest.param(range(1, 2), RAYA, None, id="una-raya"),
    ],
)
async def test_closing_with_entered_holes_and_none_validated(hoyos, propio, del_marcador):
    # Su marcadora no vino y nadie le validó nada: jugó, así que no es NP
    escenario, partida = await _en_juego(n=3)
    jugo = partida.user_ids[0]
    await _anotar(escenario, partida, jugo, hoyos, propio, del_marcador)

    await _cerrar(escenario)

    assert (await _tarjetas(escenario, partida))[jugo] == EstadoDeTarjeta.RETIRADO


async def test_closing_counts_only_the_strokes_of_its_own_group():
    # Golpes suyos de otra partida de la franja no le hacen retirado en esta
    escenario, partida = await _en_juego(n=3)
    nadie = partida.user_ids[0]
    await _anotar(escenario, partida, nadie, range(1, 4), 4, partida_id=PartidaId.generate())

    await _cerrar(escenario)

    assert (await _tarjetas(escenario, partida))[nadie] == EstadoDeTarjeta.NO_PRESENTADO


async def test_closing_with_a_hole_created_and_nothing_sent():
    escenario, partida = await _en_juego(n=3)
    nadie = partida.user_ids[0]
    await _anotar(escenario, partida, nadie, range(1, 2))

    await _cerrar(escenario)

    assert (await _tarjetas(escenario, partida))[nadie] == EstadoDeTarjeta.NO_PRESENTADO


def _cerrar(escenario, quien=None):
    return CerrarFranjaUseCase(
        uow=escenario.uow,
        zonas=escenario.zonas,
        user_repository=escenario.usuarios,
        reloj=lambda: escenario.ahora,
    ).execute(escenario.manana.id.value, quien or escenario.creador, False)


async def test_closing_before_the_first_tee_time():
    # Dejaba a todos no presentados y la franja sin poder rehacerse
    escenario, partida = await _partida()
    escenario.ahora = datetime(2030, 10, 11, 6, 59, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError):
        await _cerrar(escenario)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.SCHEDULED


async def test_closing_with_the_competition_not_in_play():
    escenario, _ = await _partida()
    competicion = await escenario.uow.competitions.find_by_id(escenario.competicion.id)
    competicion._status = CompetitionStatus.ACTIVE
    await escenario.uow.competitions.update(competicion)

    with pytest.raises(PartidaNoAnotableError):
        await _cerrar(escenario)


async def test_closing_locks_each_group_before_deciding():
    # Sin bloquear, un 18 anotado a la vez quedaba como retirado
    escenario, partida = await _en_juego()
    bloqueadas = []
    original = escenario.uow.partidas.find_by_id_for_update

    async def espia(partida_id):
        bloqueadas.append(partida_id)
        return await original(partida_id)

    escenario.uow.partidas.find_by_id_for_update = espia

    await _cerrar(escenario)

    assert bloqueadas == [partida.id]


async def test_a_player_cannot_close_the_window():
    escenario, partida = await _en_juego()

    with pytest.raises(NotCompetitionCreatorError):
        await CerrarFranjaUseCase(
            uow=escenario.uow,
            zonas=escenario.zonas,
            user_repository=escenario.usuarios,
            reloj=lambda: escenario.ahora,
        ).execute(escenario.manana.id.value, partida.user_ids[0], False)


def test_a_correction_without_any_side():
    # Vacía arrancaría la partida y dejaría un golpe sin nada que impide
    # borrar la franja
    with pytest.raises(ValidationError):
        CorrectHoleBodyDTO()


@pytest.mark.parametrize("cuerpo", [{"own_score": None}, {"marker_score": 4}])
def test_a_correction_with_one_side(cuerpo):
    assert CorrectHoleBodyDTO(**cuerpo).model_fields_set == set(cuerpo)


@pytest.mark.parametrize("caso", [_reabrir, _no_presentado, _retirar])
async def test_not_once_the_competition_is_over_either(caso):
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]
    await con_estado(escenario, CompetitionStatus.COMPLETED)

    with pytest.raises(PartidaNoAnotableError):
        await caso(escenario).execute(partida.id.value, a.value, escenario.creador, False)


@pytest.mark.parametrize("caso", [_reabrir, _no_presentado, _retirar])
async def test_not_before_the_first_tee_time_either(caso):
    # Un no presentado puesto antes de salir ignoraba luego sus golpes en silencio
    escenario, partida = await _partida()
    a = partida.user_ids[0]
    escenario.ahora = datetime(2030, 10, 11, 6, 59, tzinfo=UTC)

    with pytest.raises(ScoringNotOpenYetError):
        await caso(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.JUGANDO


async def test_reopening_a_card_already_open():
    # Dos organizadores a la vez: el segundo ve que se le adelantaron (#545)
    escenario, partida = await _en_juego()
    a = partida.user_ids[0]

    with pytest.raises(TarjetaYaAbiertaError):
        await _reabrir(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.JUGANDO


@pytest.mark.parametrize(
    ("propio", "del_marcador"),
    [
        pytest.param(4, None, id="suyos"),
        pytest.param(None, 5, id="solo-del-marcador"),
        pytest.param(RAYA, None, id="una-raya"),
    ],
)
async def test_no_show_with_strokes_entered(propio, del_marcador):
    # Jugó: se retira, no es no presentado (#550)
    escenario, partida = await _en_juego(n=3)
    a = partida.user_ids[0]
    await _anotar(escenario, partida, a, range(1, 2), propio, del_marcador)

    with pytest.raises(TieneGolpesError):
        await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.JUGANDO


async def test_no_show_with_strokes_only_in_another_group():
    escenario, partida = await _en_juego(n=3)
    a = partida.user_ids[0]
    await _anotar(escenario, partida, a, range(1, 3), 4, partida_id=PartidaId.generate())

    await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.NO_PRESENTADO


async def test_the_organiser_retires_a_player():
    escenario, partida = await _en_juego(n=3)
    a, b, c = partida.user_ids
    await _anotar(escenario, partida, a, range(1, 4), 4)

    await _retirar(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    leida = await escenario.uow.partidas.find_by_id(partida.id)
    assert leida.estados_de_tarjeta[a] == EstadoDeTarjeta.RETIRADO
    # Como cuando se retira él: los que quedan se marcan entre ellos
    assert set(leida.marcadores) == {b, c}
    assert set(leida.marcadores.values()) == {b, c}


async def test_retiring_in_a_group_not_started():
    escenario, partida = await _partida()
    a = partida.user_ids[0]

    with pytest.raises(PartidaNoEmpezadaError):
        await _retirar(escenario).execute(partida.id.value, a.value, escenario.creador, False)


async def test_retiring_a_closed_card():
    escenario, partida = await _en_juego(n=3)
    a = partida.user_ids[0]
    entregada = await escenario.uow.partidas.find_by_id(partida.id)
    entregada.entregar(a)
    await escenario.uow.partidas.guardar([entregada])

    with pytest.raises(TarjetaCerradaError):
        await _retirar(escenario).execute(partida.id.value, a.value, escenario.creador, False)


async def test_a_player_cannot_retire_another():
    escenario, partida = await _en_juego(n=3)
    a, b, _ = partida.user_ids

    with pytest.raises(NotCompetitionCreatorError):
        await _retirar(escenario).execute(partida.id.value, a.value, b, False)


async def test_no_show_when_only_another_player_scored():
    escenario, partida = await _en_juego(n=3)
    a, b, _ = partida.user_ids
    await _anotar(escenario, partida, b, range(1, 3), 4)

    await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.NO_PRESENTADO


async def test_no_show_with_a_hole_created_and_nothing_sent():
    escenario, partida = await _en_juego(n=3)
    a = partida.user_ids[0]
    await _anotar(escenario, partida, a, range(1, 2))

    await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.NO_PRESENTADO


async def test_no_show_on_a_closed_card_with_strokes():
    # Antes decía «tiene golpes, retíralo» y retirarlo también fallaba (revisor)
    escenario, partida = await _en_juego(n=3)
    a = partida.user_ids[0]
    await _anotar(escenario, partida, a, range(1, 4), 4)
    retirada = await escenario.uow.partidas.find_by_id(partida.id)
    retirada.retirar(a)
    await escenario.uow.partidas.guardar([retirada])

    with pytest.raises(TarjetaCerradaError):
        await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)


async def _anoto_a_su_marcado(escenario, partida, marcador):
    """Solo el lado del marcador en la tarjeta de quien marca: él no se anotó nada."""
    marcado = partida.marcadores[marcador]
    golpe = GolpeDePartida.crear(
        partida.id, partida.round_id, partida.competition_id, marcado, 1, escenario.ahora
    )
    golpe.anotar_del_marcador(4, True, marcador, escenario.ahora)
    await escenario.uow.golpes_de_partida.guardar(golpe)


async def test_no_show_for_someone_who_only_scored_whom_they_mark():
    # Estuvo en el campo: se retira, no es no presentado (12 oct 2026)
    escenario, partida = await _en_juego(n=3)
    a = partida.user_ids[0]
    await _anoto_a_su_marcado(escenario, partida, a)

    with pytest.raises(TieneGolpesError):
        await _no_presentado(escenario).execute(partida.id.value, a.value, escenario.creador, False)


async def test_closing_with_someone_who_only_scored_whom_they_mark():
    escenario, partida = await _en_juego(n=3)
    a = partida.user_ids[0]
    await _anoto_a_su_marcado(escenario, partida, a)

    await _cerrar(escenario)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.RETIRADO


async def test_retiring_someone_not_in_the_group():
    escenario, partida = await _en_juego(n=3)

    with pytest.raises(PartidaNotFoundError):
        await _retirar(escenario).execute(
            partida.id.value, UserId.generate().value, escenario.creador, False
        )


async def test_an_admin_can_retire():
    escenario, partida = await _en_juego(n=3)
    a, b, _ = partida.user_ids

    await _retirar(escenario).execute(partida.id.value, a.value, b, True)

    assert (await _tarjetas(escenario, partida))[a] == EstadoDeTarjeta.RETIRADO


async def test_retiring_the_last_one_playing_finishes_the_group():
    escenario, partida = await _en_juego(n=2)
    a, b = partida.user_ids
    entregada = await escenario.uow.partidas.find_by_id(partida.id)
    entregada.entregar(b)
    await escenario.uow.partidas.guardar([entregada])

    await _retirar(escenario).execute(partida.id.value, a.value, escenario.creador, False)

    assert (await escenario.uow.partidas.find_by_id(partida.id)).estado == EstadoPartida.COMPLETED


async def _organiza_y_juega(escenario, partida):
    """El organizador es uno de la partida y corrige la tarjeta de otro al que no marca."""
    organizador = partida.user_ids[0]
    competicion = await escenario.uow.competitions.find_by_id(escenario.competicion.id)
    competicion._creator_id = organizador
    await escenario.uow.competitions.update(competicion)
    no_marca = next(
        u for u in partida.user_ids if u not in (organizador, partida.marcadores[organizador])
    )
    golpe = GolpeDePartida.crear(
        partida.id, partida.round_id, partida.competition_id, no_marca, 1, escenario.ahora
    )
    golpe.anotar_del_marcador(4, True, organizador, escenario.ahora)
    await escenario.uow.golpes_de_partida.guardar(golpe)
    return organizador


async def test_a_playing_organiser_who_only_corrected_can_be_a_no_show():
    # CodeRabbit (13 oct): corregir desde la casa club no es haber jugado
    escenario, partida = await _en_juego(n=3)
    organizador = await _organiza_y_juega(escenario, partida)

    await _no_presentado(escenario).execute(partida.id.value, organizador.value, organizador, False)

    assert (await _tarjetas(escenario, partida))[organizador] == EstadoDeTarjeta.NO_PRESENTADO


async def test_closing_with_a_playing_organiser_who_only_corrected():
    escenario, partida = await _en_juego(n=3)
    organizador = await _organiza_y_juega(escenario, partida)

    await _cerrar(escenario, quien=organizador)

    assert (await _tarjetas(escenario, partida))[organizador] == EstadoDeTarjeta.NO_PRESENTADO

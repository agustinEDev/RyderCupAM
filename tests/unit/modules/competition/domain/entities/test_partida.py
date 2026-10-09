"""
La partida de stroke play: un grupo que sale junto a su hora (#251, PR 4).

Decidido con Agustín el 6-9 oct 2026: de 3 o 4 al generar; de 1 solo por bajas
(D4), incompleta y sin marcador; marcadores en cadena que el organizador puede
cambiar sin que nadie se marque a sí mismo (D12). Empezada, ya no se toca.

| Caso                                              | Resultado                       |
|---------------------------------------------------|---------------------------------|
| Jugador: 18 hoyos que suman su hándicap de juego  | Vale (también plus y scratch)   |
| Jugador: 17 hoyos, o no suman                     | Error                           |
| Crear de 2 a 4                                    | SCHEDULED, marcadores en cadena |
| Número 0, vacía, de 5, jugador repetido           | Error                           |
| De 1                                              | Incompleta, sin marcador        |
| Quitar / meter                                    | Rehace la cadena                |
| Meter en una llena, o a uno que ya está           | Error                           |
| Quitar a uno que no está                          | Error                           |
| Cambiar marcadores                                | Validados                       |
| Renumerar a 0                                     | Error                           |
| Recalcular con otros jugadores                    | Error                           |
| Cualquier cambio con la partida empezada          | PartidaEmpezadaError            |
| may_mark                                          | Solo a quien le toca            |
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.partida import (
    Partida,
    PartidaEmpezadaError,
    PartidaInvalidaError,
)
from src.modules.competition.domain.services.marcadores_en_cadena import (
    MarcadoresInvalidosError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


def _golpes(playing_handicap: int) -> tuple[int, ...]:
    """Reparto plano que suma el hándicap de juego: lo justo para el invariante."""
    base, resto = divmod(abs(playing_handicap), 18)
    signo = 1 if playing_handicap >= 0 else -1
    return tuple(signo * (base + (1 if hoyo < resto else 0)) for hoyo in range(18))


def _jugador(playing_handicap: int = 10, user_id: UserId | None = None) -> JugadorDePartida:
    return JugadorDePartida(
        user_id=user_id or UserId.generate(),
        handicap=Decimal("11.4"),
        playing_handicap=playing_handicap,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        golpes_por_hoyo=_golpes(playing_handicap),
    )


def _partida(n: int = 4, numero: int = 1) -> Partida:
    return Partida.crear(
        competition_id=CompetitionId(uuid4()),
        round_id=RoundId.generate(),
        numero=numero,
        jugadores=[_jugador() for _ in range(n)],
    )


def _empezada() -> Partida:
    partida = _partida()
    return Partida(
        id=partida.id,
        competition_id=partida.competition_id,
        round_id=partida.round_id,
        numero=partida.numero,
        jugadores=partida.jugadores,
        marcadores=partida.marcadores,
        estado=EstadoPartida.IN_PROGRESS,
    )


class TestJugadorDePartida:
    @pytest.mark.parametrize("playing_handicap", [20, -2, 0, 36, 18])
    def test_eighteen_holes_adding_up_to_the_playing_handicap(self, playing_handicap):
        jugador = _jugador(playing_handicap)

        assert sum(jugador.golpes_por_hoyo) == playing_handicap

    def test_seventeen_holes_is_refused(self):
        with pytest.raises(ValueError):
            JugadorDePartida(
                user_id=UserId.generate(),
                handicap=Decimal("5.0"),
                playing_handicap=0,
                tee_color=TeeColor.YELLOW,
                tee_gender=None,
                golpes_por_hoyo=(0,) * 17,
            )

    def test_strokes_that_do_not_add_up_are_refused(self):
        with pytest.raises(ValueError):
            JugadorDePartida(
                user_id=UserId.generate(),
                handicap=Decimal("5.0"),
                playing_handicap=5,
                tee_color=TeeColor.YELLOW,
                tee_gender=None,
                golpes_por_hoyo=_golpes(4),
            )


class TestCrear:
    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_a_new_one_is_scheduled_with_markers_in_a_chain(self, n):
        partida = _partida(n)
        ids = partida.user_ids

        assert partida.estado == EstadoPartida.SCHEDULED
        assert not partida.empezada
        assert not partida.incompleta
        assert partida.marcadores == {ids[i]: ids[(i + 1) % n] for i in range(n)}

    def test_one_of_one_is_incomplete_and_has_no_marker(self):
        partida = _partida(1)

        assert partida.incompleta
        assert partida.marcadores == {}

    @pytest.mark.parametrize(
        ("numero", "n"),
        [
            pytest.param(0, 4, id="número 0"),
            pytest.param(1, 0, id="vacía"),
            pytest.param(1, 5, id="de 5"),
        ],
    )
    def test_impossible_ones_are_refused(self, numero, n):
        with pytest.raises(PartidaInvalidaError):
            _partida(n, numero=numero)

    def test_the_same_player_twice_is_refused(self):
        repetido = UserId.generate()
        with pytest.raises(PartidaInvalidaError):
            Partida.crear(
                competition_id=CompetitionId(uuid4()),
                round_id=RoundId.generate(),
                numero=1,
                jugadores=[_jugador(user_id=repetido), _jugador(user_id=repetido)],
            )


class TestCambios:
    def test_taking_one_out_redoes_the_chain(self):
        partida = _partida(4)
        a, b, c, d = partida.user_ids

        partida.quitar(b)

        assert partida.user_ids == [a, c, d]
        assert partida.marcadores == {a: c, c: d, d: a}

    def test_taking_out_down_to_one_leaves_it_incomplete_and_without_marker(self):
        partida = _partida(2)

        partida.quitar(partida.user_ids[0])

        assert partida.incompleta
        assert partida.marcadores == {}

    def test_taking_out_somebody_who_is_not_there_is_refused(self):
        with pytest.raises(PartidaInvalidaError):
            _partida().quitar(UserId.generate())

    def test_putting_one_in_goes_last_and_redoes_the_chain(self):
        partida = _partida(2)
        a, b = partida.user_ids
        nuevo = _jugador()

        partida.meter(nuevo, jugadores_por_partida=4)

        assert partida.user_ids == [a, b, nuevo.user_id]
        assert partida.marcadores == {a: b, b: nuevo.user_id, nuevo.user_id: a}

    @pytest.mark.parametrize(("n", "tamano"), [(4, 4), (3, 3)])
    def test_putting_one_in_a_full_one_is_refused(self, n, tamano):
        with pytest.raises(PartidaInvalidaError):
            _partida(n).meter(_jugador(), jugadores_por_partida=tamano)

    def test_putting_in_somebody_who_is_already_there_is_refused(self):
        partida = _partida(2)
        with pytest.raises(PartidaInvalidaError):
            partida.meter(partida.jugadores[0], jugadores_por_partida=4)

    def test_changing_markers_keeps_a_valid_assignment(self):
        partida = _partida(4)
        a, b, c, d = partida.user_ids

        partida.cambiar_marcadores({a: b, b: a, c: d, d: c})

        assert partida.marcadores == {a: b, b: a, c: d, d: c}

    def test_changing_markers_to_an_invalid_one_is_refused(self):
        partida = _partida(3)
        a, b, c = partida.user_ids
        with pytest.raises(MarcadoresInvalidosError):
            partida.cambiar_marcadores({a: a, b: c, c: b})

    def test_renumbering(self):
        partida = _partida()

        partida.renumerar(7)

        assert partida.numero == 7

    def test_renumbering_to_zero_is_refused(self):
        with pytest.raises(PartidaInvalidaError):
            _partida().renumerar(0)

    def test_recalculating_replaces_the_data_of_the_same_players(self):
        partida = _partida(2)
        marcadores = partida.marcadores
        nuevos = [_jugador(25, user_id=uid) for uid in partida.user_ids]

        partida.recalcular(nuevos)

        assert [j.playing_handicap for j in partida.jugadores] == [25, 25]
        assert partida.marcadores == marcadores

    def test_recalculating_with_other_players_is_refused(self):
        partida = _partida(2)
        with pytest.raises(PartidaInvalidaError):
            partida.recalcular([_jugador(), _jugador()])


class TestEmpezada:
    @pytest.mark.parametrize(
        "cambio",
        [
            pytest.param(lambda p: p.quitar(p.user_ids[0]), id="quitar"),
            pytest.param(lambda p: p.meter(_jugador(), jugadores_por_partida=5), id="meter"),
            pytest.param(lambda p: p.cambiar_marcadores(p.marcadores), id="marcadores"),
            pytest.param(lambda p: p.renumerar(2), id="renumerar"),
            pytest.param(lambda p: p.recalcular(list(p.jugadores)), id="recalcular"),
        ],
    )
    def test_a_started_one_is_not_touched(self, cambio):
        partida = _empezada()

        assert partida.empezada
        with pytest.raises(PartidaEmpezadaError):
            cambio(partida)


class TestMayMark:
    def test_only_whom_the_chain_says(self):
        partida = _partida(3)
        a, b, c = partida.user_ids

        assert partida.may_mark(a, b)
        assert not partida.may_mark(a, c)
        assert not partida.may_mark(a, a)
        assert not partida.may_mark(UserId.generate(), b)

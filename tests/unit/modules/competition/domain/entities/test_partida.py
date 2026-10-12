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
    PartidaLlenaError,
    PartidaNoEmpezadaError,
    TarjetaCerradaError,
    TarjetaYaAbiertaError,
)
from src.modules.competition.domain.services.marcadores_en_cadena import (
    MarcadoresEnCadena,
    MarcadoresInvalidosError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.estado_de_tarjeta import EstadoDeTarjeta
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.jugador_de_partida import (
    JugadorDePartida,
)
from src.modules.competition.domain.value_objects.partida_id import PartidaId
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
        par_por_hoyo=(4,) * 18,
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
                par_por_hoyo=(4,) * 18,
            )

    @pytest.mark.parametrize(
        "pares",
        [pytest.param((4,) * 17, id="17 hoyos"), pytest.param((2,) + (4,) * 17, id="par 2")],
    )
    def test_the_par_of_each_hole_is_eighteen_from_three_to_six(self, pares):
        """El par de SU barra, hoyo a hoyo (PR 5, P12): sin él no hay puntos ni «par»."""
        with pytest.raises(ValueError):
            JugadorDePartida(
                user_id=UserId.generate(),
                handicap=Decimal("5.0"),
                playing_handicap=0,
                tee_color=TeeColor.YELLOW,
                tee_gender=None,
                golpes_por_hoyo=(0,) * 18,
                par_por_hoyo=pares,
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
                par_por_hoyo=(4,) * 18,
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


class TestCicloDeLaTarjeta:
    """
    La partida en juego y la tarjeta de cada uno (PR 5; P2, P3, P6, P9).

    | Caso                                  | Resultado                              |
    |---------------------------------------|----------------------------------------|
    | Nueva                                 | Todas JUGANDO                          |
    | Empezar, dos veces                    | IN_PROGRESS; la segunda no hace nada   |
    | Entregar sin empezar / dos veces      | Error                                  |
    | Entregar una / todas                  | Sigue IN_PROGRESS / COMPLETED          |
    | Retirarse con los demás entregados    | RETIRADO y COMPLETED                   |
    | No presentado, sin empezar            | NO_PRESENTADO                          |
    | Reabrir una entregada                 | JUGANDO, y la partida en juego         |
    | Cerrar (organizador)                  | Completas ENTREGADA, sin hoyos NO_PRES.,|
    |                                       | el resto RETIRADO                      |
    | Un jugador que no está                | Error                                  |
    """

    def _empezada(self, n=2) -> Partida:
        partida = _partida(n)
        partida.empezar()
        return partida

    def test_new_every_card_playing(self):
        partida = _partida(3)

        assert set(partida.estados_de_tarjeta.values()) == {EstadoDeTarjeta.JUGANDO}

    def test_starting_twice(self):
        partida = self._empezada()
        partida.empezar()

        assert partida.estado == EstadoPartida.IN_PROGRESS

    def test_starting_a_finished_group_does_not_reopen_it(self):
        """Un golpe que llega tarde (la cola sin conexión) no la devuelve a juego."""
        partida = self._empezada()
        for user_id in partida.user_ids:
            partida.entregar(user_id)

        partida.empezar()

        assert partida.estado == EstadoPartida.COMPLETED

    def test_delivering_before_starting(self):
        partida = _partida(2)
        with pytest.raises(PartidaNoEmpezadaError):
            partida.entregar(partida.user_ids[0])

    def test_delivering_twice(self):
        partida = self._empezada()
        partida.entregar(partida.user_ids[0])
        with pytest.raises(TarjetaCerradaError):
            partida.entregar(partida.user_ids[0])

    def test_one_and_then_all_delivered(self):
        partida = self._empezada()
        a, b = partida.user_ids

        partida.entregar(a)
        assert partida.estado == EstadoPartida.IN_PROGRESS
        partida.entregar(b)

        assert partida.estado == EstadoPartida.COMPLETED
        assert partida.estados_de_tarjeta == {
            a: EstadoDeTarjeta.ENTREGADA,
            b: EstadoDeTarjeta.ENTREGADA,
        }

    def test_retiring_with_the_rest_delivered_completes_it(self):
        partida = self._empezada()
        a, b = partida.user_ids
        partida.entregar(a)

        partida.retirar(b)

        assert partida.estados_de_tarjeta[b] == EstadoDeTarjeta.RETIRADO
        assert partida.estado == EstadoPartida.COMPLETED

    def test_no_show_even_without_starting(self):
        partida = _partida(2)

        partida.no_presentado(partida.user_ids[0])

        assert partida.estados_de_tarjeta[partida.user_ids[0]] == EstadoDeTarjeta.NO_PRESENTADO

    def test_reopening_a_delivered_card(self):
        partida = self._empezada()
        a, b = partida.user_ids
        partida.entregar(a)
        partida.entregar(b)

        partida.reabrir_tarjeta(a)

        assert partida.estados_de_tarjeta[a] == EstadoDeTarjeta.JUGANDO
        assert partida.estado == EstadoPartida.IN_PROGRESS

    def test_reopening_a_card_already_open(self):
        # Dos organizadores a la vez: el segundo se entera (#545)
        partida = self._empezada()
        a = partida.user_ids[0]

        with pytest.raises(TarjetaYaAbiertaError):
            partida.reabrir_tarjeta(a)

        assert partida.estados_de_tarjeta[a] == EstadoDeTarjeta.JUGANDO

    def test_closing_by_the_organiser(self):
        """Completa, entregada; a medias, retirado; sin ningún hoyo, no presentado."""
        partida = self._empezada(4)
        a, b, c, d = partida.user_ids
        partida.entregar(d)

        partida.cerrar(completas={a}, sin_golpes={c})

        assert partida.estados_de_tarjeta == {
            a: EstadoDeTarjeta.ENTREGADA,
            b: EstadoDeTarjeta.RETIRADO,
            c: EstadoDeTarjeta.NO_PRESENTADO,
            d: EstadoDeTarjeta.ENTREGADA,
        }
        assert partida.estado == EstadoPartida.COMPLETED

    @pytest.mark.parametrize("accion", ["entregar", "retirar", "no_presentado", "reabrir_tarjeta"])
    def test_someone_not_in_the_group(self, accion):
        partida = self._empezada()
        with pytest.raises(PartidaInvalidaError):
            getattr(partida, accion)(UserId.generate())


class TestElMarcadorQueSeVa:
    """
    Si un marcador se retira o no se presenta, su jugador no se queda sin
    validar (QA del 11 oct 2026, decidido con Agustín).

    | Caso                                          | Resultado                                  |
    |-----------------------------------------------|--------------------------------------------|
    | A·B·C·D en juego; C se retira                 | Círculo por orden de salida: A→B, B→D, D→A |
    | De 3; uno no presentado                       | Los otros dos se marcan entre ellos        |
    | A entregó; C se retira                        | A sigue en el círculo                      |
    | De 2; uno se retira                           | Sin marcadores: el otro, solo              |
    | Sin empezar, de 2; un no presentado           | Sin marcadores                             |
    | Cerrar                                        | Círculo entre los entregados               |
    | Reabrir a un retirado                         | Los marcadores no cambian                  |
    | Leer con un retirado en el círculo            | Error                                      |
    | Leer con un reabierto fuera del círculo       | Vale                                       |
    | Acompañar al que se quedó solo, sin empezar   | Entra, círculo nuevo, marcado como traído  |
    | Acompañar sin estar solo o empezada           | Error                                      |
    | Acompañar en una de 4 con tres no presentados | Entra: el NP no ocupa sitio (QA 2, 12 oct) |
    | Leer 5 filas con un NP, o 4 que juegan + 2 NP | Vale                                       |
    | Leer 5 filas sin ningún NP                    | Error                                      |
    | Meter en una de 4 con un NP / con 4 que juegan| Entra / llena                              |
    | Reabrir un NP con 4 ya jugando                | PartidaLlenaError (12 oct)                 |
    | Reabrir un NP con hueco, sin salir            | Entra en el círculo                        |
    """

    def _empezada(self, n=4) -> Partida:
        partida = _partida(n)
        partida.empezar()
        return partida

    def test_a_marker_who_withdraws_is_replaced_in_tee_order(self):
        partida = self._empezada(4)
        a, b, c, d = partida.user_ids

        partida.retirar(c)

        assert partida.marcadores == {a: b, b: d, d: a}

    def test_a_no_show_in_a_three_leaves_the_other_two_marking_each_other(self):
        partida = self._empezada(3)
        a, b, c = partida.user_ids

        partida.no_presentado(a)

        assert partida.marcadores == {b: c, c: b}

    def test_who_handed_in_their_card_keeps_marking(self):
        partida = self._empezada(3)
        a, b, c = partida.user_ids
        partida.entregar(a)

        partida.retirar(c)

        assert partida.marcadores == {a: b, b: a}

    def test_alone_after_a_withdrawal_nobody_marks(self):
        partida = self._empezada(2)
        a, b = partida.user_ids

        partida.retirar(b)

        assert partida.marcadores == {}
        assert not partida.may_mark(b, a)

    def test_a_no_show_before_starting_leaves_the_other_alone(self):
        partida = _partida(2)
        a, _ = partida.user_ids

        partida.no_presentado(a)

        assert partida.marcadores == {}
        assert partida.sin_marcador_en_juego == [partida.user_ids[1]]

    def test_closing_keeps_the_circle_among_those_who_handed_in(self):
        partida = self._empezada(4)
        a, _, c, d = partida.user_ids

        partida.cerrar(completas={a, c}, sin_golpes={d})

        assert partida.marcadores == {a: c, c: a}

    def test_reopening_a_withdrawn_card_does_not_touch_the_markers(self):
        partida = self._empezada(3)
        a, b, c = partida.user_ids
        partida.retirar(c)

        partida.reabrir_tarjeta(c)

        assert partida.marcadores == {a: b, b: a}
        assert partida.estados_de_tarjeta[c] == EstadoDeTarjeta.JUGANDO

    def _leida(self, partida, marcadores, tarjetas) -> Partida:
        return Partida(
            id=partida.id,
            competition_id=partida.competition_id,
            round_id=partida.round_id,
            numero=partida.numero,
            jugadores=partida.jugadores,
            marcadores=marcadores,
            estado=EstadoPartida.IN_PROGRESS,
            estados_de_tarjeta=tarjetas,
        )

    def test_reading_a_withdrawn_player_in_the_circle_fails(self):
        partida = _partida(3)
        a, b, c = partida.user_ids

        with pytest.raises(MarcadoresInvalidosError):
            self._leida(partida, {a: b, b: c, c: a}, {c: EstadoDeTarjeta.RETIRADO})

    def test_reading_a_reopened_player_outside_the_circle_is_fine(self):
        partida = _partida(3)
        a, b, _ = partida.user_ids

        leida = self._leida(partida, {a: b, b: a}, {})

        assert leida.marcadores == {a: b, b: a}

    def test_reading_a_circle_with_a_single_member_fails(self):
        partida = _partida(3)
        a, _, _ = partida.user_ids

        with pytest.raises(MarcadoresInvalidosError):
            self._leida(partida, {a: a}, {})

    def test_reading_a_marker_outside_the_group_fails(self):
        partida = _partida(3)
        a, b, _ = partida.user_ids

        with pytest.raises(MarcadoresInvalidosError):
            self._leida(partida, {a: b, b: UserId.generate()}, {})

    def _sola(self, n=3) -> Partida:
        """Sin empezar, con todos menos el último no presentados."""
        partida = _partida(n)
        for user_id in partida.user_ids[:-1]:
            partida.no_presentado(user_id)
        return partida

    def test_keeping_company_to_who_was_left_alone(self):
        partida = self._sola(2)
        _, solo = partida.user_ids
        nuevo = _jugador()

        partida.acompanar(nuevo)

        assert partida.user_ids[-1] == nuevo.user_id
        assert partida.marcadores == {solo: nuevo.user_id, nuevo.user_id: solo}
        assert partida.traidos == {nuevo.user_id}
        assert partida.estados_de_tarjeta[nuevo.user_id] == EstadoDeTarjeta.JUGANDO
        assert not partida.sin_marcador_en_juego

    def test_marked_by_someone_who_handed_in_the_organiser_may_validate(self):
        partida = self._empezada(3)
        a, b, c = partida.user_ids
        partida.entregar(a)
        partida.retirar(c)

        assert partida.marcadores == {a: b, b: a}
        assert partida.sin_marcador_en_juego == [b]

    def test_quedan_in_tee_order(self):
        partida = self._empezada(4)
        a, b, c, d = partida.user_ids
        partida.retirar(b)
        partida.entregar(d)

        assert partida.quedan == [a, c, d]

    def test_alone_among_no_shows_is_incomplete(self):
        partida = self._sola(3)

        assert partida.incompleta

    def test_who_was_brought_in_and_leaves_again_is_no_longer_brought_in(self):
        partida = self._sola(2)
        nuevo = _jugador()
        partida.acompanar(nuevo)

        partida.quitar(nuevo.user_id)

        assert partida.traidos == set()

    def test_keeping_company_in_a_group_of_four_with_three_no_shows(self):
        # Los no presentados no ocupan sitio (2.ª pasada del QA, 12 oct 2026)
        partida = self._sola(4)
        solo = partida.user_ids[-1]
        nuevo = _jugador()

        partida.acompanar(nuevo)

        assert len(partida.user_ids) == 5
        assert partida.marcadores == {solo: nuevo.user_id, nuevo.user_id: solo}

    def test_reading_five_rows_with_a_no_show(self):
        jugadores = [_jugador() for _ in range(5)]

        leida = self._con_filas(jugadores, {jugadores[0].user_id: EstadoDeTarjeta.NO_PRESENTADO})

        assert len(leida.quedan) == 4

    def test_reading_four_playing_and_two_no_shows(self):
        jugadores = [_jugador() for _ in range(6)]
        faltan = {j.user_id: EstadoDeTarjeta.NO_PRESENTADO for j in jugadores[:2]}

        leida = self._con_filas(jugadores, faltan)

        assert len(leida.quedan) == 4

    def test_reading_five_rows_without_a_no_show_fails(self):
        jugadores = [_jugador() for _ in range(5)]

        with pytest.raises(PartidaInvalidaError):
            self._con_filas(jugadores, {jugadores[0].user_id: EstadoDeTarjeta.RETIRADO})

    def test_putting_one_in_a_group_of_four_with_a_no_show(self):
        partida = _partida(4)
        partida.no_presentado(partida.user_ids[0])
        nuevo = _jugador()

        partida.meter(nuevo, 4)

        assert partida.quedan[-1] == nuevo.user_id

    def test_putting_one_in_a_group_of_four_playing_is_full(self):
        partida = _partida(4)

        with pytest.raises(PartidaLlenaError):
            partida.meter(_jugador(), 4)

    def test_reopening_a_no_show_with_four_already_playing_is_refused(self):
        partida = _partida(4)
        falta = partida.user_ids[0]
        partida.no_presentado(falta)
        partida.meter(_jugador(), 4)

        with pytest.raises(PartidaLlenaError):
            partida.reabrir_tarjeta(falta)

        assert partida.estados_de_tarjeta[falta] == EstadoDeTarjeta.NO_PRESENTADO

    def test_reopening_a_no_show_counts_the_withdrawn_too(self):
        # 3 juegan + 1 retirado: reabrir al NP dejaría 5 tarjetas que no son NP (/code-review)
        partida = _partida(4)
        falta = partida.user_ids[0]
        partida.no_presentado(falta)
        partida.meter(_jugador(), 4)
        partida.empezar()
        partida.retirar(partida.user_ids[1])

        with pytest.raises(PartidaLlenaError):
            partida.reabrir_tarjeta(falta)

    def test_reopening_a_no_show_in_a_group_of_three_with_three_playing(self):
        partida = _partida(3)
        falta = partida.user_ids[0]
        partida.no_presentado(falta)
        partida.meter(_jugador(), 3)

        with pytest.raises(PartidaLlenaError):
            partida.reabrir_tarjeta(falta, jugadores_por_partida=3)

    def test_reopening_a_no_show_with_room_gets_a_marker(self):
        partida = _partida(3)
        a, b, c = partida.user_ids
        partida.no_presentado(a)

        partida.reabrir_tarjeta(a)

        assert partida.marcadores == {a: b, b: c, c: a}

    def test_reopening_a_handed_in_card_with_four_playing_is_fine(self):
        partida = self._empezada(4)
        a = partida.user_ids[0]
        partida.entregar(a)

        partida.reabrir_tarjeta(a)

        assert partida.estados_de_tarjeta[a] == EstadoDeTarjeta.JUGANDO

    def test_reopening_a_no_show_once_started_does_not_touch_the_markers(self):
        partida = self._empezada(3)
        a, b, c = partida.user_ids
        partida.no_presentado(a)

        partida.reabrir_tarjeta(a)

        assert partida.marcadores == {b: c, c: b}

    def test_reopening_a_withdrawn_card_with_four_rows_is_fine(self):
        partida = self._empezada(4)
        d = partida.user_ids[3]
        partida.retirar(d)

        partida.reabrir_tarjeta(d)

        assert partida.estados_de_tarjeta[d] == EstadoDeTarjeta.JUGANDO

    def _con_filas(self, jugadores, tarjetas) -> Partida:
        quedan = [j.user_id for j in jugadores if j.user_id not in tarjetas]
        return Partida(
            id=PartidaId.generate(),
            competition_id=CompetitionId(uuid4()),
            round_id=RoundId.generate(),
            numero=1,
            jugadores=jugadores,
            marcadores=MarcadoresEnCadena.de(quedan),
            estado=EstadoPartida.SCHEDULED,
            estados_de_tarjeta=tarjetas,
        )

    def test_keeping_company_to_a_group_that_is_not_alone(self):
        partida = _partida(2)

        with pytest.raises(PartidaInvalidaError):
            partida.acompanar(_jugador())

    def test_keeping_company_once_started(self):
        partida = self._sola(2)
        partida.empezar()

        with pytest.raises(PartidaEmpezadaError):
            partida.acompanar(_jugador())

    def test_who_was_brought_in_is_read_back(self):
        partida = self._sola(2)
        nuevo = _jugador()
        partida.acompanar(nuevo)

        leida = Partida(
            id=partida.id,
            competition_id=partida.competition_id,
            round_id=partida.round_id,
            numero=partida.numero,
            jugadores=partida.jugadores,
            marcadores=partida.marcadores,
            estado=partida.estado,
            estados_de_tarjeta=partida.estados_de_tarjeta,
            traidos={nuevo.user_id},
        )

        assert leida.traidos == {nuevo.user_id}

    def test_without_marker_only_a_player_still_playing_whom_nobody_marks(self):
        partida = self._empezada(3)
        a, b, c = partida.user_ids
        assert not partida.sin_marcador_en_juego
        partida.retirar(a)
        assert not partida.sin_marcador_en_juego
        partida.retirar(b)
        assert partida.sin_marcador_en_juego == [c]
        partida.entregar(c)
        assert not partida.sin_marcador_en_juego

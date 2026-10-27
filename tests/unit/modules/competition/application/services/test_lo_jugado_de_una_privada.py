"""
Lo jugado de una privada: clasificaciones y partidas (tabla del 27 oct 2026).

  #   quien mira una privada                         | ve
  ----|---------------------------------------------|-----------------------------
  1   organizador o admin                             | todo
  2,3 aprobado (también capitán o vice)               | todo
  5   retirado o rechazado                            | nada
  6   de fuera, sin evento                            | nada
  7   de fuera, con evento de un amigo de ese torneo   | la clasificación y la partida
                                                      | de ese amigo; las demás, no
  -   cualquiera en una pública                        | todo, como siempre
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    Acceso,
    LoJugadoQueVe,
    NoPuedeVerloError,
    PuertaDeLoJugado,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId

YO = UserId(uuid4())
CREADOR = UserId(uuid4())
AMIGO = UserId(uuid4())
OTRO = UserId(uuid4())


class _Eventos:
    def __init__(self, amigos=()):
        self.amigos = frozenset(amigos)
        self.preguntas = 0

    async def amigos_con_evento_en(self, user_id, competition_id):
        self.preguntas += 1
        return self.amigos


class _Uow:
    """Lo justo para la puerta: competición, inscripción, ronda, partido y partida."""

    def __init__(self, visibilidad=Visibility.PRIVATE, estado=None):
        self.comp = SimpleNamespace(
            id=CompetitionId(uuid4()),
            visibility=visibilidad,
            is_creator=lambda quien: quien == CREADOR,
        )
        self.ronda = SimpleNamespace(id=uuid4(), competition_id=self.comp.id)
        inscripcion = None if estado is None else SimpleNamespace(status=estado)
        self.competitions = SimpleNamespace(find_by_id=AsyncMock(return_value=self.comp))
        self.enrollments = SimpleNamespace(
            find_by_user_and_competition=AsyncMock(return_value=inscripcion)
        )
        self.rounds = SimpleNamespace(find_by_id=AsyncMock(return_value=self.ronda))
        self.matches = SimpleNamespace(find_by_id=AsyncMock(return_value=None))
        self.partidas = SimpleNamespace(find_by_id=AsyncMock(return_value=None))
        self.dentro = 0

    async def __aenter__(self):
        self.dentro += 1
        return self

    async def __aexit__(self, *exc):
        self.dentro -= 1

    def con_partido(self, *jugadores):
        jugador = lambda u: SimpleNamespace(user_id=u)  # noqa: E731
        self.matches.find_by_id.return_value = SimpleNamespace(
            round_id=self.ronda.id,
            team_a_players=tuple(jugador(u) for u in jugadores[:1]),
            team_b_players=tuple(jugador(u) for u in jugadores[1:]),
        )

    def con_partida(self, *jugadores):
        self.partidas.find_by_id.return_value = SimpleNamespace(
            competition_id=self.comp.id, user_ids=list(jugadores)
        )


async def _ve(uow, quien=YO, eventos=None, es_admin=False) -> LoJugadoQueVe:
    puerta = PuertaDeLoJugado(uow, eventos or _Eventos())
    return await puerta.de_la_competicion(uow.comp.id, quien, es_admin=es_admin)


class TestQuienEstaDentro:
    async def test_1_el_organizador_lo_ve_todo(self):
        assert (await _ve(_Uow(), CREADOR)).acceso is Acceso.ENTERO

    async def test_1_un_admin_lo_ve_todo(self):
        assert (await _ve(_Uow(), es_admin=True)).acceso is Acceso.ENTERO

    async def test_2_el_aprobado_lo_ve_todo(self):
        assert (await _ve(_Uow(estado=EnrollmentStatus.APPROVED))).acceso is Acceso.ENTERO

    async def test_dentro_no_se_pregunta_por_los_eventos(self):
        eventos = _Eventos({AMIGO})

        await _ve(_Uow(estado=EnrollmentStatus.APPROVED), eventos=eventos)

        assert eventos.preguntas == 0

    async def test_en_una_publica_cualquiera_lo_ve_todo(self):
        uow = _Uow(Visibility.PUBLIC)

        assert (await _ve(uow)).acceso is Acceso.ENTERO
        uow.enrollments.find_by_user_and_competition.assert_not_called()


class TestQuienEstaFuera:
    @pytest.mark.parametrize(
        "estado",
        [
            EnrollmentStatus.WITHDRAWN,
            EnrollmentStatus.REJECTED,
            EnrollmentStatus.REQUESTED,
            EnrollmentStatus.INVITED,
        ],
    )
    async def test_5_retirado_rechazado_o_pendiente_no_ve_nada(self, estado):
        assert (await _ve(_Uow(estado=estado))).acceso is Acceso.NADA

    async def test_6_sin_evento_nada(self):
        assert (await _ve(_Uow())).acceso is Acceso.NADA

    async def test_7_con_evento_de_un_amigo_sus_amigos(self):
        ve = await _ve(_Uow(), eventos=_Eventos({AMIGO}))

        assert ve.acceso is Acceso.SUS_AMIGOS
        assert ve.amigos == frozenset({AMIGO})

    async def test_los_eventos_se_preguntan_fuera_del_uow_de_competiciones(self):
        """Las unidades de trabajo comparten sesión: una dentro de otra la cerraría."""
        uow = _Uow()

        class _Mira(_Eventos):
            async def amigos_con_evento_en(self, user_id, competition_id):
                assert uow.dentro == 0
                return frozenset({AMIGO})

        assert (await _ve(uow, eventos=_Mira())).acceso is Acceso.SUS_AMIGOS


class TestLoQueVe:
    def test_entero_ve_la_clasificacion_y_cualquier_partida(self):
        ve = LoJugadoQueVe(Acceso.ENTERO)

        assert ve.ve_la_clasificacion
        assert ve.ve_la_partida([OTRO])

    def test_7_con_la_llave_la_clasificacion_y_solo_la_partida_de_su_amigo(self):
        ve = LoJugadoQueVe(Acceso.SUS_AMIGOS, frozenset({AMIGO}))

        assert ve.ve_la_clasificacion
        assert ve.ve_la_partida([OTRO, AMIGO])
        assert not ve.ve_la_partida([OTRO])

    def test_6_nada_ni_la_clasificacion_ni_partidas(self):
        ve = LoJugadoQueVe(Acceso.NADA, frozenset({AMIGO}))

        assert not ve.ve_la_clasificacion
        assert not ve.ve_la_partida([AMIGO])


class TestLaPuerta:
    async def test_6_la_clasificacion_cerrada_para_quien_esta_fuera(self):
        uow = _Uow()

        with pytest.raises(NoPuedeVerloError):
            await PuertaDeLoJugado(uow, _Eventos()).exigir_la_clasificacion(uow.comp.id, YO)

    async def test_7_la_clasificacion_abierta_con_la_llave(self):
        uow = _Uow()

        await PuertaDeLoJugado(uow, _Eventos({AMIGO})).exigir_la_clasificacion(uow.comp.id, YO)

    async def test_la_clasificacion_de_una_ronda_va_por_su_competicion(self):
        uow = _Uow()

        with pytest.raises(NoPuedeVerloError):
            await PuertaDeLoJugado(uow, _Eventos()).exigir_la_clasificacion_de_la_ronda(
                uow.ronda.id, YO
            )
        await PuertaDeLoJugado(uow, _Eventos({AMIGO})).exigir_la_clasificacion_de_la_ronda(
            uow.ronda.id, YO
        )

    async def test_7_el_partido_de_su_amigo_si_y_otro_no(self):
        uow = _Uow()
        puerta = PuertaDeLoJugado(uow, _Eventos({AMIGO}))

        uow.con_partido(OTRO, AMIGO)
        await puerta.exigir_el_partido(uuid4(), YO)
        uow.con_partido(OTRO, UserId(uuid4()))
        with pytest.raises(NoPuedeVerloError):
            await puerta.exigir_el_partido(uuid4(), YO)

    async def test_7_la_partida_de_su_amigo_si_y_otra_no(self):
        uow = _Uow()
        puerta = PuertaDeLoJugado(uow, _Eventos({AMIGO}))

        uow.con_partida(AMIGO, OTRO)
        await puerta.exigir_la_partida(uuid4(), YO)
        uow.con_partida(OTRO)
        with pytest.raises(NoPuedeVerloError):
            await puerta.exigir_la_partida(uuid4(), YO)

    async def test_1_el_organizador_entra_a_cualquier_partida(self):
        uow = _Uow()
        uow.con_partida(OTRO)

        await PuertaDeLoJugado(uow, _Eventos()).exigir_la_partida(uuid4(), CREADOR)

    async def test_un_admin_entra_a_cualquier_partido(self):
        uow = _Uow()
        uow.con_partido(OTRO)

        await PuertaDeLoJugado(uow, _Eventos()).exigir_el_partido(uuid4(), YO, es_admin=True)

    async def test_lo_que_no_existe_lo_dice_luego_su_caso_de_uso(self):
        """Sin partido, partida, ronda o competición no se corta: el caso de uso da su 404."""
        uow = _Uow()
        puerta = PuertaDeLoJugado(uow, _Eventos())

        await puerta.exigir_el_partido(uuid4(), YO)
        await puerta.exigir_la_partida(uuid4(), YO)
        uow.rounds.find_by_id.return_value = None
        await puerta.exigir_la_clasificacion_de_la_ronda(uuid4(), YO)
        uow.competitions.find_by_id.return_value = None
        await puerta.exigir_la_clasificacion(CompetitionId(uuid4()), YO)

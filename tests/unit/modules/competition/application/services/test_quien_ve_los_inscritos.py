"""
Quién ve a los inscritos de una competición (release social 2, tabla del 27 oct 2026).

  #   quien mira                                         | ve
  ----|-------------------------------------------------|----------------------
  1   organizador o admin                                | todo
  2   privada, sin estar dentro                          | nada (solo lo suyo)
  3   privada, con fila de retirado o rechazado          | nada (solo lo suyo)
  4   privada, con invitación pendiente                  | sus amigos aprobados
  5   privada, aprobado                                  | todos los aprobados
  6   pública antes de publicarse, inscrito o no         | sus amigos aprobados
  7   stroke play con las partidas generadas             | todos los aprobados
  8   Ryder con los equipos formados                     | todos los aprobados
  9   capitán o vicecapitán, antes de los equipos        | todos los aprobados
  10  su propia fila                                     | siempre
  11  amigo = amistad aceptada                           | (lo da el puerto)
"""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.services.quien_ve_los_inscritos import (
    Alcance,
    LoQueVe,
    alcance,
)
from src.modules.competition.domain.value_objects.ryder_cup_setup import RyderCupSetup
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId

YO = UserId(uuid4())
CREADOR = UserId(uuid4())


def _competicion(visibilidad=Visibility.PUBLIC, ryder=None, stroke_play=None):
    return SimpleNamespace(
        visibility=visibilidad,
        ryder_cup=ryder,
        stroke_play=stroke_play,
        is_creator=lambda quien: quien == CREADOR,
    )


def _ryder(**capitanes):
    return replace(RyderCupSetup.create("Europa", "América"), **capitanes)


def _alcance(competicion, quien=YO, **como):
    datos = {"es_admin": False, "aprobado": False, "invitado": False, "publicada": False}
    return alcance(competicion, quien, **{**datos, **como})


PRIVADA = Visibility.PRIVATE


class TestElQueOrganiza:
    @pytest.mark.parametrize("visibilidad", [Visibility.PUBLIC, PRIVADA])
    def test_1_el_organizador_lo_ve_todo(self, visibilidad):
        assert _alcance(_competicion(visibilidad), CREADOR) is Alcance.TODO

    @pytest.mark.parametrize("visibilidad", [Visibility.PUBLIC, PRIVADA])
    def test_1_un_admin_lo_ve_todo(self, visibilidad):
        assert _alcance(_competicion(visibilidad), es_admin=True) is Alcance.TODO


class TestUnaPrivada:
    def test_2_sin_estar_dentro_no_ve_a_nadie(self):
        assert _alcance(_competicion(PRIVADA)) is Alcance.NADA

    def test_4_con_invitacion_pendiente_ve_a_sus_amigos(self):
        assert _alcance(_competicion(PRIVADA), invitado=True) is Alcance.AMIGOS

    def test_5_aprobado_ve_a_todos(self):
        assert _alcance(_competicion(PRIVADA), aprobado=True) is Alcance.APROBADOS

    def test_5_aprobado_e_invitado_otra_vez_sigue_viendo_a_todos(self):
        assert _alcance(_competicion(PRIVADA), aprobado=True, invitado=True) is Alcance.APROBADOS

    def test_7_8_publicada_la_ve_cualquiera(self):
        assert _alcance(_competicion(PRIVADA), publicada=True) is Alcance.APROBADOS


class TestUnaPublica:
    def test_6_sin_estar_dentro_ve_a_sus_amigos(self):
        assert _alcance(_competicion()) is Alcance.AMIGOS

    def test_6_inscrito_tambien_solo_a_sus_amigos(self):
        assert _alcance(_competicion(), aprobado=True) is Alcance.AMIGOS

    def test_6_invitado_tambien_solo_a_sus_amigos(self):
        assert _alcance(_competicion(), invitado=True) is Alcance.AMIGOS

    def test_7_8_publicada_ve_a_todos(self):
        assert _alcance(_competicion(), publicada=True) is Alcance.APROBADOS


class TestLosCapitanes:
    @pytest.mark.parametrize(
        "cargo",
        [
            "team_a_captain_id",
            "team_b_captain_id",
            "team_a_vice_captain_id",
            "team_b_vice_captain_id",
        ],
    )
    @pytest.mark.parametrize("visibilidad", [Visibility.PUBLIC, PRIVADA])
    def test_9_capitan_o_vice_ve_a_todos_antes_de_los_equipos(self, cargo, visibilidad):
        competicion = _competicion(visibilidad, ryder=_ryder(**{cargo: YO}))

        assert _alcance(competicion, aprobado=True) is Alcance.APROBADOS

    def test_9_capitan_que_se_retiro_ya_no(self):
        """Revisor: el cargo se queda en la Ryder, pero quien se retiró ya no está."""
        competicion = _competicion(ryder=_ryder(team_a_captain_id=YO))

        assert _alcance(competicion, aprobado=False) is Alcance.AMIGOS

    def test_9_capitan_de_otro_no_cuenta(self):
        competicion = _competicion(ryder=_ryder(team_a_captain_id=UserId(uuid4())))

        assert _alcance(competicion) is Alcance.AMIGOS


class TestLoQueVe:
    AMIGO = UserId(uuid4())
    OTRO = UserId(uuid4())

    @pytest.mark.parametrize("a", [Alcance.TODO, Alcance.APROBADOS])
    def test_completa_ve_a_cualquiera(self, a):
        assert LoQueVe(a, YO).ve_a(self.OTRO) is True

    def test_amigos_ve_a_sus_amigos_y_no_a_otros(self):
        lo = LoQueVe(Alcance.AMIGOS, YO, frozenset({self.AMIGO}))

        assert lo.ve_a(self.AMIGO) is True
        assert lo.ve_a(self.OTRO) is False

    def test_nada_no_ve_ni_a_un_amigo(self):
        lo = LoQueVe(Alcance.NADA, YO, frozenset({self.AMIGO}))

        assert lo.ve_a(self.AMIGO) is False

    @pytest.mark.parametrize("a", list(Alcance))
    def test_10_a_si_mismo_siempre(self, a):
        assert LoQueVe(a, YO).ve_a(YO) is True

    @pytest.mark.parametrize(
        ("a", "completa"),
        [
            (Alcance.TODO, True),
            (Alcance.APROBADOS, True),
            (Alcance.AMIGOS, False),
            (Alcance.NADA, False),
        ],
    )
    def test_si_ve_la_lista_completa(self, a, completa):
        assert LoQueVe(a, YO).completa is completa


# --- De dónde salen los datos (alcance_de) ------------------------------------------

from unittest.mock import AsyncMock

from src.modules.competition.application.services.quien_ve_los_inscritos import (
    alcance_de,
)
from src.modules.competition.domain.value_objects.competition_id import (
    CompetitionId,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


def _uow(*, equipos=None, partidas=()):
    uow = InMemoryUnitOfWork()
    uow.team_assignments.find_by_competition = AsyncMock(return_value=equipos)
    uow.partidas.de_la_competicion = AsyncMock(return_value=list(partidas))
    return uow


def _con_id(**como):
    competicion = _competicion(**como)
    competicion.id = CompetitionId(uuid4())
    return competicion


class TestCuandoEstaPublicada:
    async def test_7_stroke_play_con_partidas_generadas(self):
        competicion = _con_id(stroke_play=object())
        uow = _uow(partidas=[object()])

        async with uow:
            assert await alcance_de(uow, competicion, YO) is Alcance.APROBADOS

    async def test_7_stroke_play_sin_partidas_aun_no(self):
        competicion = _con_id(stroke_play=object())
        uow = _uow(equipos=object())

        async with uow:
            assert await alcance_de(uow, competicion, YO) is Alcance.AMIGOS

    async def test_8_ryder_con_equipos_formados(self):
        competicion = _con_id(ryder=_ryder())
        uow = _uow(equipos=object())

        async with uow:
            assert await alcance_de(uow, competicion, YO) is Alcance.APROBADOS

    async def test_8_ryder_sin_equipos_aun_no(self):
        competicion = _con_id(ryder=_ryder())
        uow = _uow(partidas=[object()])

        async with uow:
            assert await alcance_de(uow, competicion, YO) is Alcance.AMIGOS

    async def test_el_organizador_no_necesita_leer_nada(self):
        competicion = _con_id(visibilidad=PRIVADA)
        uow = _uow()

        async with uow:
            assert await alcance_de(uow, competicion, CREADOR) is Alcance.TODO
        uow.team_assignments.find_by_competition.assert_not_called()

"""
Las franjas del calendario, según quién mira (release social 2, tabla del 27 oct 2026).

  #   quien mira                         | en cada franja
  ----|---------------------------------|-------------------------------------------
  14  no ve la lista completa            | solo sus amigos y él (dentro y esperando);
                                         | las plazas ocupadas, las de verdad
  15  la ve completa (o nadie dice quién) | todos, como siempre
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import GetScheduleRequestDTO
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.test_list_enrollments_privacy import (
    _Amigos,
)
from tests.unit.modules.competition.application.use_cases.test_listas_de_espera_use_cases import (
    _Escenario,
)

pytestmark = pytest.mark.asyncio


class _Publica(_Escenario):
    async def montar(self) -> "_Publica":
        await self.torneo()
        self.competicion._visibility = Visibility.PUBLIC
        async with self.uow:
            await self.uow.competitions.update(self.competicion)
        self.dentro = await self.llena(self.manana)
        self.esperando = await self.aprobado()
        await self.esperar(self.manana, self.esperando)
        self.otro_esperando = await self.aprobado()
        await self.esperar(self.manana, self.otro_esperando)
        self.en_la_tarde = await self.aprobado()
        await self.coger(self.tarde, self.en_la_tarde)
        return self

    async def franjas(self, amigos=None, **quien):
        agenda = await GetScheduleUseCase(self.uow, amigos=amigos).execute(
            GetScheduleRequestDTO(competition_id=self.competicion.id.value), **quien
        )
        return {
            r.session_type: r.tee_sheet
            for dia in agenda.days
            for r in dia.rounds
            if r.round_date == self.manana.round_date
        }


@pytest.fixture
async def p() -> _Publica:
    return await _Publica().montar()


def _ids(*quienes: UserId) -> list:
    return [q.value for q in quienes]


class TestQuienNoVeLaListaCompleta:
    async def test_14_ve_solo_a_sus_amigos_dentro_y_esperando(self, p):
        yo = UserId(uuid4())
        amigos = _Amigos({yo: {p.dentro[1], p.esperando}})

        franjas = await p.franjas(amigos, viewer_id=yo)

        manana = franjas["MORNING"]
        assert manana.player_ids == _ids(p.dentro[1])
        assert manana.waiting_ids == _ids(p.esperando)
        # Las plazas libres salen bien: cuenta a todos los que están dentro
        assert manana.places_taken == 3
        tarde = franjas["AFTERNOON"]
        assert tarde.player_ids == []
        assert tarde.places_taken == 1

    async def test_14_se_ve_a_si_mismo(self, p):
        yo = p.dentro[0]

        franjas = await p.franjas(_Amigos(), viewer_id=yo)

        assert franjas["MORNING"].player_ids == _ids(yo)


class TestLaListaDeEspera:
    """Revisor del front: con la espera filtrada, su puesto y cuántos esperan salían mal."""

    async def test_cuantos_esperan_de_verdad(self, p):
        franjas = await p.franjas(_Amigos(), viewer_id=UserId(uuid4()))

        assert franjas["MORNING"].waiting_ids == []
        assert franjas["MORNING"].waiting_count == 2

    async def test_su_puesto_en_la_espera_de_verdad(self, p):
        # El segundo en esperar, sin amigos delante: sigue siendo el 2.º
        franjas = await p.franjas(_Amigos(), viewer_id=p.otro_esperando)

        assert franjas["MORNING"].waiting_ids == _ids(p.otro_esperando)
        assert franjas["MORNING"].my_waiting_position == 2

    async def test_sin_esperar_no_tiene_puesto(self, p):
        franjas = await p.franjas(_Amigos(), viewer_id=p.dentro[0])

        assert franjas["MORNING"].my_waiting_position is None

    async def test_sin_decir_quien_mira_tampoco(self, p):
        franjas = await p.franjas()

        assert franjas["MORNING"].waiting_count == 2
        assert franjas["MORNING"].my_waiting_position is None


class TestQuienLaVeCompleta:
    async def test_15_el_organizador_ve_a_todos(self, p):
        franjas = await p.franjas(_Amigos(), viewer_id=p.creador)

        assert franjas["MORNING"].player_ids == _ids(*p.dentro)
        assert franjas["MORNING"].waiting_ids == _ids(p.esperando, p.otro_esperando)

    async def test_15_un_admin_ve_a_todos(self, p):
        franjas = await p.franjas(_Amigos(), viewer_id=UserId(uuid4()), viewer_is_admin=True)

        assert franjas["MORNING"].player_ids == _ids(*p.dentro)

    async def test_15_sin_decir_quien_mira_va_completa(self, p):
        """Los usos internos (avisos, próximos partidos) leen la agenda entera."""
        franjas = await p.franjas()

        assert franjas["MORNING"].player_ids == _ids(*p.dentro)
        assert franjas["AFTERNOON"].player_ids == _ids(p.en_la_tarde)

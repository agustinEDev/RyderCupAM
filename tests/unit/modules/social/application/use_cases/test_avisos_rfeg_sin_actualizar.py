"""
Los avisos de Actividad de los hándicaps sin actualizar con la RFEG (15 nov 2026).

| Caso | Aviso                                                    | Para quién                 |
|------|----------------------------------------------------------|----------------------------|
| H2   | «{N} jugadores sin actualizar con la RFEG en {torneo}»   | el organizador (SELF)      |
| H2   | otra pasada con otro N: el aviso se renueva, no se suma  | el organizador             |
| H3   | «No hemos encontrado tu hándicap en la RFEG para {torneo}»| cada no encontrado (SELF) |
| H3   | otra actualización que tampoco lo encuentra: se renueva  | el jugador                 |
| —    | al borrar el torneo se van                               | todos                      |
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
    TournamentRef,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_audience import (
    AUDIENCE_BY_TYPE,
    ActivityAudience,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType as T
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)

pytestmark = pytest.mark.asyncio


def _torneo():
    return TournamentRef(
        competition_id=str(uuid4()),
        name="Copa X",
        start_date=date(2027, 3, 3),
        end_date=date(2027, 3, 4),
        is_public=True,
    )


async def _escenario():
    social, usuarios = InMemorySocialUnitOfWork(), UsuariosEnMemoria()
    gente = []
    for nombre in ("Org", "Ana", "Luis"):
        u = User.create(
            first_name=nombre,
            last_name="Gil",
            email_str=f"rfeg_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with usuarios:
            await usuarios.users.save(u)
        gente.append(u)
    return social, PublishCompetitionNoticesUseCase(social, usuarios), *gente


async def _de(social, quien, tipo):
    async with social:
        eventos = await social.activity_events.find_in(
            [ActivitySlice(user_ids=(quien.id,), types=frozenset(T))], limit=100
        )
    return [e for e in eventos if e.type == tipo]


@pytest.mark.parametrize("tipo", [T.HANDICAPS_NOT_UPDATED, T.RFEG_HANDICAP_NOT_FOUND])
def test_son_solo_de_quien_los_recibe(tipo):
    """Given los dos avisos When se mira su público Then solo los ve quien los recibe."""
    assert AUDIENCE_BY_TYPE[tipo] is ActivityAudience.SELF


class TestAlOrganizador:
    async def test_cuantos_y_de_que_torneo(self):
        """
        Given una actualización que deja 3 jugadores sin actualizar
        When se avisa al organizador
        Then le llega un aviso con el número y el torneo, solo a él (H2)
        """
        social, avisos, org, ana, _ = await _escenario()
        torneo = _torneo()

        await avisos.handicaps_not_updated(org.id, torneo, 3)

        [aviso] = await _de(social, org, T.HANDICAPS_NOT_UPDATED)
        assert aviso.source_match_id == torneo.competition_id
        assert aviso.payload["competition_id"] == torneo.competition_id
        assert aviso.payload["competition_name"] == "Copa X"
        assert aviso.payload["count"] == 3
        assert await _de(social, ana, T.HANDICAPS_NOT_UPDATED) == []

    async def test_otra_pasada_lo_renueva(self):
        """
        Given un aviso de 3 sin actualizar
        When otra pasada deja 1
        Then queda un solo aviso, con 1
        """
        social, avisos, org, _, _ = await _escenario()
        torneo = _torneo()
        await avisos.handicaps_not_updated(org.id, torneo, 3)

        await avisos.handicaps_not_updated(org.id, torneo, 1)

        [aviso] = await _de(social, org, T.HANDICAPS_NOT_UPDATED)
        assert aviso.payload["count"] == 1


class TestAlJugador:
    async def test_a_cada_no_encontrado_el_suyo(self):
        """
        Given dos españoles a los que la RFEG no encontró
        When se les avisa
        Then cada uno recibe el suyo, del torneo (H3)
        """
        social, avisos, org, ana, luis = await _escenario()
        torneo = _torneo()

        await avisos.handicap_not_found(torneo, [ana.id, luis.id])

        for jugador in (ana, luis):
            [aviso] = await _de(social, jugador, T.RFEG_HANDICAP_NOT_FOUND)
            assert aviso.source_match_id == torneo.competition_id
            assert aviso.payload["competition_name"] == "Copa X"
        assert await _de(social, org, T.RFEG_HANDICAP_NOT_FOUND) == []

    async def test_otra_vez_no_encontrado_se_renueva(self):
        """Given su aviso When otra actualización tampoco lo encuentra Then sigue habiendo uno."""
        social, avisos, _, ana, _ = await _escenario()
        torneo = _torneo()
        await avisos.handicap_not_found(torneo, [ana.id])

        await avisos.handicap_not_found(torneo, [ana.id])

        assert len(await _de(social, ana, T.RFEG_HANDICAP_NOT_FOUND)) == 1

    async def test_sin_nadie_no_publica_nada(self):
        """Given nadie no encontrado When se avisa Then no pasa nada."""
        social, avisos, _, ana, _ = await _escenario()

        await avisos.handicap_not_found(_torneo(), [])

        assert await _de(social, ana, T.RFEG_HANDICAP_NOT_FOUND) == []


async def test_al_borrar_el_torneo_se_van():
    """Given los dos avisos When se borra el torneo Then se van con él."""
    social, avisos, org, ana, _ = await _escenario()
    torneo = _torneo()
    await avisos.handicaps_not_updated(org.id, torneo, 1)
    await avisos.handicap_not_found(torneo, [ana.id])

    await avisos.tournament_deleted(torneo.competition_id)

    assert await _de(social, org, T.HANDICAPS_NOT_UPDATED) == []
    assert await _de(social, ana, T.RFEG_HANDICAP_NOT_FOUND) == []

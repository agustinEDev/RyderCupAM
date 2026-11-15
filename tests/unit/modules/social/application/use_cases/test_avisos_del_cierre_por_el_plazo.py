"""
Los avisos del cierre por el plazo, al organizador (15 nov 2026).

    #    aviso                                                     | para quién
    -----|---------------------------------------------------------|------------------------
    C5   «Se han cerrado las inscripciones de X»                   | el organizador (SELF)
    C4   «{N} jugadores sin franja en X: colócalos y cierra»       | el organizador (SELF)
         (o sin hándicap), con el motivo y cuántos                 |
         uno por competición: si vuelve a pasar, se renueva        |
         borrar la competición se los lleva                        |
    C4   al cerrarse por fin, el de «no se puede cerrar» se va     |
    O2   reabierta al mover el torneo, el de «se han cerrado» se va |
    F2   cancelada, el de «no se puede cerrar» se va                |
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
    ActivityAudience,
    audience_of,
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
        is_public=False,
    )


async def _escenario():
    social, usuarios = InMemorySocialUnitOfWork(), UsuariosEnMemoria()
    organizador = User.create(
        first_name="Org",
        last_name="Gil",
        email_str=f"plazo_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with usuarios:
        await usuarios.users.save(organizador)
    return social, PublishCompetitionNoticesUseCase(social, usuarios), organizador


async def _de(social, quien, tipo):
    async with social:
        eventos = await social.activity_events.find_in(
            [ActivitySlice(user_ids=(quien.id,), types=frozenset(T))], limit=100
        )
    return [e for e in eventos if e.type == tipo]


class TestElPublico:
    @pytest.mark.parametrize("tipo", [T.ENROLLMENTS_CLOSED, T.ENROLLMENT_CLOSE_BLOCKED])
    def test_son_solo_del_organizador(self, tipo):
        """C4, C5. Given los dos avisos / Then SELF: los ve solo él."""
        assert audience_of(tipo) is ActivityAudience.SELF

    @pytest.mark.parametrize("tipo", [T.ENROLLMENTS_CLOSED, T.ENROLLMENT_CLOSE_BLOCKED])
    def test_caben_en_la_columna(self, tipo):
        """Given el tipo / Then cabe en VARCHAR(30), sin migración."""
        assert len(tipo.value) <= 30


class TestSeHanCerrado:
    async def test_al_organizador_con_su_torneo(self):
        """C5. Given cerradas por el plazo / Then el organizador recibe el aviso con el torneo."""
        social, avisos, organizador = await _escenario()
        torneo = _torneo()

        await avisos.enrollments_closed(organizador.id, torneo)

        [aviso] = await _de(social, organizador, T.ENROLLMENTS_CLOSED)
        assert aviso.payload["competition_id"] == torneo.competition_id
        assert aviso.payload["competition_name"] == "Copa X"
        assert aviso.source_match_id == torneo.competition_id

    async def test_otra_vez_se_renueva(self):
        """C5. Given ya cerrada una vez por el plazo / When otra vez / Then uno solo: el nuevo."""
        social, avisos, organizador = await _escenario()
        torneo = _torneo()

        await avisos.enrollments_closed(organizador.id, torneo)
        [primero] = await _de(social, organizador, T.ENROLLMENTS_CLOSED)
        await avisos.enrollments_closed(organizador.id, torneo)

        [segundo] = await _de(social, organizador, T.ENROLLMENTS_CLOSED)
        assert segundo.id != primero.id


class TestNoSePuedeCerrar:
    async def test_con_el_motivo_y_cuantos(self):
        """C4. Given 3 sin franja / Then el aviso lleva el motivo y el número."""
        social, avisos, organizador = await _escenario()
        torneo = _torneo()

        await avisos.close_blocked(organizador.id, torneo, "NO_TEE_WINDOW", 3)

        [aviso] = await _de(social, organizador, T.ENROLLMENT_CLOSE_BLOCKED)
        assert aviso.payload["reason"] == "NO_TEE_WINDOW"
        assert aviso.payload["player_count"] == 3
        assert aviso.payload["competition_name"] == "Copa X"

    async def test_otra_vez_se_renueva(self):
        """C4. Given ya avisado / When se avisa otra vez (plazo nuevo) / Then uno, el nuevo."""
        social, avisos, organizador = await _escenario()
        torneo = _torneo()

        await avisos.close_blocked(organizador.id, torneo, "NO_TEE_WINDOW", 3)
        await avisos.close_blocked(organizador.id, torneo, "NO_HANDICAP", 1)

        [aviso] = await _de(social, organizador, T.ENROLLMENT_CLOSE_BLOCKED)
        assert aviso.payload["reason"] == "NO_HANDICAP"


class TestAlCerrarsePorFin:
    async def test_se_retira_el_de_no_se_puede_cerrar(self):
        """
        C4. Given avisado de que no se podía cerrar, y de otra competición también
        When esta se cierra por fin
        Then su aviso de bloqueo se va; el de la otra y el de «se han cerrado» se quedan
        """
        social, avisos, organizador = await _escenario()
        torneo, otro = _torneo(), _torneo()
        await avisos.close_blocked(organizador.id, torneo, "NO_HANDICAP", 1)
        await avisos.close_blocked(organizador.id, otro, "NO_HANDICAP", 1)
        await avisos.enrollments_closed(organizador.id, torneo)

        await avisos.close_block_withdrawn(organizador.id, torneo.competition_id)

        [queda] = await _de(social, organizador, T.ENROLLMENT_CLOSE_BLOCKED)
        assert queda.payload["competition_id"] == otro.competition_id
        assert len(await _de(social, organizador, T.ENROLLMENTS_CLOSED)) == 1


class TestAlReabrirseSolaYAlCancelar:
    async def test_reabierta_al_moverla_se_retira_el_de_cerradas(self):
        """O2. Given «se han cerrado» / When se reabre al mover el torneo / Then se va."""
        social, avisos, organizador = await _escenario()
        torneo, otro = _torneo(), _torneo()
        await avisos.enrollments_closed(organizador.id, torneo)
        await avisos.enrollments_closed(organizador.id, otro)

        await avisos.enrollments_closed_withdrawn(organizador.id, torneo.competition_id)

        [queda] = await _de(social, organizador, T.ENROLLMENTS_CLOSED)
        assert queda.payload["competition_id"] == otro.competition_id

    async def test_cancelada_se_va_el_de_no_se_puede_cerrar(self):
        """F2. Given «no se puede cerrar» / When se cancela la competición / Then se va."""
        social, avisos, organizador = await _escenario()
        torneo = _torneo()
        await avisos.close_blocked(organizador.id, torneo, "NO_HANDICAP", 1)

        await avisos.tournament_cancelled(torneo.competition_id)

        assert await _de(social, organizador, T.ENROLLMENT_CLOSE_BLOCKED) == []


class TestAlBorrarLaCompeticion:
    async def test_se_van_los_dos(self):
        """C4, C5. Given los dos avisos / When se borra la competición / Then no queda ninguno."""
        social, avisos, organizador = await _escenario()
        torneo = _torneo()
        await avisos.close_blocked(organizador.id, torneo, "NO_HANDICAP", 1)
        await avisos.enrollments_closed(organizador.id, torneo)

        await avisos.tournament_deleted(torneo.competition_id)

        assert await _de(social, organizador, T.ENROLLMENTS_CLOSED) == []
        assert await _de(social, organizador, T.ENROLLMENT_CLOSE_BLOCKED) == []

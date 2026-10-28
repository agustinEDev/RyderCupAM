"""
Los avisos de la inscripción directa (release social 3, tabla del 28 oct 2026).

    #    aviso                                              | para quién
    -----|--------------------------------------------------|-------------------------
    A1   «Ana se ha apuntado a Copa X» (o a la espera)      | el organizador (SELF)
    A3   «Has entrado en la franja de las 9:00»             | el que esperaba (SELF)
    A2   ... y sus amigos ven que se ha apuntado            | con plaza y si es pública
    A4   «No hubo plaza en Copa X»                          | quien seguía en espera (SELF)
         volver a entrar quita el «no hubo plaza»           | (como rechazada o quitada)
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
    TeeWindowRef,
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


def _torneo(publico=True):
    return TournamentRef(
        competition_id=str(uuid4()),
        name="Copa X",
        start_date=date(2027, 3, 3),
        end_date=date(2027, 3, 4),
        is_public=publico,
    )


FRANJA = TeeWindowRef(
    round_id="ronda-1", round_date=date(2027, 3, 3), session_type="MORNING", tee_time="09:00"
)


async def _escenario():
    social, usuarios = InMemorySocialUnitOfWork(), UsuariosEnMemoria()
    gente = []
    for nombre in ("Org", "Ana"):
        u = User.create(
            first_name=nombre,
            last_name="Gil",
            email_str=f"directa_{uuid4().hex[:8]}@test.com",
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


@pytest.mark.parametrize(
    "tipo", [T.PLAYER_JOINED, T.PLACE_FROM_WAITING_LIST, T.ENROLLMENT_NO_PLACE]
)
def test_los_tres_son_solo_de_quien_los_recibe(tipo):
    assert AUDIENCE_BY_TYPE[tipo] is ActivityAudience.SELF


class TestA1AlOrganizador:
    async def test_se_ha_apuntado_con_su_franja(self):
        social, avisos, org, ana = await _escenario()
        torneo = _torneo()

        await avisos.joined(org.id, ana.id, torneo, "enr-1", FRANJA, waiting=False)

        [aviso] = await _de(social, org, T.PLAYER_JOINED)
        assert aviso.source_match_id == "enr-1"
        assert aviso.payload["competition_id"] == torneo.competition_id
        assert aviso.payload["player_id"] == str(ana.id.value)
        assert aviso.payload["round_id"] == "ronda-1"
        assert aviso.payload["round_date"] == "2027-03-03"
        assert aviso.payload["session_type"] == "MORNING"
        assert aviso.payload["tee_time"] == "09:00"
        assert aviso.payload["waiting"] is False
        assert await _de(social, ana, T.PLAYER_JOINED) == []

    async def test_a_la_espera(self):
        social, avisos, org, ana = await _escenario()

        await avisos.joined(org.id, ana.id, _torneo(), "enr-1", FRANJA, waiting=True)

        [aviso] = await _de(social, org, T.PLAYER_JOINED)
        assert aviso.payload["waiting"] is True

    async def test_sin_franja(self):
        social, avisos, org, ana = await _escenario()

        await avisos.joined(org.id, ana.id, _torneo(), "enr-1", None, waiting=False)

        [aviso] = await _de(social, org, T.PLAYER_JOINED)
        assert aviso.payload["round_id"] is None
        assert aviso.payload["tee_time"] is None

    async def test_si_vuelve_a_apuntarse_el_aviso_se_renueva(self):
        social, avisos, org, ana = await _escenario()
        torneo = _torneo()
        await avisos.joined(org.id, ana.id, torneo, "enr-1", FRANJA, waiting=True)

        await avisos.joined(org.id, ana.id, torneo, "enr-1", None, waiting=False)

        [aviso] = await _de(social, org, T.PLAYER_JOINED)
        assert aviso.payload["waiting"] is False


class TestA3PlazaDesdeLaEspera:
    async def test_le_llega_su_franja_y_sus_amigos_ven_que_se_apunto(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo(publico=True)

        await avisos.placed_from_waiting_list(ana.id, torneo, FRANJA)

        [aviso] = await _de(social, ana, T.PLACE_FROM_WAITING_LIST)
        assert aviso.source_match_id == "ronda-1"
        assert aviso.payload["tee_time"] == "09:00"
        assert aviso.payload["round_date"] == "2027-03-03"
        assert len(await _de(social, ana, T.ENROLLED_IN_TOURNAMENT)) == 1
        assert len(await _de(social, ana, T.ENROLLMENT_CONFIRMED)) == 1

    async def test_en_una_privada_los_amigos_no(self):
        social, avisos, _, ana = await _escenario()

        await avisos.placed_from_waiting_list(ana.id, _torneo(publico=False), FRANJA)

        assert await _de(social, ana, T.ENROLLED_IN_TOURNAMENT) == []

    async def test_una_segunda_plaza_no_duplica_el_de_inscrito(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()
        otra = TeeWindowRef("ronda-2", date(2027, 3, 4), "MORNING", "10:00")

        await avisos.placed_from_waiting_list(ana.id, torneo, FRANJA)
        await avisos.placed_from_waiting_list(ana.id, torneo, otra)

        assert len(await _de(social, ana, T.PLACE_FROM_WAITING_LIST)) == 2
        assert len(await _de(social, ana, T.ENROLLED_IN_TOURNAMENT)) == 1

    async def test_la_misma_franja_otra_vez_se_renueva(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()

        await avisos.placed_from_waiting_list(ana.id, torneo, FRANJA)
        await avisos.placed_from_waiting_list(ana.id, torneo, FRANJA)

        assert len(await _de(social, ana, T.PLACE_FROM_WAITING_LIST)) == 1


class TestA4SinPlazaAlCerrar:
    async def test_le_llega_que_no_hubo_plaza(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()

        await avisos.no_place(torneo, [(ana.id, "enr-1")])

        [aviso] = await _de(social, ana, T.ENROLLMENT_NO_PLACE)
        assert aviso.source_match_id == "enr-1"
        assert aviso.payload["competition_name"] == "Copa X"

    async def test_si_vuelve_a_entrar_el_aviso_se_va(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()
        await avisos.no_place(torneo, [(ana.id, "enr-1")])

        await avisos.enrolled(ana.id, torneo, "enr-1", accepted_request=False)

        assert await _de(social, ana, T.ENROLLMENT_NO_PLACE) == []


class TestTrasElRevisor:
    """Hallazgos del revisor sin contexto de la BE PR A (28 oct 2026)."""

    async def test_apuntarse_a_la_espera_quita_el_te_han_quitado(self):
        social, avisos, org, ana = await _escenario()
        torneo = _torneo()
        await avisos.removed(ana.id, torneo, "enr-1")

        await avisos.joined(org.id, ana.id, torneo, "enr-1", FRANJA, waiting=True)

        assert await _de(social, ana, T.ENROLLMENT_REMOVED) == []

    async def test_al_irse_se_va_su_has_entrado_en_la_franja(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()
        await avisos.placed_from_waiting_list(ana.id, torneo, FRANJA)

        await avisos.left(ana.id, torneo.competition_id)

        assert await _de(social, ana, T.PLACE_FROM_WAITING_LIST) == []

    async def test_al_borrar_la_franja_se_va_su_has_entrado(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()
        await avisos.placed_from_waiting_list(ana.id, torneo, FRANJA)

        await avisos.round_deleted(torneo.competition_id, FRANJA.round_id)

        assert await _de(social, ana, T.PLACE_FROM_WAITING_LIST) == []

    async def test_se_ha_quitado_la_franja_en_la_que_esperaba(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()

        await avisos.window_removed(ana.id, torneo, "enr-1", FRANJA)

        [aviso] = await _de(social, ana, T.TEE_WINDOW_REMOVED)
        assert aviso.source_match_id == "enr-1"
        assert aviso.payload["tee_time"] == "09:00"
        assert AUDIENCE_BY_TYPE[T.TEE_WINDOW_REMOVED] is ActivityAudience.SELF

    async def test_si_vuelve_a_entrar_el_de_franja_quitada_se_va(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()
        await avisos.window_removed(ana.id, torneo, "enr-1", FRANJA)

        await avisos.enrolled(ana.id, torneo, "enr-1", accepted_request=False)

        assert await _de(social, ana, T.TEE_WINDOW_REMOVED) == []

    async def test_el_de_franja_quitada_se_renueva(self):
        social, avisos, _, ana = await _escenario()
        torneo = _torneo()
        otra = TeeWindowRef("ronda-2", date(2027, 3, 3), "AFTERNOON", "15:00")
        await avisos.window_removed(ana.id, torneo, "enr-1", FRANJA)

        await avisos.window_removed(ana.id, torneo, "enr-1", otra)

        [aviso] = await _de(social, ana, T.TEE_WINDOW_REMOVED)
        assert aviso.payload["tee_time"] == "15:00"

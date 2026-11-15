"""
Los avisos de las invitaciones en espera y de los equipos deshechos (15 nov 2026).

    #    aviso                                                       | para quién
    -----|-----------------------------------------------------------|-----------------------
    P2   «Ya puedes aceptar la invitación a X» (se reabrió)          | el invitado (SELF)
         INVITATION_ACCEPTABLE_AGAIN, uno por invitación (su id)     |
         se renueva si vuelve a pasar; se va al responderla, al      |
         retirarla o al cerrarse otra vez; si ya no se puede         |
         aceptar, el feed no lo enseña (como «Te han invitado»)      |
    P3   «No hubo plaza en X» (empezó o se canceló esperando)        | el invitado (SELF)
         el ENROLLMENT_NO_PLACE de siempre, con el id de la          |
         invitación como origen                                      |
    B3   «{X} ha entrado en {Y}: los equipos se han deshecho y hay   | el organizador (SELF)
         que volver a formarlos», TEAMS_UNDONE_BY_ENTRY, con el      |
         jugador y su nombre; uno por inscripción                    |
"""

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.social.application.feed_visibility import sin_invitaciones_cerradas
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
    TournamentRef,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
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

NUEVOS = [T.INVITATION_ACCEPTABLE_AGAIN, T.TEAMS_UNDONE_BY_ENTRY]


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
    gente = []
    for nombre in ("Org", "Eva"):
        persona = User.create(
            first_name=nombre,
            last_name="Gil",
            email_str=f"espera_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with usuarios:
            await usuarios.users.save(persona)
        gente.append(persona)
    return social, PublishCompetitionNoticesUseCase(social, usuarios), *gente


async def _de(social, quien, tipo):
    async with social:
        eventos = await social.activity_events.find_in(
            [ActivitySlice(user_ids=(quien.id,), types=frozenset(T))], limit=100
        )
    return [e for e in eventos if e.type == tipo]


class TestLosTipos:
    @pytest.mark.parametrize("tipo", NUEVOS)
    async def test_son_solo_de_quien_los_recibe(self, tipo):
        """P2, B3. Given los avisos nuevos / Then SELF: solo los ve quien los recibe."""
        assert audience_of(tipo) is ActivityAudience.SELF

    @pytest.mark.parametrize("tipo", NUEVOS)
    async def test_caben_en_la_columna(self, tipo):
        """Given el tipo / Then cabe en VARCHAR(30), sin migración."""
        assert len(tipo.value) <= 30


class TestYaPuedesAceptar:
    async def test_a_cada_invitado_con_su_invitacion(self):
        """P2. Given dos invitaciones que vuelven / Then a cada uno el suyo, con su origen."""
        social, avisos, organizador, eva = await _escenario()
        torneo = _torneo()
        de_eva, del_org = str(uuid4()), str(uuid4())

        await avisos.invitations_acceptable_again(
            torneo, [(eva.id, de_eva), (organizador.id, del_org)]
        )

        [aviso] = await _de(social, eva, T.INVITATION_ACCEPTABLE_AGAIN)
        assert aviso.source_match_id == de_eva
        assert aviso.payload["competition_id"] == torneo.competition_id
        assert aviso.payload["competition_name"] == "Copa X"
        assert len(await _de(social, organizador, T.INVITATION_ACCEPTABLE_AGAIN)) == 1

    async def test_otra_vez_se_renueva(self):
        """P2. Given ya avisado / When se reabre otra vez / Then uno solo: el nuevo."""
        social, avisos, _, eva = await _escenario()
        torneo, invitacion = _torneo(), str(uuid4())

        await avisos.invitations_acceptable_again(torneo, [(eva.id, invitacion)])
        [primero] = await _de(social, eva, T.INVITATION_ACCEPTABLE_AGAIN)
        await avisos.invitations_acceptable_again(torneo, [(eva.id, invitacion)])

        [segundo] = await _de(social, eva, T.INVITATION_ACCEPTABLE_AGAIN)
        assert segundo.id != primero.id

    @pytest.mark.parametrize("como", ["answered", "withdrawn", "closed"])
    async def test_se_va_al_responderla_retirarla_o_cerrarse(self, como):
        """
        P2. Given el aviso «ya puedes aceptar»
        When la responde, el organizador la retira o se cierra otra vez
        Then el aviso se va, como el de «te han invitado»
        """
        social, avisos, _, eva = await _escenario()
        invitacion = str(uuid4())
        await avisos.invitations_acceptable_again(_torneo(), [(eva.id, invitacion)])

        if como == "answered":
            await avisos.invitation_answered(eva.id, invitacion)
        elif como == "withdrawn":
            await avisos.invitation_withdrawn(eva.id, invitacion)
        else:
            await avisos.invitations_closed([(eva.id, invitacion)])

        assert await _de(social, eva, T.INVITATION_ACCEPTABLE_AGAIN) == []

    async def test_sin_ninguna_no_se_publica_nada(self):
        """P2. Given ninguna que vuelva / Then nada."""
        social, avisos, _, eva = await _escenario()

        await avisos.invitations_acceptable_again(_torneo(), [])

        assert await _de(social, eva, T.INVITATION_ACCEPTABLE_AGAIN) == []

    async def test_el_feed_no_lo_ensena_si_ya_no_se_puede_aceptar(self):
        """P2. Given su invitación ya no se puede aceptar / Then el feed lo oculta."""
        cerrada, abierta = str(uuid4()), str(uuid4())

        class _Invitaciones:
            async def closed_ids(self, ids):
                return {i for i in ids if i == cerrada}

        def _aviso(origen):
            return ActivityEvent.create(
                user_id=User.create(
                    first_name="Eva",
                    last_name="Gil",
                    email_str=f"f_{uuid4().hex[:8]}@test.com",
                    plain_password="SecureP@ssw0rd123",
                ).id,
                type=T.INVITATION_ACCEPTABLE_AGAIN,
                occurred_at=datetime(2026, 11, 15, 12, 0),
                source_match_id=origen,
                payload={"competition_id": str(uuid4()), "competition_name": "Copa"},
                published_at=datetime(2026, 11, 15, 12, 0) + timedelta(minutes=1),
            )

        quedan = await sin_invitaciones_cerradas(
            [_aviso(cerrada), _aviso(abierta)], _Invitaciones()
        )

        assert [e.source_match_id for e in quedan] == [abierta]


class TestNoHuboPlaza:
    async def test_al_invitado_con_su_invitacion_como_origen(self):
        """P3. Given una invitación en espera que se queda sin plaza / Then ENROLLMENT_NO_PLACE."""
        social, avisos, _, eva = await _escenario()
        torneo, invitacion = _torneo(), str(uuid4())

        await avisos.no_place(torneo, [(eva.id, invitacion)])

        [aviso] = await _de(social, eva, T.ENROLLMENT_NO_PLACE)
        assert aviso.source_match_id == invitacion
        assert aviso.payload["competition_id"] == torneo.competition_id


class TestEquiposDeshechos:
    async def test_al_organizador_con_quien_entro(self):
        """
        B3. Given Eva entra y deshace los equipos
        Then el organizador recibe TEAMS_UNDONE_BY_ENTRY con ella y su nombre
        """
        social, avisos, organizador, eva = await _escenario()
        torneo, inscripcion = _torneo(), str(uuid4())

        await avisos.teams_undone_by_entry(organizador.id, eva.id, torneo, inscripcion)

        [aviso] = await _de(social, organizador, T.TEAMS_UNDONE_BY_ENTRY)
        assert aviso.source_match_id == inscripcion
        assert aviso.payload["competition_id"] == torneo.competition_id
        assert aviso.payload["player_id"] == str(eva.id.value)
        assert aviso.payload["player_name"] == eva.display_name_or_legal(True)
        assert await _de(social, eva, T.TEAMS_UNDONE_BY_ENTRY) == []

    async def test_con_el_nombre_que_eligio_para_esa_competicion(self):
        """B3. Given eligió no mostrar su nombre real / Then el aviso usa el que eligió."""
        social, avisos, organizador, eva = await _escenario()
        eva.update_profile(alias="Evita")

        await avisos.teams_undone_by_entry(
            organizador.id, eva.id, _torneo(), str(uuid4()), use_real_name=False
        )

        [aviso] = await _de(social, organizador, T.TEAMS_UNDONE_BY_ENTRY)
        assert aviso.payload["player_name"] == "Evita"

    async def test_otra_vez_se_renueva(self):
        """B3. Given ya avisado por esa inscripción / When vuelve a pasar / Then uno: el nuevo."""
        social, avisos, organizador, eva = await _escenario()
        torneo, inscripcion = _torneo(), str(uuid4())

        await avisos.teams_undone_by_entry(organizador.id, eva.id, torneo, inscripcion)
        [primero] = await _de(social, organizador, T.TEAMS_UNDONE_BY_ENTRY)
        await avisos.teams_undone_by_entry(organizador.id, eva.id, torneo, inscripcion)

        [segundo] = await _de(social, organizador, T.TEAMS_UNDONE_BY_ENTRY)
        assert segundo.id != primero.id

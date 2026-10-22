"""
Tests de los avisos de Actividad que salen de una competicion (BE-2).

Los numeros de cada test son los de la tabla aprobada el 21 oct 2026: A (avisos
de inscripcion, solo tuyos), B (amigo apuntado, lo ven sus amigos) y C
(resultados de torneo, solo tuyos).
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    MatchOutcome,
    PublishCompetitionNoticesUseCase,
    StandingRef,
    TournamentRef,
)
from src.modules.social.application.use_cases.set_activity_sharing_use_case import (
    SetActivitySharingUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

T = ActivityEventType


def _torneo(is_public: bool = True, competition_id: str | None = None) -> TournamentRef:
    return TournamentRef(
        competition_id=competition_id or str(uuid4()),
        name="Torneo RyderCup Atlantica",
        start_date=date(2027, 3, 3),
        end_date=date(2027, 3, 4),
        is_public=is_public,
    )


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def avisos(social_uow, user_uow):
    return PublishCompetitionNoticesUseCase(social_uow, user_uow)


async def _user(user_uow, share_activity: bool = True) -> User:
    user = User.create(
        first_name="Juan",
        last_name="Lopez",
        email_str=f"avisos_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if not share_activity:
        user.set_activity_sharing(False)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _amigos(social_uow, a: User, b: User) -> None:
    friendship = Friendship.create(id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id)
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)


async def _guardados(social_uow, user: User):
    async with social_uow:
        return await social_uow.activity_events.find_in(
            [ActivitySlice(user_ids=(user.id,), types=frozenset(ActivityEventType))], limit=100
        )


async def _tipos(social_uow, user: User) -> list[ActivityEventType]:
    return sorted(e.type for e in await _guardados(social_uow, user))


async def _feed(social_uow, user_uow, viewer: User):
    return await GetFriendsFeedUseCase(
        social_uow, user_uow, InMemoryGolfCourseUnitOfWork()
    ).execute(str(viewer.id.value))


class TestAvisosDeInscripcion:
    async def test_a1_aceptar_tu_solicitud_te_avisa_una_vez(self, avisos, social_uow, user_uow):
        """
        A1. Given una solicitud aprobada en un torneo privado / When se avisa /
        Then un ENROLLMENT_APPROVED con el torneo, solo para mi.
        """
        yo = await _user(user_uow)
        torneo = _torneo(is_public=False)

        await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=True)

        eventos = await _guardados(social_uow, yo)
        assert [e.type for e in eventos] == [T.ENROLLMENT_APPROVED]
        payload = eventos[0].payload
        assert payload["competition_id"] == torneo.competition_id
        assert payload["competition_name"] == "Torneo RyderCup Atlantica"
        assert payload["start_date"] == "2027-03-03"
        assert payload["end_date"] == "2027-03-04"

    async def test_a2_la_inscripcion_directa_no_avisa_de_aceptacion(
        self, avisos, social_uow, user_uow
    ):
        """
        A2 y C (22 oct). Given una inscripcion directa en un torneo publico /
        When se avisa / Then no hay aviso de aceptacion: «ya estas inscrito»
        para mi y el de los amigos (B8).
        """
        yo = await _user(user_uow)

        await avisos.enrolled(yo.id, _torneo(), "enr-1", accepted_request=False)

        assert await _tipos(social_uow, yo) == sorted(
            [T.ENROLLMENT_CONFIRMED, T.ENROLLED_IN_TOURNAMENT]
        )

    async def test_a3_una_invitacion_te_avisa(self, avisos, social_uow, user_uow):
        """A3. Given una invitacion / When se avisa / Then INVITED_TO_TOURNAMENT."""
        yo = await _user(user_uow)
        torneo = _torneo()

        await avisos.invited(yo.id, torneo, "inv-1")

        eventos = await _guardados(social_uow, yo)
        assert [e.type for e in eventos] == [T.INVITED_TO_TOURNAMENT]
        assert eventos[0].source_match_id == "inv-1"
        assert eventos[0].payload["competition_id"] == torneo.competition_id

    async def test_a4_retirar_la_invitacion_borra_su_aviso(self, avisos, social_uow, user_uow):
        """
        A4. Given dos invitaciones avisadas / When el organizador retira una /
        Then desaparece ese aviso y el otro sigue.
        """
        yo = await _user(user_uow)
        await avisos.invited(yo.id, _torneo(), "inv-1")
        await avisos.invited(yo.id, _torneo(), "inv-2")

        await avisos.invitation_withdrawn(yo.id, "inv-1")

        assert [e.source_match_id for e in await _guardados(social_uow, yo)] == ["inv-2"]

    async def test_a5_solicitudes_cerradas_al_empezar(self, avisos, social_uow, user_uow):
        """
        A5. Given dos solicitudes rechazadas al empezar / When se avisa / Then
        cada uno tiene su «se cerro sin plaza».
        """
        ana = await _user(user_uow)
        eva = await _user(user_uow)
        torneo = _torneo()

        await avisos.requests_closed(torneo, [(ana.id, "enr-a"), (eva.id, "enr-e")])

        assert await _tipos(social_uow, ana) == [T.ENROLLMENT_REQUEST_CLOSED]
        assert await _tipos(social_uow, eva) == [T.ENROLLMENT_REQUEST_CLOSED]
        (evento,) = await _guardados(social_uow, ana)
        assert evento.payload["competition_name"] == torneo.name

    async def test_a6_el_rechazo_a_mano_es_otro_aviso(self, avisos, social_uow, user_uow):
        """A6. Given un rechazo del organizador / When se avisa / Then ENROLLMENT_REJECTED."""
        yo = await _user(user_uow)

        await avisos.request_rejected(yo.id, _torneo(), "enr-1")

        assert await _tipos(social_uow, yo) == [T.ENROLLMENT_REJECTED]

    async def test_a7_repetir_el_mismo_aviso_no_lo_duplica(self, avisos, social_uow, user_uow):
        """
        A7. Given cada aviso dado dos veces (un reintento) / When se mira lo
        guardado / Then uno de cada.
        """
        yo = await _user(user_uow)
        torneo = _torneo()
        for _ in range(2):
            await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=True)
            await avisos.invited(yo.id, torneo, "inv-1")
            await avisos.requests_closed(torneo, [(yo.id, "enr-2")])
            await avisos.request_rejected(yo.id, torneo, "enr-3")

        assert await _tipos(social_uow, yo) == sorted(
            [
                T.ENROLLMENT_APPROVED,
                T.ENROLLED_IN_TOURNAMENT,
                T.INVITED_TO_TOURNAMENT,
                T.ENROLLMENT_REQUEST_CLOSED,
                T.ENROLLMENT_REJECTED,
            ]
        )

    async def test_los_avisos_propios_no_los_ven_mis_amigos(self, avisos, social_uow, user_uow):
        """Given avisos SELF mios / When mi amigo pide su feed / Then no ve ninguno."""
        yo = await _user(user_uow)
        amigo = await _user(user_uow)
        await _amigos(social_uow, yo, amigo)
        torneo = _torneo(is_public=False)
        await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=True)
        await avisos.invited(yo.id, torneo, "inv-1")

        assert (await _feed(social_uow, user_uow, amigo)).events == []
        assert len((await _feed(social_uow, user_uow, yo)).events) == 2


class TestAmigoApuntado:
    async def test_b8_apuntarte_a_un_publico_lo_ven_tus_amigos(self, avisos, social_uow, user_uow):
        """
        B8. Given me apuntan a un torneo publico (aprobada mi solicitud) / When
        mi amigo pide su feed / Then ve «X se ha apuntado a Y» con las fechas, y
        yo veo mi aviso de aceptado pero no el de amigos.
        """
        yo = await _user(user_uow)
        amigo = await _user(user_uow)
        await _amigos(social_uow, yo, amigo)
        torneo = _torneo()

        await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=True)

        del_amigo = (await _feed(social_uow, user_uow, amigo)).events
        assert [e.type for e in del_amigo] == [T.ENROLLED_IN_TOURNAMENT.value]
        assert del_amigo[0].payload["start_date"] == "2027-03-03"
        assert del_amigo[0].source_match_id == torneo.competition_id
        mio = (await _feed(social_uow, user_uow, yo)).events
        assert [e.type for e in mio] == [T.ENROLLMENT_APPROVED.value]

    async def test_b9_un_torneo_privado_no_se_publica(self, avisos, social_uow, user_uow):
        """B9. Given me apuntan a uno privado / When se avisa / Then nada para mis amigos."""
        yo = await _user(user_uow)

        await avisos.enrolled(yo.id, _torneo(is_public=False), "enr-1", accepted_request=False)

        # Solo mi «ya estas inscrito» (C, 22 oct): nada de amigos
        assert await _tipos(social_uow, yo) == [T.ENROLLMENT_CONFIRMED]

    async def test_b10_quien_no_es_amigo_no_lo_ve(self, avisos, social_uow, user_uow):
        """B10. Given me apunto a uno publico / When un no amigo pide su feed / Then nada."""
        yo = await _user(user_uow)
        extranio = await _user(user_uow)

        await avisos.enrolled(yo.id, _torneo(), "enr-1", accepted_request=False)

        assert (await _feed(social_uow, user_uow, extranio)).events == []

    async def test_b11_retirarte_borra_el_aviso_de_amigos(self, avisos, social_uow, user_uow):
        """
        B11. Given apuntado a dos torneos / When me retiro de uno / Then su aviso
        desaparece; el del otro y el de aceptado siguen.
        """
        yo = await _user(user_uow)
        uno, otro = _torneo(), _torneo()
        await avisos.enrolled(yo.id, uno, "enr-1", accepted_request=True)
        await avisos.enrolled(yo.id, otro, "enr-2", accepted_request=False)

        await avisos.left(yo.id, uno.competition_id)

        eventos = await _guardados(social_uow, yo)
        assert sorted((e.type, e.source_match_id) for e in eventos) == sorted(
            [
                (T.ENROLLMENT_APPROVED, "enr-1"),
                (T.ENROLLED_IN_TOURNAMENT, otro.competition_id),
                (T.ENROLLMENT_CONFIRMED, otro.competition_id),
            ]
        )

    async def test_b11_retirarse_no_borra_el_aviso_de_los_demas(self, avisos, social_uow, user_uow):
        """B11. Given dos apuntados al mismo torneo / When uno se retira / Then el del otro sigue."""
        ana = await _user(user_uow)
        eva = await _user(user_uow)
        torneo = _torneo()
        await avisos.enrolled(ana.id, torneo, "enr-a", accepted_request=False)
        await avisos.enrolled(eva.id, torneo, "enr-e", accepted_request=False)

        await avisos.left(ana.id, torneo.competition_id)

        assert await _tipos(social_uow, ana) == []
        assert await _tipos(social_uow, eva) == sorted(
            [T.ENROLLMENT_CONFIRMED, T.ENROLLED_IN_TOURNAMENT]
        )

    async def test_b11_cancelar_el_torneo_borra_los_avisos_de_todos(
        self, avisos, social_uow, user_uow
    ):
        """B11. Given dos apuntados / When se cancela el torneo / Then ningun aviso de amigos."""
        ana = await _user(user_uow)
        eva = await _user(user_uow)
        torneo = _torneo()
        await avisos.enrolled(ana.id, torneo, "enr-a", accepted_request=False)
        await avisos.enrolled(eva.id, torneo, "enr-e", accepted_request=False)

        await avisos.tournament_cancelled(torneo.competition_id)

        assert await _tipos(social_uow, ana) == []
        assert await _tipos(social_uow, eva) == []

    async def test_1_pasar_a_privada_borra_los_avisos_de_apuntado(
        self, avisos, social_uow, user_uow
    ):
        """1. Given dos apuntados a un publico / When pasa a privado / Then sin avisos de amigos."""
        ana = await _user(user_uow)
        eva = await _user(user_uow)
        torneo = _torneo()
        otro = _torneo()
        await avisos.enrolled(ana.id, torneo, "enr-a", accepted_request=True)
        await avisos.enrolled(eva.id, torneo, "enr-e", accepted_request=False)
        await avisos.enrolled(eva.id, otro, "enr-o", accepted_request=False)

        await avisos.tournament_made_private(torneo.competition_id)

        assert await _tipos(social_uow, ana) == [T.ENROLLMENT_APPROVED]
        # Su «ya estas inscrito» es solo suyo: pasar a privado no lo toca
        assert sorted(
            (e.type, e.source_match_id) for e in await _guardados(social_uow, eva)
        ) == sorted(
            [
                (T.ENROLLMENT_CONFIRMED, torneo.competition_id),
                (T.ENROLLMENT_CONFIRMED, otro.competition_id),
                (T.ENROLLED_IN_TOURNAMENT, otro.competition_id),
            ]
        )

    async def test_2_borrar_el_torneo_borra_todos_sus_avisos(self, avisos, social_uow, user_uow):
        """
        2. Given avisos de todo tipo de un torneo y de otro / When se borra / Then
        no queda ninguno del borrado, aunque su origen sea la inscripcion, la
        invitacion o el partido.
        """
        yo = await _user(user_uow)
        torneo = _torneo()
        otro = _torneo()
        await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=True)
        await avisos.enrolled(yo.id, torneo, "enr-4", accepted_request=False)
        await avisos.invited(yo.id, torneo, "inv-1")
        await avisos.request_rejected(yo.id, torneo, "enr-2")
        await avisos.requests_closed(torneo, [(yo.id, "enr-3")])
        await avisos.match_finished(
            torneo,
            MatchOutcome(str(uuid4()), date(2027, 3, 3), (yo.id,), (), "A", "1UP"),
        )
        await avisos.final_standings(torneo, "MEDAL", [StandingRef(yo.id, 1, False, 0, "OK")])
        await avisos.invited(yo.id, otro, "inv-otro")

        await avisos.tournament_deleted(torneo.competition_id)

        assert [(e.type, e.source_match_id) for e in await _guardados(social_uow, yo)] == [
            (T.INVITED_TO_TOURNAMENT, "inv-otro")
        ]

    async def test_b12_con_la_publicacion_apagada_no_lo_ven_ni_al_encenderla(
        self, avisos, social_uow, user_uow
    ):
        """
        B12. Given la publicacion apagada / When me apunto y luego la enciendo /
        Then mi amigo no lo ve ni entonces ni despues.
        """
        yo = await _user(user_uow, share_activity=False)
        amigo = await _user(user_uow)
        await _amigos(social_uow, yo, amigo)

        await avisos.enrolled(yo.id, _torneo(), "enr-1", accepted_request=False)
        assert (await _feed(social_uow, user_uow, amigo)).events == []

        await SetActivitySharingUseCase(user_uow, social_uow).execute(
            str(yo.id.value), enabled=True
        )
        assert (await _feed(social_uow, user_uow, amigo)).events == []
        guardado = next(
            e for e in await _guardados(social_uow, yo) if e.type == T.ENROLLED_IN_TOURNAMENT
        )
        assert guardado.visible_to_friends is False


class TestResultadosDeTorneo:
    def _partido(self, team_a, team_b, winner, score) -> MatchOutcome:
        return MatchOutcome(
            match_id=str(uuid4()),
            played_on=date(2027, 3, 3),
            team_a=tuple(u.id for u in team_a),
            team_b=tuple(u.id for u in team_b),
            winner=winner,
            score=score,
        )

    async def test_c13_cada_jugador_su_resultado(self, avisos, social_uow, user_uow):
        """
        C13. Given un fourball que gana A 3&2 / When se avisa / Then cuatro
        avisos: WON para A, LOST para B, con el 3&2, rivales y companero.
        """
        a1, a2, b1, b2 = [await _user(user_uow) for _ in range(4)]
        partido = self._partido([a1, a2], [b1, b2], "A", "3&2")

        await avisos.match_finished(_torneo(), partido)

        (de_a1,) = await _guardados(social_uow, a1)
        (de_b2,) = await _guardados(social_uow, b2)
        assert de_a1.type == T.TOURNAMENT_MATCH_RESULT
        assert de_a1.source_match_id == partido.match_id
        assert de_a1.payload["outcome"] == "WON"
        assert de_a1.payload["score"] == "3&2"
        assert de_a1.payload["opponent_ids"] == [str(b1.id.value), str(b2.id.value)]
        assert de_a1.payload["partner_ids"] == [str(a2.id.value)]
        assert de_b2.payload["outcome"] == "LOST"
        assert de_b2.payload["opponent_ids"] == [str(a1.id.value), str(a2.id.value)]
        assert de_b2.payload["partner_ids"] == [str(b1.id.value)]

    @pytest.mark.parametrize(
        ("winner", "score", "de_a", "de_b"),
        [
            ("HALVED", "AS", "HALVED", "HALVED"),
            ("B", "CONCEDED", "LOST", "WON"),
            ("A", "W/O", "WON", "LOST"),
        ],
    )
    async def test_c13_empate_concesion_y_walkover(
        self, avisos, social_uow, user_uow, winner, score, de_a, de_b
    ):
        """C13. Given empate, concesion o walkover / When se avisa / Then el lado de cada uno."""
        a = await _user(user_uow)
        b = await _user(user_uow)

        await avisos.match_finished(_torneo(), self._partido([a], [b], winner, score))

        (de_a_evt,) = await _guardados(social_uow, a)
        (de_b_evt,) = await _guardados(social_uow, b)
        assert (de_a_evt.payload["outcome"], de_a_evt.payload["score"]) == (de_a, score)
        assert (de_b_evt.payload["outcome"], de_b_evt.payload["score"]) == (de_b, score)

    async def test_c13_sin_ganador_no_se_avisa(self, avisos, social_uow, user_uow):
        """Given un partido cerrado sin ningun hoyo validado / When se avisa / Then nada."""
        a = await _user(user_uow)
        b = await _user(user_uow)

        await avisos.match_finished(_torneo(), self._partido([a], [b], None, None))

        assert await _tipos(social_uow, a) == []

    async def test_c13_el_resultado_es_solo_tuyo_y_no_se_duplica(
        self, avisos, social_uow, user_uow
    ):
        """C13. Given el mismo partido avisado dos veces / Then uno, y mi amigo no lo ve."""
        a = await _user(user_uow)
        b = await _user(user_uow)
        amigo = await _user(user_uow)
        await _amigos(social_uow, a, amigo)
        partido = self._partido([a], [b], "A", "2UP")

        await avisos.match_finished(_torneo(), partido)
        await avisos.match_finished(_torneo(), partido)

        assert await _tipos(social_uow, a) == [T.TOURNAMENT_MATCH_RESULT]
        assert (await _feed(social_uow, user_uow, amigo)).events == []

    async def test_c14_clasificacion_final_para_cada_inscrito(self, avisos, social_uow, user_uow):
        """
        C14. Given la general oficial de un Stableford / When se avisa / Then
        cada jugador su puesto, de cuantos, empatado o no y sus puntos.
        """
        ana, eva, luz = [await _user(user_uow) for _ in range(3)]
        torneo = _torneo()
        filas = [
            StandingRef(ana.id, 1, True, 36, "CLASIFICADO"),
            StandingRef(eva.id, 1, True, 36, "CLASIFICADO"),
            StandingRef(luz.id, None, False, None, "NP"),
        ]

        await avisos.final_standings(torneo, "STABLEFORD", filas)

        (de_eva,) = await _guardados(social_uow, eva)
        assert de_eva.type == T.TOURNAMENT_FINAL_STANDING
        assert de_eva.source_match_id == torneo.competition_id
        assert de_eva.payload["position"] == 1
        assert de_eva.payload["tied"] is True
        assert de_eva.payload["total_players"] == 3
        assert de_eva.payload["value"] == 36
        assert de_eva.payload["tournament_type"] == "STABLEFORD"
        (de_luz,) = await _guardados(social_uow, luz)
        assert de_luz.payload["position"] is None
        assert de_luz.payload["status"] == "NP"

    async def test_c15_reabrir_y_cerrar_deja_el_puesto_nuevo(self, avisos, social_uow, user_uow):
        """
        C15. Given 4.º al cerrar / When se reabre y se vuelve a cerrar con 2.º /
        Then queda el 2.º, uno solo.
        """
        yo = await _user(user_uow)
        torneo = _torneo()
        await avisos.final_standings(
            torneo, "MEDAL", [StandingRef(yo.id, 4, False, 3, "CLASIFICADO")]
        )

        await avisos.reopened(torneo.competition_id)
        assert await _tipos(social_uow, yo) == []
        await avisos.final_standings(
            torneo, "MEDAL", [StandingRef(yo.id, 2, False, -1, "CLASIFICADO")]
        )

        (evento,) = await _guardados(social_uow, yo)
        assert evento.payload["position"] == 2
        assert evento.payload["value"] == -1

    async def test_4_cerrar_otra_vez_sustituye_aunque_no_se_borrara_al_reabrir(
        self, avisos, social_uow, user_uow, monkeypatch
    ):
        """
        4. Given 4.º publicado y un reabrir cuyo borrado fallo / When se cierra
        con 2.º / Then queda el 2.º, uno solo, y en una sola transaccion.
        """
        yo = await _user(user_uow)
        torneo = _torneo()
        await avisos.final_standings(
            torneo, "MEDAL", [StandingRef(yo.id, 4, False, 3, "CLASIFICADO")]
        )
        entradas = []
        original = type(social_uow).__aenter__

        async def _cuenta(uow):
            entradas.append(1)
            return await original(uow)

        monkeypatch.setattr(type(social_uow), "__aenter__", _cuenta)

        await avisos.final_standings(
            torneo, "MEDAL", [StandingRef(yo.id, 2, False, -1, "CLASIFICADO")]
        )

        monkeypatch.undo()
        (evento,) = await _guardados(social_uow, yo)
        assert evento.payload["position"] == 2
        assert len(entradas) == 1

    async def test_reabrir_no_toca_otros_avisos_del_torneo(self, avisos, social_uow, user_uow):
        """Given apuntado y clasificado / When se reabre / Then el aviso de apuntado sigue."""
        yo = await _user(user_uow)
        torneo = _torneo()
        await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=False)
        await avisos.final_standings(
            torneo, "MEDAL", [StandingRef(yo.id, 1, False, 0, "CLASIFICADO")]
        )

        await avisos.reopened(torneo.competition_id)

        assert await _tipos(social_uow, yo) == sorted(
            [T.ENROLLMENT_CONFIRMED, T.ENROLLED_IN_TOURNAMENT]
        )


class TestTablaCInscripcionConfirmada:
    async def test_c_aceptar_una_invitacion_o_ser_inscrito_te_confirma(
        self, avisos, social_uow, user_uow
    ):
        """
        C. Given me inscriben sin solicitud (invitacion aceptada o el organizador)
        / When se avisa / Then ENROLLMENT_CONFIRMED con el torneo, por el torneo.
        """
        yo = await _user(user_uow)
        torneo = _torneo(is_public=False)

        await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=False)

        (evento,) = await _guardados(social_uow, yo)
        assert evento.type == T.ENROLLMENT_CONFIRMED
        assert evento.source_match_id == torneo.competition_id
        assert evento.payload == {
            "competition_id": torneo.competition_id,
            "competition_name": "Torneo RyderCup Atlantica",
            "start_date": "2027-03-03",
            "end_date": "2027-03-04",
        }

    async def test_c_aprobar_tu_solicitud_no_duplica_con_confirmada(
        self, avisos, social_uow, user_uow
    ):
        """C. Given el organizador aprueba mi solicitud / Then ENROLLMENT_APPROVED, sin CONFIRMED."""
        yo = await _user(user_uow)

        await avisos.enrolled(yo.id, _torneo(is_public=False), "enr-1", accepted_request=True)

        assert await _tipos(social_uow, yo) == [T.ENROLLMENT_APPROVED]

    async def test_c_confirmada_es_solo_tuya(self, avisos, social_uow, user_uow):
        """C. Given me inscriben en uno privado / When mi amigo y yo miramos / Then solo yo."""
        yo = await _user(user_uow)
        amigo = await _user(user_uow)
        await _amigos(social_uow, yo, amigo)

        await avisos.enrolled(yo.id, _torneo(is_public=False), "enr-1", accepted_request=False)

        assert (await _feed(social_uow, user_uow, amigo)).events == []
        assert [e.type for e in (await _feed(social_uow, user_uow, yo)).events] == [
            T.ENROLLMENT_CONFIRMED.value
        ]

    async def test_c_repetir_no_duplica(self, avisos, social_uow, user_uow):
        yo = await _user(user_uow)
        torneo = _torneo(is_public=False)

        for _ in range(2):
            await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=False)

        assert await _tipos(social_uow, yo) == [T.ENROLLMENT_CONFIRMED]

    async def test_c_retirarte_borra_tu_confirmada_y_no_la_de_otros(
        self, avisos, social_uow, user_uow
    ):
        ana = await _user(user_uow)
        eva = await _user(user_uow)
        torneo, otro = _torneo(is_public=False), _torneo(is_public=False)
        await avisos.enrolled(ana.id, torneo, "enr-a", accepted_request=False)
        await avisos.enrolled(ana.id, otro, "enr-o", accepted_request=False)
        await avisos.enrolled(eva.id, torneo, "enr-e", accepted_request=False)

        await avisos.left(ana.id, torneo.competition_id)

        assert [(e.type, e.source_match_id) for e in await _guardados(social_uow, ana)] == [
            (T.ENROLLMENT_CONFIRMED, otro.competition_id)
        ]
        assert await _tipos(social_uow, eva) == [T.ENROLLMENT_CONFIRMED]

    async def test_c_cancelar_borra_las_confirmadas_de_todos(self, avisos, social_uow, user_uow):
        ana = await _user(user_uow)
        eva = await _user(user_uow)
        torneo = _torneo(is_public=False)
        await avisos.enrolled(ana.id, torneo, "enr-a", accepted_request=False)
        await avisos.enrolled(eva.id, torneo, "enr-e", accepted_request=False)

        await avisos.tournament_cancelled(torneo.competition_id)

        assert await _tipos(social_uow, ana) == []
        assert await _tipos(social_uow, eva) == []

    async def test_c_volver_a_inscribirte_tras_retirarte_te_confirma_otra_vez(
        self, avisos, social_uow, user_uow
    ):
        yo = await _user(user_uow)
        torneo = _torneo(is_public=False)
        await avisos.enrolled(yo.id, torneo, "enr-1", accepted_request=False)
        await avisos.left(yo.id, torneo.competition_id)

        await avisos.enrolled(yo.id, torneo, "enr-2", accepted_request=False)

        assert await _tipos(social_uow, yo) == [T.ENROLLMENT_CONFIRMED]

    async def test_c_responder_la_invitacion_borra_su_aviso(self, avisos, social_uow, user_uow):
        """
        C. Given dos invitaciones avisadas / When respondo a una (aceptar o
        rechazar) / Then desaparece su aviso de invitado y el otro sigue.
        """
        yo = await _user(user_uow)
        otro = await _user(user_uow)
        await avisos.invited(yo.id, _torneo(), "inv-1")
        await avisos.invited(yo.id, _torneo(), "inv-2")
        await avisos.invited(otro.id, _torneo(), "inv-1")

        await avisos.invitation_answered(yo.id, "inv-1")

        assert [e.source_match_id for e in await _guardados(social_uow, yo)] == ["inv-2"]
        assert [e.source_match_id for e in await _guardados(social_uow, otro)] == ["inv-1"]


class TestInvitacionesCerradasSolas:
    async def test_cerradas_solas_retiran_cada_una_su_aviso(self, avisos, social_uow, user_uow):
        """
        Given tres invitaciones avisadas / When se cierran solas dos (sin plaza o
        caducadas) / Then sus avisos desaparecen; la tercera y las de otros siguen.
        """
        ana = await _user(user_uow)
        eva = await _user(user_uow)
        await avisos.invited(ana.id, _torneo(), "inv-a")
        await avisos.invited(eva.id, _torneo(), "inv-e")
        await avisos.invited(ana.id, _torneo(), "inv-otra")
        await avisos.invited(eva.id, _torneo(), "inv-a")

        await avisos.invitations_closed([(ana.id, "inv-a"), (eva.id, "inv-e")])

        assert [e.source_match_id for e in await _guardados(social_uow, ana)] == ["inv-otra"]
        assert [e.source_match_id for e in await _guardados(social_uow, eva)] == ["inv-a"]

    async def test_sin_ninguna_no_hace_nada(self, avisos, social_uow, user_uow):
        ana = await _user(user_uow)
        await avisos.invited(ana.id, _torneo(), "inv-a")

        await avisos.invitations_closed([])

        assert len(await _guardados(social_uow, ana)) == 1

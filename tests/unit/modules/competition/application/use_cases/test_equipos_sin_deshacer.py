"""
Los equipos de una Ryder ya no se deshacen (release social 3, tabla del 28 oct 2026).

Cambia lo decidido el 27 oct: ni entrar ni salir deshace el reparto.

    #    caso                                                | queda
    -----|---------------------------------------------------|---------------------------------
    T1   entra alguien con los equipos formados             | el reparto igual; él, sin equipo
    T2   sale uno de un equipo (se retira o le quitan)      | sale de su equipo; los demás igual
    T2   ... si era subcapitán                              | el puesto, vacío
    T2   ... si era capitán                                 | sube su subcapitán (como hoy)
    T2   ... con partidos generados                         | el reparto no se toca
    T3   el organizador mueve a uno de A a B                | movido
    T3   ... a uno sin equipo                               | puesto en el suyo
    T3   ... a un capitán                                   | CaptainCannotMoveError
    T3   ... a un subcapitán                                | movido y sin el puesto
    T3   ... con partidos, sin equipos o sin ser org.       | error
    T4   cualquier cambio                                   | los dos sobres a borrador y aviso
                                                         | a los dos capitanes
    T5   generar con alguien sin equipo / A y B a más de 1  | error (con uno de diferencia, sí)
    T6   con la sala de draft abierta no entra nadie         | DraftInProgressError
    T7   la sala de draft, las sesiones y los capitanes      | se quedan
    A1   se vuelven a formar sin partidos (también revelados)| los dos sobres a borrador y aviso
    A2   se forman la primera vez                            | ni se reabre ni se avisa
    A3   ... sin sobres entregados                           | se avisa igual
    A4   ... con partidos                                    | ni se reabre ni se avisa
    D1   tras el draft, uno cambia de equipo                 | la sala, con los equipos de verdad;
                                                         | su elección, con «ahora en B»
    D2   ... se retira                                       | en ningún equipo; «se retiró»
    D3   ... se forman de nuevo sin draft                    | los nuevos, y marcado quien cambió
    D4   nadie cambia, o la sala sigue abierta               | sin marcas
    D    terminada: nombre de todos los de los equipos, nadie disponible y el
         capitán de ahora (revisor y Agustín, 29 oct 2026)
    A    con la sala de draft abierta no se forman equipos    | DraftInProgressError
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
    RemoveEnrolledPlayerRequestDTO,
    WithdrawEnrollmentRequestDTO,
)
from src.modules.competition.application.dto.round_match_dto import (
    AssignTeamsRequestDTO,
    GenerateMatchesRequestDTO,
    MoverDeEquipoRequestDTO,
)
from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
)
from src.modules.competition.application.services.baja_de_la_competicion import (
    DraftInProgressError,
)
from src.modules.competition.application.services.equipos_que_cambian import (
    CaptainCannotMoveError,
    PlayersWithoutTeamError,
    TeamsLockedError,
    TeamsUnbalancedError,
)
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.competition.application.use_cases.get_draft_use_case import GetDraftUseCase
from src.modules.competition.application.use_cases.mover_de_equipo_use_case import (
    MoverDeEquipoUseCase,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    RemoveEnrolledPlayerUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.draft import Draft, DraftPick
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


class _Actividad:
    def __init__(self):
        self.llamadas = []

    def __getattr__(self, nombre):
        async def apunta(*args, **kwargs):
            self.llamadas.append((nombre, args))

        return apunta

    def de(self, nombre):
        return [args for n, args in self.llamadas if n == nombre]


class _E:
    """Una cerrada con 2 contra 2, capitanes, subcapitán en A, draft terminado y dos sobres."""

    async def montar(self, estado="CLOSED", draft=DraftStatus.COMPLETED):
        """Con `estado` ACTIVE se reabren las inscripciones tras montar; IN_PROGRESS, se empieza."""
        self.uow = InMemoryUnitOfWork()
        self.actividad = _Actividad()
        self.creador = UserId(uuid4())
        creada = await create_competition(self.uow, self.creador)
        self.comp_id = CompetitionId(creada.id)
        resto = [UserId(uuid4()) for _ in range(3)]
        for jugador in resto:
            await create_approved_enrollment(self.uow, creada.id, jugador)
        await set_competition_status(self.uow, creada.id, "CLOSED")
        todos = [self.creador, *resto]
        self.a, self.b = todos[:2], todos[2:]
        async with self.uow:
            competicion = await self.uow.competitions.find_by_id(self.comp_id)
            competicion.name_captains(self.a[0], self.b[0], todos, has_teams=False)
            competicion.name_vice_captain("A", self.a[1], self.a, has_teams=True)
            await self.uow.competitions.update(competicion)
            await self.uow.team_assignments.add(
                TeamAssignment.create(
                    competition_id=self.comp_id,
                    team_a_player_ids=self.a,
                    team_b_player_ids=self.b,
                    mode=TeamAssignmentMode.DRAFT,
                )
            )
            await self.uow.drafts.add(
                Draft(
                    id=DraftId.generate(),
                    competition_id=self.comp_id,
                    team_a_captain_id=self.a[0],
                    team_b_captain_id=self.b[0],
                    status=draft,
                )
            )
            self.ronda = Round.create(
                competition_id=self.comp_id,
                golf_course_id=GolfCourseId.generate(),
                round_date=date(2026, 12, 1),
                session_type=SessionType.MORNING,
                match_format=MatchFormat.SINGLES,
            )
            self.ronda.mark_teams_assigned()
            await self.uow.rounds.add(self.ronda)
            for equipo, jugadores in (("A", self.a), ("B", self.b)):
                sobre = Envelope.create(self.comp_id, self.ronda.id, equipo, MatchFormat.SINGLES)
                sobre.submit([[j] for j in jugadores], jugadores, jugadores[0], datetime.now(UTC))
                await self.uow.envelopes.add(sobre)
            await self.uow.commit()
        if estado == "ACTIVE":
            await self.reabrir()
        elif estado == "IN_PROGRESS":
            async with self.uow:
                competicion = await self.uow.competitions.find_by_id(self.comp_id)
                competicion.start()
                await self.uow.competitions.update(competicion)
        return self

    async def reabrir(self):
        async with self.uow:
            competicion = await self.uow.competitions.find_by_id(self.comp_id)
            competicion.reopen_enrollments()
            await self.uow.competitions.update(competicion)

    async def reparto(self):
        async with self.uow:
            r = await self.uow.team_assignments.find_by_competition(self.comp_id)
        return (list(r.team_a_player_ids), list(r.team_b_player_ids)) if r else None

    async def sobres_entregados(self):
        async with self.uow:
            return sorted(
                s.team
                for s in await self.uow.envelopes.find_by_round(self.ronda.id)
                if s.is_submitted()
            )

    async def competicion(self):
        async with self.uow:
            return await self.uow.competitions.find_by_id(self.comp_id)

    async def inscripcion(self, quien):
        async with self.uow:
            return await self.uow.enrollments.find_by_user_and_competition(quien, self.comp_id)

    async def con_un_partido(self):
        jugador = MatchPlayer.create(
            user_id=self.a[0],
            playing_handicap=10,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
            strokes_received=[],
        )
        rival = MatchPlayer.create(
            user_id=self.b[0],
            playing_handicap=10,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
            strokes_received=[],
        )
        async with self.uow:
            await self.uow.matches.add(
                Match.create(
                    round_id=self.ronda.id,
                    match_number=1,
                    team_a_players=[jugador],
                    team_b_players=[rival],
                )
            )

    def avisados(self):
        return [set(args[1]) for args in self.actividad.de("teams_changed")]

    async def mover(self, quien, equipo, por=None, is_admin=False):
        return await MoverDeEquipoUseCase(self.uow, actividad=self.actividad).execute(
            MoverDeEquipoRequestDTO(
                competition_id=self.comp_id.value, user_id=quien.value, team=equipo
            ),
            por or self.creador,
            is_admin=is_admin,
        )


@pytest.fixture
async def e():
    return await _E().montar()


class TestT2Salir:
    async def test_quien_se_retira_sale_de_su_equipo_y_los_demas_se_quedan(self, e):
        inscripcion = await e.inscripcion(e.b[1])

        await WithdrawEnrollmentUseCase(e.uow, actividad=e.actividad).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[1]
        )

        assert await e.reparto() == (e.a, [e.b[0]])

    async def test_t7_la_sala_las_sesiones_y_los_capitanes_se_quedan(self, e):
        inscripcion = await e.inscripcion(e.b[1])

        await WithdrawEnrollmentUseCase(e.uow, actividad=e.actividad).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[1]
        )

        async with e.uow:
            assert await e.uow.drafts.find_by_competition(e.comp_id) is not None
            ronda = await e.uow.rounds.find_by_id(e.ronda.id)
        assert ronda.status == RoundStatus.PENDING_MATCHES
        competicion = await e.competicion()
        assert competicion.ryder_cup.team_a_vice_captain_id == e.a[1]

    async def test_t4_los_dos_sobres_a_borrador_y_aviso_a_los_dos_capitanes(self, e):
        inscripcion = await e.inscripcion(e.b[1])

        await WithdrawEnrollmentUseCase(e.uow, actividad=e.actividad).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[1]
        )

        assert await e.sobres_entregados() == []
        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_si_le_quita_el_organizador_igual(self, e):
        inscripcion = await e.inscripcion(e.b[1])

        await RemoveEnrolledPlayerUseCase(e.uow, actividad=e.actividad).execute(
            RemoveEnrolledPlayerRequestDTO(enrollment_id=inscripcion.id.value), e.creador
        )

        assert await e.reparto() == (e.a, [e.b[0]])
        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_si_era_subcapitan_el_puesto_queda_vacio(self, e):
        inscripcion = await e.inscripcion(e.a[1])

        await WithdrawEnrollmentUseCase(e.uow, actividad=e.actividad).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.a[1]
        )

        competicion = await e.competicion()
        assert competicion.ryder_cup.team_a_vice_captain_id is None
        assert await e.reparto() == ([e.a[0]], e.b)

    async def test_con_partidos_el_reparto_no_se_toca(self, e):
        await e.con_un_partido()
        inscripcion = await e.inscripcion(e.b[1])

        await WithdrawEnrollmentUseCase(e.uow, actividad=e.actividad).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[1]
        )

        assert await e.reparto() == (e.a, e.b)
        assert e.avisados() == []


class TestT1Entrar:
    async def test_quien_entra_queda_sin_equipo_y_el_reparto_igual(self, e):
        await e.reabrir()
        nuevo = UserId(uuid4())

        await DirectEnrollPlayerUseCase(e.uow, USUARIOS_CON_GENERO, actividad=e.actividad).execute(
            DirectEnrollPlayerRequestDTO(competition_id=e.comp_id.value, user_id=nuevo.value),
            e.creador,
        )

        assert await e.reparto() == (e.a, e.b)
        assert await e.sobres_entregados() == []
        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_t6_con_la_sala_de_draft_abierta_no_entra_nadie(self):
        e = await _E().montar(estado="ACTIVE", draft=DraftStatus.IN_PROGRESS)

        with pytest.raises(DraftInProgressError):
            await DirectEnrollPlayerUseCase(e.uow, USUARIOS_CON_GENERO).execute(
                DirectEnrollPlayerRequestDTO(competition_id=e.comp_id.value, user_id=uuid4()),
                e.creador,
            )


class TestT3Mover:
    async def test_el_organizador_mueve_a_uno_de_a_a_b(self, e):
        await e.mover(e.a[1], "B")

        assert await e.reparto() == ([e.a[0]], [*e.b, e.a[1]])
        assert await e.sobres_entregados() == []
        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_mover_a_un_subcapitan_le_quita_el_puesto(self, e):
        await e.mover(e.a[1], "B")

        competicion = await e.competicion()
        assert competicion.ryder_cup.team_a_vice_captain_id is None

    async def test_poner_a_uno_sin_equipo(self, e):
        nuevo = UserId(uuid4())
        await create_approved_enrollment(e.uow, e.comp_id.value, nuevo)

        await e.mover(nuevo, "A")

        assert await e.reparto() == ([*e.a, nuevo], e.b)

    async def test_a_un_capitan_no(self, e):
        with pytest.raises(CaptainCannotMoveError):
            await e.mover(e.a[0], "B")

    async def test_al_mismo_equipo_no_cambia_nada(self, e):
        await e.mover(e.a[1], "A")

        assert await e.reparto() == (e.a, e.b)
        assert await e.sobres_entregados() == ["A", "B"]
        assert e.avisados() == []

    async def test_con_partidos_no(self, e):
        await e.con_un_partido()

        with pytest.raises(TeamsLockedError):
            await e.mover(e.a[1], "B")

    async def test_a_quien_no_esta_inscrito_no(self, e):
        with pytest.raises(TeamsLockedError):
            await e.mover(UserId(uuid4()), "B")

    async def test_a_quien_se_retiro_no(self, e):
        inscripcion = await e.inscripcion(e.b[1])
        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[1]
        )

        with pytest.raises(TeamsLockedError):
            await e.mover(e.b[1], "A")

    async def test_sin_ser_organizador_no(self, e):
        with pytest.raises(NotCompetitionCreatorError):
            await e.mover(e.a[1], "B", por=e.b[1])

    async def test_un_admin_si(self, e):
        await e.mover(e.a[1], "B", por=UserId(uuid4()), is_admin=True)

        assert await e.reparto() == ([e.a[0]], [*e.b, e.a[1]])

    async def test_empezada_no(self):
        e = await _E().montar(estado="IN_PROGRESS")

        with pytest.raises(TeamsLockedError):
            await e.mover(e.a[1], "B")

    async def test_con_la_sala_de_draft_abierta_no(self):
        e = await _E().montar(draft=DraftStatus.IN_PROGRESS)

        with pytest.raises(DraftInProgressError):
            await e.mover(e.a[1], "B")


class TestT5Generar:
    async def _generar(self, e):
        await GenerateMatchesUseCase(e.uow, AsyncMock(), AsyncMock()).execute(
            GenerateMatchesRequestDTO(round_id=e.ronda.id.value), e.creador
        )

    async def test_con_alguien_sin_equipo_no(self, e):
        await create_approved_enrollment(e.uow, e.comp_id.value, UserId(uuid4()))

        with pytest.raises(PlayersWithoutTeamError):
            await self._generar(e)

    async def test_con_dos_de_diferencia_no(self, e):
        await e.mover(e.b[1], "A")
        # 3 contra 1
        with pytest.raises(TeamsUnbalancedError):
            await self._generar(e)

    async def test_con_uno_de_diferencia_tampoco(self, e):
        """A = B, como dice la tabla aprobada (revisor, 28 oct 2026)."""
        inscripcion = await e.inscripcion(e.b[1])
        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[1]
        )
        # 2 contra 1
        with pytest.raises(TeamsUnbalancedError):
            await self._generar(e)

    async def test_con_partidos_en_otra_sesion_no_se_exige_nada(self, e):
        """
        Revisor: con partidos ya no se puede mover a nadie; exigir aquí bloqueaba
        la siguiente sesión para siempre. Como antes: quien no tiene equipo no juega.
        """
        await e.con_un_partido()
        await create_approved_enrollment(e.uow, e.comp_id.value, UserId(uuid4()))
        try:
            await self._generar(e)
        except (PlayersWithoutTeamError, TeamsUnbalancedError):
            pytest.fail("Con partidos ya no se exigen los equipos completos")
        except Exception:
            pass

    async def test_se_cuentan_solo_los_inscritos(self, e):
        """Revisor: el reparto puede guardar a quien se retiró con partidos."""
        async with e.uow:
            reparto = await e.uow.team_assignments.find_by_competition(e.comp_id)
            reparto.poner(UserId(uuid4()), "A")
            await e.uow.team_assignments.update(reparto)
        try:
            await self._generar(e)
        except (PlayersWithoutTeamError, TeamsUnbalancedError):
            pytest.fail("Un id que ya no está inscrito no cuenta")
        except Exception:
            pass


class _Usuario:
    def __init__(self, user_id):
        self.id = user_id
        self.handicap = None

    def display_name_or_legal(self, nombre_legal):
        return f"N-{self.id.value}"


class _ConNombres:
    """Cada usuario se llama `N-<su id>`; sin hándicap, como un recién llegado."""

    async def find_by_ids(self, user_ids):
        return [_Usuario(u) for u in user_ids]

    async def find_by_id(self, user_id):
        return None


class _SinUsuarios:
    """Nadie en el repositorio de usuarios: los nombres salen vacíos."""

    async def find_by_ids(self, user_ids):
        return []

    async def find_by_id(self, user_id):
        return None


class TestA1VolverAFormarlos:
    """Volver a formar los equipos (AssignTeams) es otro cambio de equipos (29 oct 2026)."""

    async def _formar(self, e, a, b):
        return await AssignTeamsUseCase(e.uow, _SinUsuarios(), actividad=e.actividad).execute(
            AssignTeamsRequestDTO(
                competition_id=e.comp_id.value,
                mode="MANUAL",
                team_a_player_ids=[u.value for u in a],
                team_b_player_ids=[u.value for u in b],
            ),
            e.creador,
        )

    async def _sobres(self, e):
        async with e.uow:
            return {s.team: s for s in await e.uow.envelopes.find_by_round(e.ronda.id)}

    async def test_a1_los_sobres_a_borrador_y_aviso_a_los_dos_capitanes(self, e):
        await self._formar(e, [e.a[0], e.b[1]], [e.b[0], e.a[1]])

        assert await e.sobres_entregados() == []
        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_a1_tambien_el_sobre_ya_revelado(self, e):
        async with e.uow:
            sobre = (await self._sobres(e))["A"]
            sobre.reveal()
            await e.uow.envelopes.update(sobre)

        await self._formar(e, [e.a[0], e.b[1]], [e.b[0], e.a[1]])

        sobres = await self._sobres(e)
        assert sobres["A"].entries == ()
        assert sobres["A"].is_submitted() is False
        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_a1_tambien_en_automatico(self, e):
        await AssignTeamsUseCase(e.uow, _SinUsuarios(), actividad=e.actividad).execute(
            AssignTeamsRequestDTO(competition_id=e.comp_id.value, mode="AUTOMATIC"), e.creador
        )

        assert await e.sobres_entregados() == []
        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_con_la_sala_de_draft_abierta_no_se_forman(self):
        """Revisor (29 oct 2026): al terminar, el draft pisaba esos equipos sin avisar."""
        e = await _E().montar(draft=DraftStatus.IN_PROGRESS)

        with pytest.raises(DraftInProgressError):
            await self._formar(e, [e.a[0], e.b[1]], [e.b[0], e.a[1]])
        assert await e.reparto() == (e.a, e.b)

    async def test_a2_la_primera_vez_ni_se_reabre_ni_se_avisa(self, e):
        async with e.uow:
            reparto = await e.uow.team_assignments.find_by_competition(e.comp_id)
            await e.uow.team_assignments.delete(reparto.id)

        await self._formar(e, e.a, e.b)

        assert await e.sobres_entregados() == ["A", "B"]
        assert e.avisados() == []

    async def test_a3_sin_sobres_entregados_se_avisa_igual(self, e):
        async with e.uow:
            for sobre in (await self._sobres(e)).values():
                sobre.reabrir()
                await e.uow.envelopes.update(sobre)

        await self._formar(e, [e.a[0], e.b[1]], [e.b[0], e.a[1]])

        assert e.avisados() == [{e.a[0], e.b[0]}]

    async def test_a4_con_partidos_ni_se_reabre_ni_se_avisa(self, e):
        await e.con_un_partido()

        await self._formar(e, [e.a[0], e.b[1]], [e.b[0], e.a[1]])

        assert await e.sobres_entregados() == ["A", "B"]
        assert e.avisados() == []


class TestDSalaCompletada:
    """La sala terminada enseña los equipos de verdad y marca quién cambió (29 oct 2026)."""

    async def _con_elecciones(self, e):
        """El draft de `e`, con a[1] elegido por A y b[1] por B."""
        async with e.uow:
            sala = await e.uow.drafts.find_by_competition(e.comp_id)
            await e.uow.drafts.update(
                Draft(
                    id=sala.id,
                    competition_id=e.comp_id,
                    team_a_captain_id=e.a[0],
                    team_b_captain_id=e.b[0],
                    status=sala.status,
                    picks=(DraftPick(e.a[1], "A", 1), DraftPick(e.b[1], "B", 2)),
                )
            )
            await e.uow.commit()

    async def _sala(self, e):
        sala = await GetDraftUseCase(e.uow, _SinUsuarios()).execute(e.comp_id.value, e.creador)
        ahora = {p.user_id: p.now_in_team for p in sala.picks}
        return sala, ahora

    async def test_d1_quien_cambia_de_equipo_sale_en_el_nuevo_y_marcado(self, e):
        await self._con_elecciones(e)
        await e.mover(e.a[1], "B")

        sala, ahora = await self._sala(e)

        assert sala.team_a == [e.a[0].value]
        assert set(sala.team_b) == {e.b[0].value, e.b[1].value, e.a[1].value}
        assert ahora[e.a[1].value] == "B"
        # La elección se queda como fue
        assert [(p.user_id, p.team) for p in sala.picks] == [
            (e.a[1].value, "A"),
            (e.b[1].value, "B"),
        ]

    async def test_d2_quien_se_retira_no_sale_en_ningun_equipo(self, e):
        await self._con_elecciones(e)
        inscripcion = await e.inscripcion(e.b[1])
        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[1]
        )

        sala, ahora = await self._sala(e)

        assert e.b[1].value not in sala.team_a + sala.team_b
        assert ahora[e.b[1].value] is None

    async def test_d3_formados_de_nuevo_sin_draft_se_ven_los_nuevos(self, e):
        await self._con_elecciones(e)
        await TestA1VolverAFormarlos()._formar(e, [e.a[0], e.b[1]], [e.b[0], e.a[1]])

        sala, ahora = await self._sala(e)

        assert set(sala.team_a) == {e.a[0].value, e.b[1].value}
        assert set(sala.team_b) == {e.b[0].value, e.a[1].value}
        assert ahora == {e.a[1].value: "B", e.b[1].value: "A"}

    async def test_d4_sin_cambios_cada_uno_donde_le_eligieron(self, e):
        await self._con_elecciones(e)

        sala, ahora = await self._sala(e)

        assert sala.team_a == [e.a[0].value, e.a[1].value]
        assert sala.team_b == [e.b[0].value, e.b[1].value]
        assert ahora == {e.a[1].value: "A", e.b[1].value: "B"}

    async def test_d4_en_curso_sin_marcas_y_los_equipos_del_draft(self):
        """Mientras se elige mandan las elecciones, aunque haya un reparto guardado."""
        e = await _E().montar(draft=DraftStatus.IN_PROGRESS)
        await self._con_elecciones(e)
        async with e.uow:
            reparto = await e.uow.team_assignments.find_by_competition(e.comp_id)
            reparto.quitar(e.a[1])
            await e.uow.team_assignments.update(reparto)

        sala, ahora = await self._sala(e)

        assert sala.team_a == [e.a[0].value, e.a[1].value]
        assert ahora == {e.a[1].value: "A", e.b[1].value: "B"}

    async def test_revisor_quien_no_eligieron_tambien_lleva_nombre(self, e):
        """Revisor: quien entró tras el draft y está en un equipo no salía en ninguna elección."""
        await self._con_elecciones(e)
        nuevo = UserId(uuid4())
        await create_approved_enrollment(e.uow, e.comp_id.value, nuevo)
        await e.mover(nuevo, "B")

        sala = await GetDraftUseCase(e.uow, _ConNombres()).execute(e.comp_id.value, e.creador)

        assert {**sala.team_names} == {
            u.value: f"N-{u.value}" for u in (e.a[0], e.a[1], e.b[0], e.b[1], nuevo)
        }

    async def test_revisor_terminada_nadie_disponible(self, e):
        """Revisor: quien entró después salía disponible y en un equipo a la vez."""
        await self._con_elecciones(e)
        nuevo = UserId(uuid4())
        await create_approved_enrollment(e.uow, e.comp_id.value, nuevo)
        await e.mover(nuevo, "B")

        sala, _ = await self._sala(e)

        assert sala.available_players == []

    async def test_el_capitan_de_ahora(self, e):
        """Se retira el capitán de B y sube su subcapitán: la sala dice el de ahora (29 oct 2026)."""
        await self._con_elecciones(e)
        async with e.uow:
            competicion = await e.uow.competitions.find_by_id(e.comp_id)
            competicion.name_vice_captain("B", e.b[1], e.b, has_teams=True)
            await e.uow.competitions.update(competicion)
        inscripcion = await e.inscripcion(e.b[0])
        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), e.b[0]
        )

        sala = await GetDraftUseCase(e.uow, _ConNombres()).execute(e.comp_id.value, e.creador)

        assert sala.team_b_captain_id == e.b[1].value
        assert sala.team_b_captain_name == f"N-{e.b[1].value}"
        assert sala.team_a_captain_id == e.a[0].value

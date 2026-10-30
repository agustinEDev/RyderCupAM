"""
Los capitanes después del draft (BE #320, decidido el 22 sep).

Cada capitán elige a su subcapitán entre los de su equipo, y el organizador
también puede, por si un capitán no usa la app. Si un capitán se va, asciende
su subcapitán; si no lo había, el organizador cubre el puesto con alguien de
ese equipo. Así una baja nunca deja la competición atascada.

Desde la release social 2 (27 oct 2026), sin partidos generados la baja deshace
los equipos: entonces no hay equipo donde cubrir, y los capitanes se vuelven a
nombrar. Cubrir el puesto queda para cuando ya hay partidos (`con_partidos`).

Desde el 29 oct 2026, con los equipos formados el jugador no se retira solo: le
quita el organizador, y solo sin partidos (`quitar`). Una baja con partidos o en
juego ya no se da, pero puede estar en la base de antes (`baja_de_antes`), y
cubrir el puesto sigue sirviendo para ella.
"""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    FillCaptainRequestDTO,
    NameCaptainsRequestDTO,
    NameViceCaptainRequestDTO,
)
from src.modules.competition.application.dto.enrollment_dto import (
    RemoveEnrolledPlayerRequestDTO,
)
from src.modules.competition.application.dto.round_match_dto import AssignTeamsRequestDTO
from src.modules.competition.application.exceptions import NotCompetitionCreatorError
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
)
from src.modules.competition.application.use_cases.fill_captain_use_case import (
    FillCaptainUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.name_vice_captain_use_case import (
    NameViceCaptainUseCase,
    NotCaptainOrCreatorError,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    RemoveEnrolledPlayerUseCase,
)
from src.modules.competition.domain.entities.competition import (
    TeamsNotAssignedError,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.ryder_cup_setup import (
    CaptainOnWrongTeamError,
)
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
)
from tests.unit.modules.competition.application.use_cases.test_deshacer_equipos import _jugador

pytestmark = pytest.mark.asyncio


class Torneo:
    """Seis inscritos, Ana y Bea capitanas y, si se pide, los equipos repartidos."""

    def __init__(self):
        """Los jugadores del torneo, todavía sin montar."""
        self.uow = InMemoryUnitOfWork()
        self.organizador = UserId(uuid4())
        self.ana, self.bea = UserId(uuid4()), UserId(uuid4())
        self.otros = [UserId(uuid4()) for _ in range(3)]
        self.inscripciones = {}

    async def montar(self, repartir: bool = True) -> "Torneo":
        """Crea la competición, inscribe a todos, nombra a Ana y Bea y, si se pide, reparte."""
        creada = await create_competition(self.uow, self.organizador)
        self.comp_id = CompetitionId(creada.id)
        for jugador in (self.ana, self.bea, *self.otros):
            self.inscripciones[jugador] = await create_approved_enrollment(
                self.uow, creada.id, jugador
            )
        await NameCaptainsUseCase(self.uow).execute(
            NameCaptainsRequestDTO(
                competition_id=creada.id,
                team_a_captain_id=self.ana.value,
                team_b_captain_id=self.bea.value,
            ),
            self.organizador,
        )
        if repartir:
            await self.repartir()
        return self

    async def repartir(self):
        """Reparto automático; guarda cómo quedaron los dos equipos."""
        usuarios = AsyncMock()
        usuarios.find_by_id = AsyncMock(return_value=None)
        reparto = await AssignTeamsUseCase(self.uow, usuarios).execute(
            AssignTeamsRequestDTO(competition_id=self.comp_id.value, mode="AUTOMATIC"),
            self.organizador,
        )
        self.equipo_a = [UserId(u) for u in reparto.team_a_player_ids]
        self.equipo_b = [UserId(u) for u in reparto.team_b_player_ids]

    def de_a(self) -> UserId:
        """Un jugador corriente del equipo A: ni la capitana ni el organizador."""
        return next(j for j in self.equipo_a if j in self.otros)

    def de_b(self) -> UserId:
        """Un jugador corriente del equipo B: ni la capitana ni el organizador."""
        return next(j for j in self.equipo_b if j in self.otros)

    async def subcapitan(self, equipo: str, jugador: UserId, quien: UserId, admin=False):
        """Pide el subcapitán de ese equipo en nombre de `quien`."""
        return await NameViceCaptainUseCase(self.uow).execute(
            NameViceCaptainRequestDTO(
                competition_id=self.comp_id.value, team=equipo, player_id=jugador.value
            ),
            quien,
            is_admin=admin,
        )

    async def cubrir(self, equipo: str, jugador: UserId, quien: UserId, admin=False):
        """Pide cubrir el puesto de capitán de ese equipo en nombre de `quien`."""
        return await FillCaptainUseCase(self.uow).execute(
            FillCaptainRequestDTO(
                competition_id=self.comp_id.value, team=equipo, player_id=jugador.value
            ),
            quien,
            is_admin=admin,
        )

    async def quitar(self, jugador: UserId):
        """El organizador le quita: con equipos formados, el único camino (29 oct 2026)."""
        await RemoveEnrolledPlayerUseCase(self.uow).execute(
            RemoveEnrolledPlayerRequestDTO(enrollment_id=self.inscripciones[jugador].id.value),
            self.organizador,
        )

    async def baja_de_antes(self, jugador: UserId):
        """
        Una baja con partidos o en juego, de antes del 29 oct 2026: ya no se da,
        pero puede estar en la base. Lo que hacía la retirada con la capitanía.
        """
        async with self.uow:
            inscripcion = await self.uow.enrollments.find_by_id(self.inscripciones[jugador].id)
            inscripcion.withdraw()
            await self.uow.enrollments.update(inscripcion)
            competicion = await self.uow.competitions.find_by_id(self.comp_id)
            competicion.handle_withdrawal(jugador)
            await self.uow.competitions.update(competicion)
            await self.uow.commit()

    async def con_partidos(self) -> "Torneo":
        """
        Con un partido ya generado: los equipos ya no se deshacen cuando alguien
        se va (release social 2), y el puesto de capitán se cubre dentro del equipo.
        """
        async with self.uow:
            sesion = Round.create(
                competition_id=self.comp_id,
                golf_course_id=GolfCourseId.generate(),
                round_date=date(2026, 12, 1),
                session_type=SessionType.MORNING,
                match_format=MatchFormat.SINGLES,
            )
            sesion.mark_teams_assigned()
            await self.uow.rounds.add(sesion)
            await self.uow.matches.add(
                Match.create(
                    round_id=sesion.id,
                    match_number=1,
                    team_a_players=[_jugador(self.equipo_a[0])],
                    team_b_players=[_jugador(self.equipo_b[0])],
                )
            )
            sesion.mark_matches_generated()
            await self.uow.rounds.update(sesion)
            await self.uow.commit()
        return self

    async def competicion(self):
        """La competición tal como quedó guardada."""
        async with self.uow:
            return await self.uow.competitions.find_by_id(self.comp_id)


# ------------------------------------------------------------------ subcapitán


async def test_la_capitana_elige_a_su_subcapitan():
    """
    Given: equipos repartidos
    When: Ana elige a un jugador de su equipo
    Then: queda guardado y la respuesta lo trae
    """
    t = await Torneo().montar()

    respuesta = await t.subcapitan("A", t.de_a(), t.ana)

    assert (await t.competicion()).ryder_cup.team_a_vice_captain_id == t.de_a()
    assert respuesta.team_a_vice_captain_id == t.de_a().value


@pytest.mark.parametrize("quien", ["organizador", "admin"])
async def test_el_organizador_o_un_admin_tambien_pueden(quien):
    """Por si un capitán no usa la app."""
    t = await Torneo().montar()
    persona = t.organizador if quien == "organizador" else UserId(uuid4())

    await t.subcapitan("B", t.de_b(), persona, admin=quien == "admin")

    assert (await t.competicion()).ryder_cup.team_b_vice_captain_id == t.de_b()


@pytest.mark.parametrize("quien", ["la otra capitana", "un jugador"])
async def test_nadie_mas_puede_elegirlo(quien):
    """
    Given: equipos repartidos
    When: la otra capitana o un jugador corriente eligen el subcapitán del A
    Then: se rechaza y no se guarda nada
    """
    t = await Torneo().montar()
    persona = t.bea if quien == "la otra capitana" else t.de_a()

    with pytest.raises(NotCaptainOrCreatorError):
        await t.subcapitan("A", t.de_a(), persona)

    assert (await t.competicion()).ryder_cup.team_a_vice_captain_id is None


async def test_tiene_que_ser_de_su_equipo():
    """
    Given: equipos repartidos
    When: Ana elige a alguien del equipo B
    Then: se rechaza
    """
    t = await Torneo().montar()

    with pytest.raises(CaptainOnWrongTeamError):
        await t.subcapitan("A", t.de_b(), t.ana)


async def test_quien_se_retiro_ya_no_cuenta_como_de_su_equipo():
    """Con partidos, el reparto guarda la lista tal cual; la baja no la toca."""
    t = await (await Torneo().montar()).con_partidos()
    se_va = t.de_a()
    await t.baja_de_antes(se_va)

    with pytest.raises(CaptainOnWrongTeamError):
        await t.subcapitan("A", se_va, t.ana)


async def test_antes_del_draft_no_hay_subcapitan():
    """
    Given: capitanes nombrados sin equipos
    When: Ana elige subcapitán
    Then: se rechaza: todavía no hay equipo del que elegir
    """
    t = await Torneo().montar(repartir=False)
    alguien = t.otros[0]

    with pytest.raises(TeamsNotAssignedError):
        await t.subcapitan("A", alguien, t.ana)


# ------------------------------------------------------ bajas y puesto vacío


async def test_si_se_va_la_capitana_asciende_su_subcapitan():
    """
    Given: Ana con subcapitán
    When: el organizador la quita (y los equipos se reinician)
    Then: el subcapitán pasa a capitán y su puesto queda libre
    """
    t = await Torneo().montar()
    segundo = t.de_a()
    await t.subcapitan("A", segundo, t.ana)

    await t.quitar(t.ana)

    competicion = await t.competicion()
    assert (
        competicion.ryder_cup.team_a_captain_id,
        competicion.ryder_cup.team_a_vice_captain_id,
    ) == (segundo, None)


async def test_sin_subcapitan_el_organizador_cubre_el_puesto():
    """
    Given: Ana se va sin subcapitán
    When: el organizador pone a un jugador del equipo A
    Then: queda de capitán y la respuesta lo trae
    """
    t = await (await Torneo().montar()).con_partidos()
    await t.baja_de_antes(t.ana)
    nuevo = t.de_a()

    respuesta = await t.cubrir("A", nuevo, t.organizador)

    assert (await t.competicion()).ryder_cup.team_a_captain_id == nuevo
    assert respuesta.team_a_captain_id == nuevo.value


async def test_cubrir_el_puesto_es_cosa_del_organizador():
    """
    Given: Ana se va sin subcapitán
    When: Bea intenta cubrir el puesto
    Then: se rechaza
    """
    t = await (await Torneo().montar()).con_partidos()
    await t.baja_de_antes(t.ana)

    with pytest.raises(NotCompetitionCreatorError):
        await t.cubrir("A", t.de_a(), t.bea)


async def test_quitar_a_alguien_deja_libres_los_subcapitanes():
    """
    Given: Ana con subcapitán
    When: el organizador quita a alguien y se vuelven a repartir los equipos
    Then: el puesto de subcapitán queda libre (con equipos formados, repartir
        otra vez sin reiniciar ya no se deja: 29 oct 2026)
    """
    t = await Torneo().montar()
    await t.subcapitan("A", t.de_a(), t.ana)

    await t.quitar(t.de_b())

    assert (await t.competicion()).ryder_cup.team_a_vice_captain_id is None


@pytest.mark.parametrize("accion", ["subcapitan", "cubrir"])
async def test_bloquean_la_fila_de_la_competicion(accion):
    """Como al nombrar capitanes y al repartir: si no, se pisan entre sí."""
    t = await (await Torneo().montar()).con_partidos()
    if accion == "cubrir":
        await t.baja_de_antes(t.ana)
    llamadas = []
    original = t.uow.competitions.find_by_id_for_update

    async def espia(competition_id):
        """Anota con qué competición se pidió el bloqueo y deja hacer al original."""
        llamadas.append(competition_id)
        return await original(competition_id)

    t.uow.competitions.find_by_id_for_update = espia

    if accion == "subcapitan":
        await t.subcapitan("A", t.de_a(), t.ana)
    else:
        await t.cubrir("A", t.de_a(), t.organizador)

    assert llamadas == [t.comp_id]


async def test_sin_partidos_la_baja_de_la_capitana_deshace_los_equipos_y_se_renombra():
    """
    Release social 2 (decidido el 27 oct 2026): sin partidos, quien se va de un
    equipo formado deshace los equipos. La capitana se va sin subcapitán: ya no
    hay equipo donde cubrir el puesto, se nombran los capitanes como al principio.
    """
    t = await Torneo().montar()
    await t.quitar(t.ana)

    with pytest.raises(TeamsNotAssignedError):
        await t.subcapitan("B", t.otros[0], t.bea)
    nueva = t.otros[0]
    await NameCaptainsUseCase(t.uow).execute(
        NameCaptainsRequestDTO(
            competition_id=t.comp_id.value,
            team_a_captain_id=nueva.value,
            team_b_captain_id=t.bea.value,
        ),
        t.organizador,
    )

    assert (await t.competicion()).ryder_cup.team_a_captain_id == nueva


async def test_un_capitan_que_se_fue_en_pleno_torneo_se_puede_sustituir_al_revertir():
    """En juego la baja no toca a los capitanes; al volver a CLOSED, se cubre el puesto."""
    t = await Torneo().montar()
    async with t.uow:
        competicion = await t.uow.competitions.find_by_id(t.comp_id)
        competicion.start()
        await t.uow.competitions.update(competicion)
        await t.uow.commit()
    await t.baja_de_antes(t.ana)
    async with t.uow:
        competicion = await t.uow.competitions.find_by_id(t.comp_id)
        assert competicion.ryder_cup.team_a_captain_id == t.ana
        competicion.revert_to_closed()
        await t.uow.competitions.update(competicion)
        await t.uow.commit()
    nuevo = t.de_a()

    await t.cubrir("A", nuevo, t.organizador)

    assert (await t.competicion()).ryder_cup.team_a_captain_id == nuevo

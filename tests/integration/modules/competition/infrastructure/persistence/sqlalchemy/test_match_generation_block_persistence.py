"""
Lo que BE #361 necesita de PostgreSQL y un test en memoria no ve.

- El motivo por el que una sesión no tiene partidos viaja como JSONB: se
  comprueba que vuelve entero, con nombres y colores.
- Abrir los sobres y crear los partidos van en la MISMA transacción, y si los
  partidos fallan a mitad solo se deshace lo suyo: eso es un SAVEPOINT de
  verdad, y aquí se comprueba contra la base de datos. Incluido lo que la mesa
  de sobres da por hecho: que tras deshacerlo, volver a leer la ronda devuelve
  la de antes y no la que quedó a medias en memoria.
"""

from datetime import datetime

import pytest

from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_GENDER,
    MISSING_TEE_COLOR,
    PLAYERS_WITHOUT_TEE,
    BlockedPlayer,
    MatchGenerationBlock,
)
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.round_repository import (
    SQLAlchemyRoundRepository,
)

# `jugadores` y `ronda` vienen del conftest de este directorio: son los mismos
# que usa el repositorio de sobres

pytestmark = [pytest.mark.integration]

CUANDO = datetime(2026, 6, 1, 0, 0, 5)


class TestElMotivoSeGuarda:
    async def test_vuelve_entero_de_la_base_de_datos(self, db_session, ronda, jugadores):
        """
        Given: una sesión que espera partidos y no los pudo tener
        When: se guarda el motivo y se vuelve a leer
        Then: vuelve el motivo, con cada jugador, su nombre, lo que le falta y el color
        """
        repo = SQLAlchemyRoundRepository(db_session)
        ronda.mark_teams_assigned()
        ronda.block_match_generation(
            MatchGenerationBlock(
                reason=PLAYERS_WITHOUT_TEE,
                players=(
                    BlockedPlayer(jugadores[1], "Bea Dos", MISSING_GENDER),
                    BlockedPlayer(jugadores[2], "Carla Tres", MISSING_TEE_COLOR, "WHITE"),
                ),
                at=CUANDO,
            )
        )
        await repo.update(ronda)
        await db_session.commit()
        db_session.expunge_all()

        leida = await repo.find_by_id(ronda.id)

        assert leida.match_generation_block == MatchGenerationBlock(
            reason=PLAYERS_WITHOUT_TEE,
            players=(
                BlockedPlayer(jugadores[1], "Bea Dos", MISSING_GENDER),
                BlockedPlayer(jugadores[2], "Carla Tres", MISSING_TEE_COLOR, "WHITE"),
            ),
            at=CUANDO,
        )

    async def test_sin_motivo_vuelve_none(self, db_session, ronda):
        db_session.expunge_all()

        leida = await SQLAlchemyRoundRepository(db_session).find_by_id(ronda.id)

        assert leida.match_generation_block is None


class TestElSavepoint:
    async def test_deshace_lo_de_dentro_y_deja_lo_de_antes(self, db_session, ronda, jugadores):
        """
        Given: un sobre abierto ANTES del savepoint
        When: dentro se escribe otro y algo revienta
        Then: tras el commit, el de antes está y el de dentro no
        """
        uow = SQLAlchemyCompetitionUnitOfWork(db_session)
        antes = Envelope.create(
            competition_id=ronda.competition_id,
            round_id=ronda.id,
            team="A",
            match_format=MatchFormat.FOURBALL,
        )
        await uow.envelopes.add(antes)

        with pytest.raises(RuntimeError):
            async with uow.savepoint():
                dentro = Envelope.create(
                    competition_id=ronda.competition_id,
                    round_id=ronda.id,
                    team="B",
                    match_format=MatchFormat.FOURBALL,
                )
                await uow.envelopes.add(dentro)
                await uow.flush()
                raise RuntimeError("revienta a mitad")

        await uow.commit()
        db_session.expunge_all()

        equipos = {s.team for s in await uow.envelopes.find_by_round(ronda.id)}
        assert equipos == {"A"}

    async def test_apuntar_el_motivo_tras_deshacer_como_la_mesa_de_sobres(self, db_session, ronda):
        """
        El camino de `EnvelopeDesk.generar_los_partidos` cuando falla a mitad.

        Tras deshacer un SAVEPOINT, SQLAlchemy caduca lo que se tocó dentro, y
        leer un atributo caducado es una carga SÍNCRONA: en asíncrono revienta
        con MissingGreenlet. Pasaba con `ronda.id`: el id se guarda antes, y la
        ronda se vuelve a pedir con él, que la recarga por el camino asíncrono.

        Given: una ronda que se marca dentro del savepoint y el savepoint revienta
        When: se vuelve a pedir con el id guardado antes, se apunta el motivo y se confirma
        Then: la ronda es la de antes, con el motivo, y nada de lo de dentro
        """
        uow = SQLAlchemyCompetitionUnitOfWork(db_session)
        a_medias = await uow.rounds.find_by_id(ronda.id)
        a_medias.mark_teams_assigned()
        await uow.rounds.update(a_medias)
        await uow.flush()
        round_id = a_medias.id

        with pytest.raises(RuntimeError):
            async with uow.savepoint():
                a_medias.block_match_generation(
                    MatchGenerationBlock(reason="UNEXPECTED", at=CUANDO)
                )
                await uow.rounds.update(a_medias)
                await uow.flush()
                raise RuntimeError("revienta a mitad")

        releida = await uow.rounds.find_by_id(round_id)
        assert releida.match_generation_block is None
        releida.block_match_generation(MatchGenerationBlock(reason=PLAYERS_WITHOUT_TEE, at=CUANDO))
        await uow.rounds.update(releida)
        await uow.commit()
        db_session.expunge_all()

        final = await uow.rounds.find_by_id(round_id)
        assert final.status == RoundStatus.PENDING_MATCHES
        assert final.match_generation_block.reason == PLAYERS_WITHOUT_TEE


class _SinZona:
    """Un campo sin zona horaria: su sesión no vence nunca sola."""

    async def for_competition(self, competition):
        return None

    async def for_course(self, golf_course_id):
        return None


class _GeneradorQueRevientaAMitad:
    """El peor caso: marca la sesión con partidos, lo escribe y revienta."""

    def __init__(self, uow):
        self._uow = uow

    async def generar_dentro(
        self, ronda, competition, manual_pairings=None, refrescar_handicap_rfeg=True
    ):
        ronda.mark_matches_generated()
        await self._uow.rounds.update(ronda)
        await self._uow.flush()
        raise RuntimeError("se cae a mitad de escribir los partidos")


class TestAbrirLosSobresContraPostgres:
    async def test_si_los_partidos_revientan_los_sobres_quedan_abiertos_y_el_motivo_apuntado(
        self, db_session, ronda, jugadores
    ):
        """
        El caso de uso entero con la Unit of Work de verdad.

        Given: una cerrada con capitanes, equipos y los dos sobres entregados
        When: se abren y la generación revienta DESPUÉS de marcar la sesión
        Then: responde sin MissingGreenlet, los sobres quedan abiertos, la
              sesión sigue esperando partidos y el motivo queda guardado
        """
        from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
            RevealEnvelopesUseCase,
        )
        from src.modules.competition.domain.entities.enrollment import Enrollment
        from src.modules.competition.domain.entities.team_assignment import TeamAssignment
        from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
        from src.modules.competition.domain.value_objects.team_assignment_mode import (
            TeamAssignmentMode,
        )

        uow = SQLAlchemyCompetitionUnitOfWork(db_session)
        equipo_a, equipo_b = jugadores[:2], jugadores[2:]
        competicion = await uow.competitions.find_by_id(ronda.competition_id)
        if competicion.is_draft():
            competicion.activate()
        competicion.name_captains(
            equipo_a[0], equipo_b[0], approved_player_ids=jugadores, has_teams=False
        )
        await uow.competitions.update(competicion)
        for uid in jugadores:
            await uow.enrollments.add(
                Enrollment.direct_enroll(
                    id=EnrollmentId.generate(), competition_id=competicion.id, user_id=uid
                )
            )
        await uow.team_assignments.add(
            TeamAssignment.create(
                competition_id=competicion.id,
                mode=TeamAssignmentMode.DRAFT,
                team_a_player_ids=equipo_a,
                team_b_player_ids=equipo_b,
            )
        )
        sesion = await uow.rounds.find_by_id(ronda.id)
        sesion.mark_teams_assigned()
        await uow.rounds.update(sesion)
        for team, equipo in (("A", equipo_a), ("B", equipo_b)):
            sobre = Envelope.create(
                competition_id=competicion.id,
                round_id=ronda.id,
                team=team,
                match_format=MatchFormat.FOURBALL,
            )
            sobre.submit([equipo], equipo=equipo, por=equipo[0], ahora=CUANDO)
            await uow.envelopes.add(sobre)
        await uow.commit()
        db_session.expunge_all()
        round_id = ronda.id

        # A mano solo abre el organizador en una sesión sin plazo (BE #374)
        respuesta = await RevealEnvelopesUseCase(
            uow, None, timezone_service=_SinZona(), generador=_GeneradorQueRevientaAMitad(uow)
        ).execute(round_id.value, competicion.creator_id)

        assert len(respuesta.matchups) == 1
        db_session.expunge_all()
        final = await uow.rounds.find_by_id(round_id)
        assert final.status == RoundStatus.PENDING_MATCHES
        assert final.match_generation_block.reason == "UNEXPECTED"
        assert all(not s.is_sealed() for s in await uow.envelopes.find_by_round(round_id))

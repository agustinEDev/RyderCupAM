"""
Tests de la partida rapida de un amigo vista en solo lectura (bloque K, 22 oct 2026).

La tabla aprobada por Agustin:

- K1: se ve la partida TERMINADA si quien mira es amigo de al menos uno de sus
  jugadores con cuenta, ese amigo publica su actividad, no hay bloqueo entre los
  dos y el amigo no la tiene en la papelera.
- K2: en curso no se ve.
- K3: se ve todo (tarjeta y clasificacion), sin poder tocar nada.
- K4: los nombres, como en Actividad: con quien haya un bloqueo o tenga la
  cuenta desactivada, «un jugador» (nombre nulo); los invitados, «un
  invitado» (nombre nulo).
- K5: sin acceso, 403.
- K6: los participantes, igual que siempre.
"""

from uuid import uuid4

import pytest

from src.modules.quick_match.application.dto.quick_match_dto import (
    QuickMatchDetailResponseDTO,
    SharedQuickMatchDetailResponseDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
    QuickMatchNotSharedError,
)
from src.modules.quick_match.application.use_cases.get_quick_match_use_case import (
    GetQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.get_shared_quick_match_use_case import (
    GetSharedQuickMatchUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.value_objects.scoring_format import ScoringFormat
from tests.unit.modules.quick_match.conftest import (
    create_accepted_friendship,
    create_golf_course,
    create_user,
    unique_email,
)

pytestmark = pytest.mark.asyncio


# ==================== Montaje ====================


async def _block(social_uow, blocker_id, blocked_id) -> None:
    async with social_uow:
        await social_uow.friendships.add(
            Friendship.create_blocked(
                id=FriendshipId.generate(), blocker_id=blocker_id, blocked_id=blocked_id
            )
        )


async def _save_user(user_uow, user) -> None:
    async with user_uow:
        await user_uow.users.save(user)


class _Escena:
    """Una partida stableford de Ana (creadora), Bea, Carlos y un invitado."""

    def __init__(self, qm_uow, user_uow, social_uow, golf_course_uow):
        self.qm_uow = qm_uow
        self.user_uow = user_uow
        self.social_uow = social_uow
        self.golf_course_uow = golf_course_uow

    async def montar(self, *, completar: bool = True, iniciar: bool = True) -> "_Escena":
        self.ana = await create_user(self.user_uow, unique_email("ana"))
        self.bea = await create_user(self.user_uow, unique_email("bea"))
        self.carlos = await create_user(self.user_uow, unique_email("carlos"))
        self.viewer = await create_user(self.user_uow, unique_email("viewer"))
        course = await create_golf_course(self.golf_course_uow, self.ana.id)

        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=self.ana.id,
            golf_course_id=course.id,
            scoring_format=ScoringFormat.STABLEFORD,
        )
        qm.add_participant(QuickMatchParticipant.for_user(self.bea.id))
        qm.add_participant(QuickMatchParticipant.for_user(self.carlos.id))
        self.guest = QuickMatchParticipant.for_guest("Gonzalo", "Invitado", handicap=12.0)
        qm.add_participant(self.guest)
        if iniciar:
            qm.start([qm.creator_participant_id, ParticipantId(self.bea.id.value)])
        if iniciar and completar:
            qm.complete()
        async with self.qm_uow:
            await self.qm_uow.quick_matches.add(qm)
            await self.qm_uow.quick_match_hole_scores.add(
                QuickMatchHoleScore.create(
                    id=QuickMatchHoleScoreId.generate(),
                    quick_match_id=qm.id,
                    hole_number=1,
                    participant_id=qm.creator_participant_id,
                    score=4,
                    recorded_by_participant_id=qm.creator_participant_id,
                )
            )
        self.qm = qm
        return self

    async def ocultar_para(self, user) -> None:
        self.qm.hide_for(ParticipantId(user.id.value))
        async with self.qm_uow:
            await self.qm_uow.quick_matches.update(self.qm)

    def caso_de_uso(self) -> GetSharedQuickMatchUseCase:
        return GetSharedQuickMatchUseCase(
            self.qm_uow,
            self.user_uow,
            self.social_uow,
            MatchPlayScoring(),
            ScoringCoverageService(),
            self.golf_course_uow,
        )

    async def ver(self, quien=None) -> SharedQuickMatchDetailResponseDTO:
        quien = quien or self.viewer
        return await self.caso_de_uso().execute(str(self.qm.id.value), str(quien.id.value))

    def nombre_de(self, detalle, participant_id) -> str | None:
        return next(p.name for p in detalle.participants if p.participant_id == participant_id)


@pytest.fixture
async def escena(qm_uow, user_uow, social_uow, golf_course_uow):
    return await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar()


# ==================== K1 y K3: el amigo la ve entera ====================


class TestFriendCanViewFinishedMatch:
    async def test_friend_of_one_player_sees_the_whole_card(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)

        detalle = await escena.ver()

        assert detalle.id == escena.qm.id.value
        assert detalle.status == "COMPLETED"
        assert detalle.read_only is True
        assert detalle.viewer_is_participant is False
        assert len(detalle.participants) == 4
        assert [(h.hole_number, h.score) for h in detalle.hole_scores] == [(1, 4)]
        assert len(detalle.participant_strokes) == 4
        assert detalle.scoring_assignments

    async def test_the_shared_view_carries_every_field_of_the_detail(self):
        """Tiene que servir para pintar la pantalla actual: ningun campo menos."""
        assert set(QuickMatchDetailResponseDTO.model_fields) <= set(
            SharedQuickMatchDetailResponseDTO.model_fields
        )

    async def test_friend_sees_the_names_of_players_without_a_block(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)

        detalle = await escena.ver()

        assert escena.nombre_de(detalle, escena.ana.id.value) == escena.ana.display_name
        assert escena.nombre_de(detalle, escena.bea.id.value) == escena.bea.display_name
        assert escena.nombre_de(detalle, escena.carlos.id.value) == escena.carlos.display_name

    async def test_one_friend_with_sharing_off_and_another_on_is_enough(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.carlos.id)
        escena.bea.set_activity_sharing(False)
        await _save_user(escena.user_uow, escena.bea)

        detalle = await escena.ver()

        assert detalle.id == escena.qm.id.value
        assert detalle.status == "COMPLETED"
        assert detalle.read_only is True
        assert detalle.viewer_is_participant is False
        assert [(h.hole_number, h.score) for h in detalle.hole_scores] == [(1, 4)]
        assert escena.nombre_de(detalle, escena.bea.id.value) == escena.bea.display_name
        assert escena.nombre_de(detalle, escena.carlos.id.value) == escena.carlos.display_name

    async def test_the_order_of_the_players_does_not_matter(self, escena):
        """Al reves que el anterior: el que no publica va despues, y con Bea basta."""
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.carlos.id)
        escena.carlos.set_activity_sharing(False)
        await _save_user(escena.user_uow, escena.carlos)

        detalle = await escena.ver()

        assert detalle.id == escena.qm.id.value

    async def test_hidden_by_another_player_does_not_matter(self, escena):
        """La papelera es de cada uno: la de Ana no le quita nada a Bea."""
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        await escena.ocultar_para(escena.ana)

        detalle = await escena.ver()

        assert detalle.id == escena.qm.id.value


# ==================== K4: los nombres, como en Actividad ====================


class TestNamesFollowTheActivityRule:
    async def test_guest_comes_without_a_name(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)

        detalle = await escena.ver()

        invitado = next(p for p in detalle.participants if p.is_guest)
        assert invitado.name is None

    async def test_friend_of_one_but_blocked_with_another_hides_that_one(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        await _block(escena.social_uow, escena.carlos.id, escena.viewer.id)

        detalle = await escena.ver()

        assert escena.nombre_de(detalle, escena.carlos.id.value) is None
        assert escena.nombre_de(detalle, escena.bea.id.value) == escena.bea.display_name

    async def test_a_block_put_by_the_viewer_also_hides_the_name(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        await _block(escena.social_uow, escena.viewer.id, escena.ana.id)

        detalle = await escena.ver()

        assert escena.nombre_de(detalle, escena.ana.id.value) is None

    async def test_a_blocked_scorer_has_no_name_in_the_assignments(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        await _block(escena.social_uow, escena.viewer.id, escena.ana.id)

        detalle = await escena.ver()

        nombres = {a.scorer_participant_id: a.scorer_name for a in detalle.scoring_assignments}
        assert nombres[escena.ana.id.value] is None
        assert nombres[escena.bea.id.value] == escena.bea.display_name

    async def test_a_deactivated_player_has_no_name(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        escena.carlos.deactivate(str(uuid4()))
        await _save_user(escena.user_uow, escena.carlos)

        detalle = await escena.ver()

        assert escena.nombre_de(detalle, escena.carlos.id.value) is None


# ==================== K2 y K5: quien no la ve ====================


class TestWhoCannotViewIt:
    async def test_a_stranger_gets_forbidden(self, escena):
        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_friend_with_sharing_off_gets_forbidden(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        escena.bea.set_activity_sharing(False)
        await _save_user(escena.user_uow, escena.bea)

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_match_in_the_friends_trash_gets_forbidden(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        await escena.ocultar_para(escena.bea)

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_deactivated_friend_gives_no_access(self, escena):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        escena.bea.deactivate(str(uuid4()))
        await _save_user(escena.user_uow, escena.bea)

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_a_pending_request_is_not_a_friendship(self, escena):
        async with escena.social_uow:
            await escena.social_uow.friendships.add(
                Friendship.create(
                    id=FriendshipId.generate(),
                    requester_id=escena.viewer.id,
                    addressee_id=escena.bea.id,
                )
            )

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_match_in_progress_gets_forbidden(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        escena = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(
            completar=False
        )
        await create_accepted_friendship(social_uow, escena.viewer.id, escena.bea.id)

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_cancelled_match_gets_forbidden(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        escena = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(
            completar=False
        )
        await create_accepted_friendship(social_uow, escena.viewer.id, escena.bea.id)
        escena.qm.cancel()
        async with escena.qm_uow:
            await escena.qm_uow.quick_matches.update(escena.qm)

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_the_message_does_not_tell_the_state_of_the_match(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        """
        A quien no participa, el 403 le dice lo mismo este o no terminada la
        partida: si no, deduciria su estado (22 oct 2026).
        """
        terminada = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar()
        with pytest.raises(QuickMatchNotSharedError) as de_la_terminada:
            await terminada.ver()
        en_juego = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(
            completar=False
        )
        with pytest.raises(QuickMatchNotSharedError) as de_la_que_sigue:
            await en_juego.ver()

        assert str(de_la_terminada.value) == str(de_la_que_sigue.value)

    async def test_unknown_match_is_not_found(self, escena):
        with pytest.raises(QuickMatchNotFoundError):
            await escena.caso_de_uso().execute(str(uuid4()), str(escena.viewer.id.value))


# ==================== K6: los participantes, igual ====================


class TestParticipantsKeepTheirView:
    async def test_participant_sees_it_with_every_name(self, escena):
        await _block(escena.social_uow, escena.bea.id, escena.carlos.id)

        detalle = await escena.ver(escena.bea)

        assert detalle.viewer_is_participant is True
        assert escena.nombre_de(detalle, escena.carlos.id.value) == escena.carlos.display_name
        invitado = next(p for p in detalle.participants if p.is_guest)
        assert invitado.name == "Gonzalo Invitado"

    async def test_the_participant_view_matches_the_regular_detail(self, escena):
        regular = await GetQuickMatchUseCase(
            escena.qm_uow,
            escena.user_uow,
            MatchPlayScoring(),
            ScoringCoverageService(),
            escena.golf_course_uow,
        ).execute(str(escena.qm.id.value), str(escena.bea.id.value))

        compartida = await escena.ver(escena.bea)

        assert compartida.model_dump(exclude={"read_only", "viewer_is_participant"}) == (
            regular.model_dump()
        )

    async def test_the_regular_detail_stays_participant_only(self, escena):
        """Ser amigo no abre `GET /quick-matches/{id}`: esa sigue siendo la de anotar."""
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)

        with pytest.raises(NotQuickMatchParticipantError):
            await GetQuickMatchUseCase(
                escena.qm_uow,
                escena.user_uow,
                MatchPlayScoring(),
                ScoringCoverageService(),
                escena.golf_course_uow,
            ).execute(str(escena.qm.id.value), str(escena.viewer.id.value))


class TestParticipantSeesItInAnyState:
    """
    Arreglo del 22 oct (prueba de punta a punta): a un PARTICIPANTE se le responde
    200 con `viewer_is_participant: true` sea cual sea el estado, para que el
    cliente lo lleve a su anotacion. A los demas, igual que antes.
    """

    async def test_participant_of_a_match_in_progress_gets_it(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        escena = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(
            completar=False
        )

        detalle = await escena.ver(escena.bea)

        assert detalle.viewer_is_participant is True
        assert detalle.status == "IN_PROGRESS"

    async def test_participant_of_a_pending_match_gets_it(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        escena = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(iniciar=False)

        detalle = await escena.ver(escena.carlos)

        assert detalle.viewer_is_participant is True
        assert detalle.status == "PENDING"

    async def test_the_creator_of_a_cancelled_match_gets_it(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        escena = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(
            completar=False
        )
        escena.qm.cancel()
        async with escena.qm_uow:
            await escena.qm_uow.quick_matches.update(escena.qm)

        detalle = await escena.ver(escena.ana)

        assert detalle.viewer_is_participant is True
        assert detalle.status == "CANCELLED"

    async def test_a_friend_of_a_pending_match_still_gets_forbidden(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        escena = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(iniciar=False)
        await create_accepted_friendship(social_uow, escena.viewer.id, escena.bea.id)

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()

    async def test_a_stranger_of_a_match_in_progress_still_gets_forbidden(
        self, qm_uow, user_uow, social_uow, golf_course_uow
    ):
        escena = await _Escena(qm_uow, user_uow, social_uow, golf_course_uow).montar(
            completar=False
        )

        with pytest.raises(QuickMatchNotSharedError):
            await escena.ver()


# ==================== Sin N+1 ====================


class TestReadsInBulk:
    async def test_users_are_read_in_one_go(self, escena, monkeypatch):
        await create_accepted_friendship(escena.social_uow, escena.viewer.id, escena.bea.id)
        uno_a_uno = []
        original = escena.user_uow.users.find_by_id

        async def _espia(user_id):
            uno_a_uno.append(user_id)
            return await original(user_id)

        monkeypatch.setattr(escena.user_uow.users, "find_by_id", _espia)

        await escena.ver()

        assert uno_a_uno == []

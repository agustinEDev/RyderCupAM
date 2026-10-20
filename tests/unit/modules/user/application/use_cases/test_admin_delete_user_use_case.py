"""Tests para AdminDeleteUserUseCase."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.use_cases.admin_delete_user_use_case import (
    AdminDeleteUserUseCase,
)
from src.modules.user.domain.entities.terms_acceptance import TermsAcceptance
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.exceptions import UserHasActivityException
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


def _make_uow_mock(**repo_attrs):
    """Crea un UoW mock cuyo __aenter__/__aexit__ funcionan como context manager."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    for name, repo in repo_attrs.items():
        setattr(uow, name, repo)
    return uow


class TestAdminDeleteUserUseCase:
    @pytest.fixture
    def user_uow(self):
        return InMemoryUnitOfWork()

    @pytest.fixture
    async def existing_user(self, user_uow):
        user = User.create(
            first_name="Carlos",
            last_name="Ruiz",
            email_str="carlos@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    def _make_use_case(
        self,
        user_uow,
        competitions_created=0,
        has_scores=False,
        quick_match_created=False,
        golf_courses_created=0,
        capitanea_un_draft=False,
        juega_una_partida=False,
    ):
        competitions_repo = AsyncMock()
        competitions_repo.count_by_creator = AsyncMock(return_value=competitions_created)
        hole_scores_repo = AsyncMock()
        hole_scores_repo.exists_by_player = AsyncMock(return_value=has_scores)
        drafts_repo = AsyncMock()
        drafts_repo.exists_by_captain = AsyncMock(return_value=capitanea_un_draft)
        partidas_repo = AsyncMock()
        partidas_repo.existe_con_jugador = AsyncMock(return_value=juega_una_partida)
        competition_uow = _make_uow_mock(
            competitions=competitions_repo,
            hole_scores=hole_scores_repo,
            drafts=drafts_repo,
            partidas=partidas_repo,
        )

        quick_matches_repo = AsyncMock()
        quick_matches_repo.exists_created_by = AsyncMock(return_value=quick_match_created)
        quick_match_uow = _make_uow_mock(quick_matches=quick_matches_repo)

        golf_courses_repo = AsyncMock()
        golf_courses_repo.count_by_creator = AsyncMock(return_value=golf_courses_created)
        golf_course_uow = _make_uow_mock(golf_courses=golf_courses_repo)

        return AdminDeleteUserUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)

    async def test_deletes_user_with_no_activity(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow)
        await use_case.execute(str(existing_user.id.value))

        async with user_uow:
            assert await user_uow.users.find_by_id(existing_user.id) is None

    async def test_blocks_delete_when_user_created_competitions(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, competitions_created=2)

        with pytest.raises(UserHasActivityException) as exc_info:
            await use_case.execute(str(existing_user.id.value))
        assert "2 competition(s)" in str(exc_info.value)

        async with user_uow:
            assert await user_uow.users.find_by_id(existing_user.id) is not None

    async def test_blocks_delete_when_user_has_hole_scores(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, has_scores=True)

        with pytest.raises(UserHasActivityException):
            await use_case.execute(str(existing_user.id.value))

    async def test_blocks_delete_when_user_created_quick_match(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, quick_match_created=True)

        with pytest.raises(UserHasActivityException):
            await use_case.execute(str(existing_user.id.value))

    async def test_blocks_delete_when_user_requested_golf_course(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, golf_courses_created=1)

        with pytest.raises(UserHasActivityException):
            await use_case.execute(str(existing_user.id.value))

    async def test_raises_not_found_before_checking_activity(self, user_uow):
        from uuid import uuid4

        use_case = self._make_use_case(user_uow)
        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(uuid4()))

    @pytest.mark.asyncio
    async def test_blocks_delete_when_user_plays_a_tee_group(self, user_uow, existing_user):
        """
        Given: un usuario que juega una partida de stroke play (#251, PR 4)
        When: un administrador intenta borrarlo
        Then: se le dice que tiene actividad: la clave ajena (RESTRICT) no lo dejaría
        """
        use_case = self._make_use_case(user_uow, juega_una_partida=True)

        with pytest.raises(UserHasActivityException) as error:
            await use_case.execute(str(existing_user.id.value))

        assert "tee group" in str(error.value).lower()
        async with user_uow:
            assert await user_uow.users.find_by_id(existing_user.id) is not None

    async def test_blocks_delete_when_user_captains_a_draft(self, user_uow, existing_user):
        """
        Given: un usuario que capitanea una sala de draft
        When: un administrador intenta borrarlo
        Then: se le dice que tiene actividad, y no se estrella contra la clave ajena
        """
        use_case = self._make_use_case(user_uow, capitanea_un_draft=True)

        with pytest.raises(UserHasActivityException) as error:
            await use_case.execute(str(existing_user.id.value))

        assert "draft" in str(error.value).lower()
        async with user_uow:
            assert await user_uow.users.find_by_id(existing_user.id) is not None


class TestAdminDeleteKeepsTermsHistory:
    """Borrar la cuenta conserva la prueba de aceptación de los Términos (3 años)."""

    @staticmethod
    def _use_case(user_uow):
        return TestAdminDeleteUserUseCase()._make_use_case(user_uow)

    @staticmethod
    async def _usuario_con_historial(user_uow):
        user = User.create(
            first_name="Carlos",
            last_name="Ruiz",
            email_str="carlos@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        fila = TermsAcceptance.record(
            user_id=user.id,
            user_email="carlos@test.com",
            terms_version="2026-10-20",
            accepted_at=datetime(2026, 10, 20, tzinfo=UTC),
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0 Safari",
        )
        async with user_uow:
            await user_uow.users.save(user)
            await user_uow.terms_acceptances.save(fila)
        return user, fila

    async def test_delete_keeps_the_terms_history_detached(self):
        """
        Given: Un usuario sin actividad con una aceptación de los Términos
        When: El admin borra su cuenta
        Then: La fila sigue, sin usuario, con el email y la fecha de borrado (UTC, ahora)
        """
        user_uow = InMemoryUnitOfWork()
        user, fila = await self._usuario_con_historial(user_uow)
        antes = datetime.now(UTC)

        await self._use_case(user_uow).execute(str(user.id.value))

        assert fila.user_id is None
        assert fila.user_email == "carlos@test.com"
        assert fila.user_deleted_at is not None
        assert antes <= fila.user_deleted_at <= datetime.now(UTC)
        assert await user_uow.users.find_by_id(user.id) is None

    async def test_blocked_delete_does_not_touch_the_history(self):
        """
        Given: Un usuario con actividad (ha creado una competición)
        When: El admin intenta borrarlo
        Then: Se bloquea y su historial sigue apuntando a él, sin fecha de borrado
        """
        user_uow = InMemoryUnitOfWork()
        user, fila = await self._usuario_con_historial(user_uow)
        use_case = TestAdminDeleteUserUseCase()._make_use_case(user_uow, competitions_created=1)

        with pytest.raises(UserHasActivityException):
            await use_case.execute(str(user.id.value))

        assert fila.user_id == user.id
        assert fila.user_deleted_at is None

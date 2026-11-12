"""Tests para BlockUserUseCase."""

import pytest

from src.modules.social.application.exceptions import AddresseeNotFoundError
from src.modules.social.application.use_cases.block_user_use_case import BlockUserUseCase
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import (
    InvalidFriendshipStatusViolation,
    SelfFriendRequestViolation,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)

pytestmark = pytest.mark.asyncio


class TestBlockUserUseCase:
    @pytest.fixture
    def uow(self):
        return InMemorySocialUnitOfWork()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _create_user(self, user_uow, email):
        user = User.create(
            first_name="Test",
            last_name="User",
            email_str=email,
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    async def test_block_without_existing_relationship_creates_blocked(self, uow, user_uow):
        blocker = await self._create_user(user_uow, "blocker@test.com")
        blocked = await self._create_user(user_uow, "blocked@test.com")

        use_case = BlockUserUseCase(uow, user_uow)
        response = await use_case.execute(str(blocker.id.value), str(blocked.id.value))

        assert response.status == "BLOCKED"

    async def test_block_existing_accepted_friendship(self, uow, user_uow):
        blocker = await self._create_user(user_uow, "blocker2@test.com")
        blocked = await self._create_user(user_uow, "blocked2@test.com")

        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=blocker.id, addressee_id=blocked.id
        )
        friendship.accept()
        async with uow:
            await uow.friendships.add(friendship)

        use_case = BlockUserUseCase(uow, user_uow)
        response = await use_case.execute(str(blocker.id.value), str(blocked.id.value))

        assert response.status == "BLOCKED"

    async def test_block_self_raises(self, uow, user_uow):
        user = await self._create_user(user_uow, "solo2@test.com")
        use_case = BlockUserUseCase(uow, user_uow)

        with pytest.raises(SelfFriendRequestViolation):
            await use_case.execute(str(user.id.value), str(user.id.value))

    async def test_block_nonexistent_user_raises(self, uow, user_uow):
        from uuid import uuid4

        blocker = await self._create_user(user_uow, "blocker3@test.com")
        use_case = BlockUserUseCase(uow, user_uow)

        with pytest.raises(AddresseeNotFoundError):
            await use_case.execute(str(blocker.id.value), str(uuid4()))

    async def test_block_is_idempotent(self, uow, user_uow):
        blocker = await self._create_user(user_uow, "blocker4@test.com")
        blocked = await self._create_user(user_uow, "blocked4@test.com")
        use_case = BlockUserUseCase(uow, user_uow)

        first = await use_case.execute(str(blocker.id.value), str(blocked.id.value))
        second = await use_case.execute(str(blocker.id.value), str(blocked.id.value))

        assert first.id == second.id
        assert second.status == "BLOCKED"

    async def test_block_handles_concurrent_insert_race_idempotently(self, uow, user_uow):
        """Simula dos bloqueos concurrentes chocando contra uq_friendship_pair.

        A diferencia de un mock que fuerce directamente la excepcion, aqui la
        fila "ganadora" se inserta con el `add()` real del repositorio en
        memoria (que ahora aplica el mismo invariante de pareja unica que el
        indice `uq_friendship_pair` de la BD) — solo se parchea `find_by_pair`
        para simular la ventana de carrera (lectura antes del commit
        concurrente). La excepcion `DuplicateFriendshipViolation` la produce
        el propio adaptador, no el test.
        """
        blocker = await self._create_user(user_uow, "blocker5@test.com")
        blocked = await self._create_user(user_uow, "blocked5@test.com")
        use_case = BlockUserUseCase(uow, user_uow)

        winning_friendship = Friendship.create_blocked(
            id=FriendshipId.generate(), blocker_id=blocker.id, blocked_id=blocked.id
        )
        async with uow:
            await uow.friendships.add(winning_friendship)

        original_find_by_pair = uow.friendships.find_by_pair
        call_count = 0

        async def find_by_pair_with_race(user_id_a, user_id_b):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simula que la lectura ocurrio antes de que la request
                # concurrente ganara la carrera e insertara la fila.
                return None
            return await original_find_by_pair(user_id_a, user_id_b)

        uow.friendships.find_by_pair = find_by_pair_with_race

        response = await use_case.execute(str(blocker.id.value), str(blocked.id.value))

        assert response.status == "BLOCKED"
        assert response.id == winning_friendship.id.value


class TestBloqueoEnCarrera:
    """Carreras al bloquear que tapaba la exención de mypy (fase 5, paso 3)."""

    @pytest.fixture
    def uow(self):
        return InMemorySocialUnitOfWork()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _usuario(self, user_uow, email):
        user = User.create(
            first_name="Test", last_name="User", email_str=email, plain_password="SecureP@ssw0rd123"
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    def _carrera(self, uow, despues_del_choque=None):
        """La primera lectura no ve la fila; la segunda ve lo que haya (o nada)."""
        original = uow.friendships.find_by_pair
        llamadas = 0

        async def find_by_pair(a, b):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 1:
                return None
            if despues_del_choque is not None:
                await despues_del_choque()
            return await original(a, b)

        uow.friendships.find_by_pair = find_by_pair

    async def test_bloquear_mientras_llega_una_solicitud_del_otro_bloquea_igualmente(
        self, uow, user_uow
    ):
        """
        Given B manda una solicitud a A justo cuando A le bloquea (gana la solicitud la carrera)
        When A termina de bloquear
        Then la relación queda BLOQUEADA por A, no como solicitud pendiente
        """
        a = await self._usuario(user_uow, "a.carrera@test.com")
        b = await self._usuario(user_uow, "b.carrera@test.com")
        solicitud = Friendship.create(
            id=FriendshipId.generate(), requester_id=b.id, addressee_id=a.id
        )
        async with uow:
            await uow.friendships.add(solicitud)
        self._carrera(uow)

        respuesta = await BlockUserUseCase(uow, user_uow).execute(str(a.id.value), str(b.id.value))

        assert respuesta.status == "BLOCKED"
        async with uow:
            guardada = await uow.friendships.find_by_pair(a.id, b.id)
        assert guardada.is_blocked()
        assert guardada.blocked_by == a.id

    async def test_bloquear_si_la_relacion_desaparece_en_la_carrera_es_un_conflicto(
        self, uow, user_uow
    ):
        """
        Given otra petición crea la pareja y otra la borra antes de releer
        When A termina de bloquear
        Then es un conflicto (409), no un 500
        """
        a = await self._usuario(user_uow, "a.borrada@test.com")
        b = await self._usuario(user_uow, "b.borrada@test.com")
        ganadora = Friendship.create(
            id=FriendshipId.generate(), requester_id=b.id, addressee_id=a.id
        )
        async with uow:
            await uow.friendships.add(ganadora)

        async def la_borran():
            await uow.friendships.remove(ganadora)

        self._carrera(uow, despues_del_choque=la_borran)

        with pytest.raises(InvalidFriendshipStatusViolation):
            await BlockUserUseCase(uow, user_uow).execute(str(a.id.value), str(b.id.value))

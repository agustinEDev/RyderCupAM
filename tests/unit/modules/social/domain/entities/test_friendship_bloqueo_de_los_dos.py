"""
Bloqueo de los dos en la entidad Friendship (SB-02, aprobado el 16 nov 2026).

Una sola fila por pareja. Si B ya bloqueó a A y A bloquea a B, la fila guarda
los dos bloqueos: el primero en `blocked_by` y el segundo en `second_blocked_at`.
Cada uno ve solo el suyo, y si uno desbloquea, el del otro sigue en pie.
"""

from uuid import uuid4

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import (
    InvalidFriendshipStatusViolation,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.domain.value_objects.friendship_status import FriendshipStatus
from src.modules.user.domain.value_objects.user_id import UserId


def _bloqueo_de(quien: UserId, a_quien: UserId) -> Friendship:
    return Friendship.create_blocked(
        id=FriendshipId.generate(), blocker_id=quien, blocked_id=a_quien
    )


@pytest.fixture
def a() -> UserId:
    return UserId(uuid4())


@pytest.fixture
def b() -> UserId:
    return UserId(uuid4())


class TestBloquearAQuienYaTeBloqueo:
    def test_se_guardan_los_dos_bloqueos(self, a, b):
        """Given B bloqueó a A / When A bloquea a B / Then la fila es de los dos."""
        fila = _bloqueo_de(b, a)

        fila.block(a)

        assert fila.bloqueado_por(a) and fila.bloqueado_por(b)
        assert fila.blocked_by == b
        assert fila.second_blocked_at is not None

    def test_el_segundo_bloqueo_no_toca_lo_que_ve_el_primero(self, a, b):
        """Given B bloqueó a A / When A bloquea / Then ni autor, ni fechas, ni participantes cambian."""
        fila = _bloqueo_de(b, a)
        antes = (fila.requester_id, fila.addressee_id, fila.blocked_by)
        fechas = (fila.created_at, fila.updated_at, fila.responded_at)

        fila.block(a)

        assert (fila.requester_id, fila.addressee_id, fila.blocked_by) == antes
        assert (fila.created_at, fila.updated_at, fila.responded_at) == fechas

    def test_volver_a_bloquear_no_mueve_nada(self, a, b):
        """Given los dos bloqueados / When cualquiera vuelve a bloquear / Then todo igual."""
        fila = _bloqueo_de(b, a)
        fila.block(a)
        segundo = fila.second_blocked_at

        fila.block(a)
        fila.block(b)

        assert fila.second_blocked_at == segundo
        assert fila.blocked_by == b

    def test_un_bloqueo_sin_autor_lo_toma_quien_bloquea(self, a, b):
        """Given un BLOCKED sin autor (la tabla lo admite) / When A bloquea / Then es de A."""
        fila = Friendship.reconstruct(
            id=FriendshipId.generate(),
            requester_id=a,
            addressee_id=b,
            status=FriendshipStatus.BLOCKED,
            blocked_by=None,
        )

        fila.block(a)

        assert fila.blocked_by == a
        assert fila.second_blocked_at is None


class TestQuienVeAQuien:
    def test_quien_fue_bloqueado_y_no_bloqueo_no_ve_al_otro(self, a, b):
        """F-09: B bloqueó a A y A no a B → para A, B no existe; para B, A sí."""
        fila = _bloqueo_de(b, a)

        assert fila.lo_oculta_a(a) is True
        assert fila.lo_oculta_a(b) is False

    def test_con_los_dos_bloqueos_ninguno_desaparece_para_el_otro(self, a, b):
        """Si A desapareciera para B, B sabría que A también le bloqueó (y al revés)."""
        fila = _bloqueo_de(b, a)
        fila.block(a)

        assert fila.lo_oculta_a(a) is False
        assert fila.lo_oculta_a(b) is False

    def test_el_segundo_bloqueador_lo_ve_como_un_bloqueo_suyo(self, a, b):
        fila = _bloqueo_de(b, a)
        fila.block(a)

        assert fila.segundo_bloqueador() == a
        assert _bloqueo_de(b, a).segundo_bloqueador() is None


class TestDesbloquear:
    def test_desbloquea_el_primero_y_queda_el_del_segundo(self, a, b):
        """Caso 7: B desbloquea → la fila sigue, ahora solo de A."""
        fila = _bloqueo_de(b, a)
        fila.block(a)

        se_borra = fila.unblock(b)

        assert se_borra is False
        assert fila.blocked_by == a
        assert fila.second_blocked_at is None
        assert fila.lo_oculta_a(b) is True

    def test_al_quedarse_con_la_fila_el_segundo_la_ve_como_su_bloqueo(self, a, b):
        """
        Caso 7: la fila que queda tiene que ser la que A ya veía (requester A, fechas
        de su bloqueo); si no, al repetir su bloqueo vería a B como autor.
        """
        fila = _bloqueo_de(b, a)
        fila.block(a)
        cuando = fila.second_blocked_at

        fila.unblock(b)

        assert (fila.requester_id, fila.addressee_id) == (a, b)
        assert fila.created_at == fila.updated_at == fila.responded_at == cuando

    def test_desbloquea_el_segundo_y_queda_el_del_primero(self, a, b):
        """Caso 8: A desbloquea → la fila sigue, solo de B."""
        fila = _bloqueo_de(b, a)
        fila.block(a)

        se_borra = fila.unblock(a)

        assert se_borra is False
        assert fila.blocked_by == b
        assert fila.second_blocked_at is None
        assert fila.lo_oculta_a(a) is True

    def test_si_solo_bloqueaba_uno_la_fila_se_borra(self, a, b):
        """Caso 9."""
        assert _bloqueo_de(a, b).unblock(a) is True

    def test_quien_no_bloqueo_no_puede_desbloquear(self, a, b):
        with pytest.raises(InvalidFriendshipStatusViolation):
            _bloqueo_de(b, a).unblock(a)
